"""Forgot password and the email on Profile (v0.27.0, F24, DEC-029), test cases TC-37.x.
Mail goes to a fake mailbox (rule T3)."""
import re
from datetime import timedelta
from helpers import check, finish, text, FakeMailbox
from werkzeug.security import generate_password_hash as g

from app import app, upgrade_database
app.config['TEST_PLAIN_LOGIN'] = True   # v0.28.0: password-only login; this file isn't about the login code (DEC-030)
from models import db, User, LoginSession, utc_now

app.config['CSRF_ENABLED'] = False
mailbox = FakeMailbox(app)

with app.app_context():
    db.drop_all(); upgrade_database()
    now = utc_now()
    db.session.add_all([
        User(username='olivia', password_hash=g('owner-pass-1'), role='owner', email='olivia@example.com'),
        User(username='cara', password_hash=g('cashier-pass-1'), role='cashier', email='cara@example.com', email_verified_at=now),
        User(username='carl', password_hash=g('cashier-pass-2'), role='cashier', email='carl@example.com'),   # not confirmed
        User(username='off', password_hash=g('cashier-pass-3'), role='cashier', email='off@example.com',
             email_verified_at=now, is_active=False),
        User(username='old', password_hash=g('cashier-pass-4'), role='cashier')])   # made before v0.27.0: no email
    db.session.commit()


def client(username, password):
    c = app.test_client()
    c.post('/login', data={'username': username, 'password': password})
    return c


def user(name):
    with app.app_context():
        return User.query.filter_by(username=name).first()


def logins(name):
    with app.app_context():
        return LoginSession.query.filter_by(user_id=user(name).id).count()


def ask(address, browser=None):
    browser = browser or app.test_client()
    return browser, browser.post('/forgot-password', data={'email': address}, follow_redirects=True)


# ---- TC-37.1 the same answer whatever the address; a code only for a switched-on account with a confirmed email
answers = {}
for address in ['cara@example.com', 'nobody@example.com', 'carl@example.com', 'off@example.com']:
    before = len(mailbox)
    _, r = ask(address)
    shown = re.findall(r'<div class="alert[^"]*">(.*?)</div>', text(r), re.S)   # the messages on the page
    answers[address] = (' '.join(shown).replace(address, 'ADDRESS'), len(mailbox) - before)
pages = {page for page, _ in answers.values()}
check('TC-37.1 the page says the same for an account, no account, an unconfirmed email and a switched-off one',
      len(pages) == 1 and 'If an account uses ADDRESS, we sent it a 6-digit code' in pages.pop())
check('TC-37.1 only the switched-on account with a confirmed email gets a code',
      [sent for _, sent in answers.values()] == [1, 0, 0, 0] and mailbox.code_for('cara@example.com'))
check('TC-37.1 the email says what the code is for, when, from which computer, and what to do if it wasn\'t you',
      all(w in mailbox.last_to('cara@example.com').get_content()
          for w in ['choose a new password', '10 minutes', 'from the computer', 'change your password']))
check('TC-37.1 the login page links to Forgot password', 'href="/forgot-password"' in text(app.test_client().get('/login')))
check('TC-37.1 the code page needs the first step (no address: back to it)',
      app.test_client().get('/forgot-password/code').headers.get('Location', '').endswith('/forgot-password'))

# ---- TC-37.2 the code and a new password; every login of the account ends
cara_till = client('cara', 'cashier-pass-1')
check('TC-37.2 (before) cara is logged in on a till', logins('cara') == 1)
browser, _ = ask('cara@example.com')
with app.app_context():   # the one-a-minute limit: pretend the first code was sent earlier
    from models import EmailCode
    for row in EmailCode.query.filter_by(email='cara@example.com'):
        row.created_at -= timedelta(minutes=2)
    db.session.commit()
browser, _ = ask('cara@example.com', browser)
code = mailbox.code_for('cara@example.com')
wrong = '000000' if code != '000000' else '111111'
r = browser.post('/forgot-password/code', data={'code': code, 'new_password': 'short', 'confirm_password': 'short'})
check('TC-37.2 a password that breaks the rules is refused BEFORE the code is used', 'at least 8' in text(r))
r = browser.post('/forgot-password/code', data={'code': wrong, 'new_password': 'Kape-2026-cara', 'confirm_password': 'Kape-2026-cara'})
check('TC-37.2 a wrong code: "not right", tries left', 'not right' in text(r))
r = browser.post('/forgot-password/code', data={'code': code, 'new_password': 'Kape-2026-cara',
                                                'confirm_password': 'Kape-2026-cara'}, follow_redirects=True)
check('TC-37.2 the right code saves the new password and goes to the login page', 'new password is saved' in text(r))
check('TC-37.2 the new password works, the old one doesn\'t',
      client('cara', 'Kape-2026-cara').get('/sales/new').status_code == 200
      and app.test_client().post('/login', data={'username': 'cara', 'password': 'cashier-pass-1'}).status_code == 200)
check('TC-37.2 the till that was logged in as cara was logged out', cara_till.get('/sales/new').status_code == 302)
r = browser.post('/forgot-password/code', data={'code': code, 'new_password': 'Kape-2026-again', 'confirm_password': 'Kape-2026-again'})
check('TC-37.2 the same code can\'t be used again', 'no longer works' in text(r) or r.status_code == 302)

# ---- TC-37.3 a new password equal to the username is refused only after the right code (reveals no username)
with app.app_context():
    for row in EmailCode.query.filter_by(email='cara@example.com'):
        row.created_at -= timedelta(minutes=2)
    db.session.commit()
browser, _ = ask('cara@example.com')
code = mailbox.code_for('cara@example.com')
r = browser.post('/forgot-password/code', data={'code': '999999' if code != '999999' else '888888',
                                                'new_password': 'cara1234', 'confirm_password': 'cara1234'})
check('TC-37.3 with a wrong code, a password equal to the username gets the "not right" answer, nothing about the username',
      'not right' in text(r) and "be the same as" not in text(r).replace('&#39;', "'"))

# ---- TC-37.4 limits: 10 requests an hour per computer; email not set up says so for every address
same_computer = app.test_client()   # its own address: the other test browsers share 127.0.0.1
statuses = [same_computer.post('/forgot-password', data={'email': f'n{i}@example.com'},
                               environ_base={'REMOTE_ADDR': '10.0.0.9'}).status_code for i in range(12)]
check('TC-37.4 a computer gets 10 requests an hour, then a plain "too many" (429)',
      statuses[:10] == [302] * 10 and statuses[10:] == [429, 429])
app.config['MAIL'], saved = {}, app.config['MAIL']
_, r = ask('cara@example.com', app.test_client())
check('TC-37.4 email not set up: the page says so (the same for every address)', 'set a new password for you' in text(r).replace('&#39;', "'"))
app.config['MAIL'] = saved

# ---- TC-37.5 the email on Profile: add or change it with the current password and a code to the NEW address
old = client('old', 'cashier-pass-4')
check('TC-37.5 an account from before v0.27.0 is asked to add an email', 'No email yet' in text(old.get('/profile')))
r = old.post('/profile/email', data={'email': 'old@example.com', 'current_password': 'wrong'}, follow_redirects=True)
check('TC-37.5 the current password is needed', 'Current password is wrong' in text(r) and not mailbox.last_to('old@example.com'))
r = old.post('/profile/email', data={'email': 'cara@example.com', 'current_password': 'cashier-pass-4'}, follow_redirects=True)
check('TC-37.5 an address another account uses is refused', 'Another account already uses' in text(r))
r = old.post('/profile/email', data={'email': 'old@example.com', 'current_password': 'cashier-pass-4'}, follow_redirects=True)
check('TC-37.5 a code goes to the new address and the page asks for it', 'Code sent to old@example.com' in text(r)
      and mailbox.code_for('old@example.com'))
check('TC-37.5 nothing is saved before the code', user('old').email is None)
r = old.post('/profile/email/confirm', data={'code': mailbox.code_for('old@example.com')}, follow_redirects=True)
check('TC-37.5 the right code saves it, confirmed', 'Email confirmed: old@example.com' in text(r)
      and user('old').email == 'old@example.com' and user('old').email_verified_at is not None)

# ---- TC-37.6 the owner's email is fixed (S12); the owner can only confirm it
owner = client('olivia', 'owner-pass-1')
page = text(owner.get('/profile'))
check('TC-37.6 the owner sees the email as "Not confirmed" and a button to confirm it, no box to change it',
      'Not confirmed' in page and 'Send me a code to confirm it' in page and 'name="email"' not in page)
owner.post('/profile/email', data={'email': 'someone-else@example.com', 'current_password': 'owner-pass-1'})
check('TC-37.6 posting another address anyway sends the code to the owner\'s OWN address',
      mailbox.code_for('olivia@example.com') and not mailbox.last_to('someone-else@example.com'))
owner.post('/profile/email/confirm', data={'code': mailbox.code_for('olivia@example.com')})
check('TC-37.6 the right code confirms it; the address is unchanged',
      user('olivia').email == 'olivia@example.com' and user('olivia').email_verified_at is not None)

finish('PASSWORD RESET')
