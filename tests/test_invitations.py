"""Invitations and signing up, and the rules for emailed codes (v0.27.0, F24, rules S12 and S14, DEC-003, DEC-029),
test cases TC-36.x. Mail goes to a fake mailbox (rule T3)."""
from datetime import timedelta
from urllib.parse import urlparse
from helpers import check, finish, text, FakeMailbox
from werkzeug.security import generate_password_hash as g

from app import app, upgrade_database
app.config['TEST_PLAIN_LOGIN'] = True   # v0.28.0: password-only login; this file isn't about the login code (DEC-030)
from models import db, User, Invitation, EmailCode, utc_now

app.config['CSRF_ENABLED'] = False
mailbox = FakeMailbox(app)

with app.app_context():
    db.drop_all(); upgrade_database()
    db.session.add_all([User(username='olivia', password_hash=g('owner-pass-1'), role='owner', email='olivia@example.com'),
                        User(username='ana', password_hash=g('admin-pass-2'), role='admin', can_invite=True),
                        User(username='cara', password_hash=g('cashier-pass-1'), role='cashier', email='cara@example.com')])
    db.session.commit()


def client(username, password):
    c = app.test_client()
    c.post('/login', data={'username': username, 'password': password})
    return c


def path_of(link):
    return urlparse(link).path


def user(name):
    with app.app_context():
        return User.query.filter_by(username=name).first()


owner, ana = client('olivia', 'owner-pass-1'), client('ana', 'admin-pass-2')

# ---- TC-36.1 the owner invites someone; the email has a one-time link; the database has only its hash
r = owner.post('/admin/users/invite', data={'email': 'Jun@Example.com', 'role': 'cashier'}, follow_redirects=True)
check('TC-36.1 "Invitation sent", and one email to the invited address', 'Invitation sent to Jun@Example.com' in text(r)
      and mailbox.last_to('jun@example.com') is not None)
link = mailbox.link_for('jun@example.com')
token = path_of(link).rsplit('/', 1)[-1]
with app.app_context():
    invitation = Invitation.query.filter_by(email='jun@example.com').first()
    stored = (invitation.token_hash, invitation.role, invitation.expires_at - invitation.created_at)
check('TC-36.1 the email names the shop, the inviter, the role and the 48 hours',
      all(words in mailbox.last_to('jun@example.com').get_content() for words in ['olivia invited you', 'as a cashier', '48 hours']))
check('TC-36.1 only a 64-character keyed hash of the link\'s token is stored (S14)',
      len(stored[0]) == 64 and token not in stored[0] and len(token) >= 40)
check('TC-36.1 it works for 48 hours, with the role the owner chose', stored[1] == 'cashier' and stored[2] == timedelta(hours=48))
check('TC-36.1 the Users page lists the invitation with Send again and Cancel',
      all(w in text(owner.get('/admin/users')) for w in ['jun@example.com', 'Send again', 'Cancel']))

# ---- TC-36.2 the link's address opens on a phone: the network address, not 127.0.0.1 (when other devices are allowed)
import blueprints.accounts as accounts_page
app.config['SERVER_HOST'] = '0.0.0.0'
real_address, accounts_page.network_address = accounts_page.network_address, lambda: '192.168.1.20'
LOCAL = 'http://127.0.0.1:5000'
owner_here = app.test_client()   # the owner at the counter computer, using 127.0.0.1
owner_here.post('/login', data={'username': 'olivia', 'password': 'owner-pass-1'}, base_url=LOCAL)
owner_here.post('/admin/users/invite', data={'email': 'phone@example.com', 'role': 'cashier'}, base_url=LOCAL)
check('TC-36.2 a link sent while using 127.0.0.1 uses the computer\'s network address',
      mailbox.link_for('phone@example.com').startswith('http://192.168.1.20:5000/signup/'))
app.config['SERVER_HOST'] = '127.0.0.1'
owner_here.post('/admin/users/invite', data={'email': 'local@example.com', 'role': 'cashier'}, base_url=LOCAL)
check('TC-36.2 ... but not when the system only allows this computer',
      mailbox.link_for('local@example.com').startswith('http://127.0.0.1:5000/signup/'))
accounts_page.network_address = real_address

# ---- TC-36.3 signing up: username and password, then the code sent to the invited address
visitor = app.test_client()
page = text(visitor.get(path_of(link)))
check('TC-36.3 the link opens the signup page with the invited email and role', 'jun@example.com' in page and 'Cashier' in page)
for form, words in [({'username': 'j', 'password': 'Kape-2026-jun', 'confirm_password': 'Kape-2026-jun'}, '3 to 50'),
                    ({'username': 'jun dela cruz', 'password': 'Kape-2026-jun', 'confirm_password': 'Kape-2026-jun'}, 'no spaces'),
                    ({'username': 'Cara', 'password': 'Kape-2026-jun', 'confirm_password': 'Kape-2026-jun'}, 'taken'),
                    ({'username': 'jun', 'password': 'short', 'confirm_password': 'short'}, 'at least 8'),
                    ({'username': 'jun', 'password': 'Kape-2026-jun', 'confirm_password': 'other-one-1'}, 'do not match')]:
    check(f'TC-36.3 refused: {words}', words in text(visitor.post(path_of(link), data={'step': 'details', **form})))
before = len(mailbox)
r = visitor.post(path_of(link), data={'step': 'details', 'username': 'jun', 'password': 'Kape-2026-jun',
                                      'confirm_password': 'Kape-2026-jun', 'role': 'admin'})   # a forged "role" field
check('TC-36.3 good details: a code goes to the invited address', 'Check your email' in text(r) and len(mailbox) == before + 1
      and mailbox.code_for('jun@example.com') is not None)
check('TC-36.3 no account exists before the code', user('jun') is None)
with app.app_context():
    codes = [c.code_hash for c in EmailCode.query]
check('TC-36.3 the code is stored only as a keyed hash (S14)', mailbox.code_for('jun@example.com') not in ''.join(codes)
      and all(len(c) == 64 for c in codes))
code = mailbox.code_for('jun@example.com')
wrong = '000000' if code != '000000' else '111111'
r = visitor.post(path_of(link), data={'step': 'code', 'code': wrong})
check('TC-36.3 a wrong code: "not right", 4 tries left', 'not right. 4 tries left' in text(r) and user('jun') is None)
r = visitor.post(path_of(link), data={'step': 'code', 'code': f'{code[:3]} {code[3:]}'}, follow_redirects=True)
jun = user('jun')
check('TC-36.3 the right code (typed with a space): the account exists and they are logged in',
      jun is not None and 'Welcome, jun' in text(r) and visitor.get('/sales/new').status_code == 200)
check('TC-36.3 ... as a CASHIER, the inviter\'s choice; the forged role field changed nothing (S12)', jun.role == 'cashier')
check('TC-36.3 ... with the invited email, confirmed', jun.email == 'jun@example.com' and jun.email_verified_at is not None)
check('TC-36.3 the link works only once', 'doesn\'t work any more' in text(app.test_client().get(path_of(link)))
      and app.test_client().get(path_of(link)).status_code == 404)

# ---- TC-36.4 who may invite whom; duplicates
check('TC-36.4 an admin allowed to invite can invite a cashier',
      'Invitation sent' in text(ana.post('/admin/users/invite', data={'email': 'mark@example.com', 'role': 'cashier'}, follow_redirects=True)))
r = owner.post('/admin/users/invite', data={'email': 'cara@example.com', 'role': 'cashier'}, follow_redirects=True)
check('TC-36.4 an address that already has an account is refused', 'already has an account' in text(r))
r = owner.post('/admin/users/invite', data={'email': 'MARK@example.com', 'role': 'cashier'}, follow_redirects=True)
check('TC-36.4 an address already invited: "use Send again" (capitals don\'t matter)', 'already been invited' in text(r))
r = owner.post('/admin/users/invite', data={'email': 'not-an-address', 'role': 'cashier'}, follow_redirects=True)
check('TC-36.4 not an email address: asked to type one', 'Type the person' in text(r))
r = owner.post('/admin/users/invite', data={'email': 'boss@example.com', 'role': 'admin'}, follow_redirects=True)
check('TC-36.4 the owner can invite an admin', 'Invitation sent' in text(r))
with app.app_context():
    mark_invitation = Invitation.query.filter_by(email='mark@example.com').first().id
    boss_invitation = Invitation.query.filter_by(email='boss@example.com').first().id
check('TC-36.4 an admin can\'t resend or cancel the owner\'s invitations (403)',
      ana.post(f'/admin/invitations/{boss_invitation}/resend').status_code == 403
      and ana.post(f'/admin/invitations/{boss_invitation}/cancel').status_code == 403)

# ---- TC-36.5 Send again: a new link, the old one stops working; Cancel
old_link = mailbox.link_for('mark@example.com')
r = ana.post(f'/admin/invitations/{mark_invitation}/resend', follow_redirects=True)
new_link = mailbox.link_for('mark@example.com')
check('TC-36.5 Send again: a new link is emailed', 'A new link was sent' in text(r) and new_link != old_link)
check('TC-36.5 ... the old link no longer works, the new one does',
      app.test_client().get(path_of(old_link)).status_code == 404 and app.test_client().get(path_of(new_link)).status_code == 200)
owner.post(f'/admin/invitations/{boss_invitation}/cancel')
check('TC-36.5 a cancelled invitation\'s link no longer works',
      app.test_client().get(path_of(mailbox.link_for('boss@example.com'))).status_code == 404)

# ---- TC-36.6 an invitation older than 48 hours no longer works
with app.app_context():
    db.session.get(Invitation, mark_invitation).expires_at = utc_now() - timedelta(minutes=1); db.session.commit()
check('TC-36.6 after 48 hours the link no longer works', app.test_client().get(path_of(new_link)).status_code == 404)
check('TC-36.6 the Users page says "expired" and offers Send again', 'expired' in text(ana.get('/admin/users')))

# ---- TC-36.7 email down: the invitation is kept and can be sent again
mailbox.down = True
r = owner.post('/admin/users/invite', data={'email': 'later@example.com', 'role': 'cashier'}, follow_redirects=True)
check('TC-36.7 no internet: "saved, but the email could not be sent", with what to do',
      'saved, but the email could not be sent' in text(r) and 'Send again' in text(r))
mailbox.down = False
app.config['MAIL'], mail_settings = {}, app.config['MAIL']
page = text(owner.get('/admin/users'))
check('TC-36.7 email not set up: the invite form says so instead', "isn't set up yet" in page.replace('&#39;', "'")
      and 'action="/admin/users/invite"' not in page)
app.config['MAIL'] = mail_settings

# ---- TC-36.8 the code rules (plan §2.4, S14): 5 tries, 10 minutes, one purpose, one a minute, 5 an hour
r = owner.post('/admin/users/invite', data={'email': 'tess@example.com', 'role': 'cashier'})
tess_link = path_of(mailbox.link_for('tess@example.com'))
tess = app.test_client()
tess.post(tess_link, data={'step': 'details', 'username': 'tess', 'password': 'Kape-2026-tess', 'confirm_password': 'Kape-2026-tess'})
code = mailbox.code_for('tess@example.com')
wrong = '000000' if code != '000000' else '111111'
answers = [text(tess.post(tess_link, data={'step': 'code', 'code': wrong})) for _ in range(5)]
check('TC-36.8 5 wrong tries count down 4, 3, 2, 1, then the code is cancelled',
      all(f'{n} tr' in a for n, a in zip([4, 3, 2, 1], answers)) and 'no longer works' in answers[4])
check('TC-36.8 ... and after that even the right code no longer works',
      'no longer works' in text(tess.post(tess_link, data={'step': 'code', 'code': code})) and user('tess') is None)
r = tess.post(tess_link, data={'step': 'code', 'again': '1'})
check('TC-36.8 a new code within a minute is refused', 'less than a minute ago' in text(r))
with app.app_context():
    for row in EmailCode.query.filter_by(email='tess@example.com'):
        row.created_at -= timedelta(minutes=2)
    db.session.commit()
r = tess.post(tess_link, data={'step': 'code', 'again': '1'})
check('TC-36.8 a minute later: a new code is sent', 'A new code was sent' in text(r))
first = mailbox.code_for('tess@example.com')
with app.app_context():
    for row in EmailCode.query.filter_by(email='tess@example.com'):
        row.created_at -= timedelta(minutes=2)
    db.session.commit()
tess.post(tess_link, data={'step': 'code', 'again': '1'})
second = mailbox.code_for('tess@example.com')
with app.app_context():
    open_codes = EmailCode.query.filter_by(email='tess@example.com', used_at=None).count()
check('TC-36.8 a newer code cancels the older one: only one code is open, and the old one is refused',
      open_codes == 1 and (first == second or 'not right' in text(tess.post(tess_link, data={'step': 'code', 'code': first}))))
with app.app_context():
    row = EmailCode.query.filter_by(email='tess@example.com').order_by(EmailCode.id.desc()).first()
    row.expires_at = utc_now() - timedelta(seconds=1); db.session.commit()
check('TC-36.8 after 10 minutes the code no longer works',
      'no longer works' in text(tess.post(tess_link, data={'step': 'code', 'code': second})))
with app.app_context():
    from store import users as user_store
    sent = []
    for _ in range(7):
        for row in EmailCode.query.filter_by(email='hour@example.com'):
            row.created_at -= timedelta(minutes=2)
        db.session.commit()
        sent.append(user_store.may_send_code('signup', 'hour@example.com'))
        if sent[-1] is None:
            user_store.new_code('signup', 'hour@example.com')
check('TC-36.8 at most 5 codes an hour to one address', sent[:5] == [None] * 5 and all('in the last hour' in s for s in sent[5:]))
with app.app_context():
    code = user_store.new_code('reset', 'purpose@example.com')
    row, _ = user_store.check_code('signup', 'purpose@example.com', code)
    right, _ = user_store.check_code('reset', 'purpose@example.com', code)
check('TC-36.8 a code works only for its own purpose (a reset code can\'t sign up)', row is None and right is not None)
with app.app_context():
    code = user_store.new_code('reset', 'once@example.com')
    first, _ = user_store.check_code('reset', 'once@example.com', code)
    again, _ = user_store.check_code('reset', 'once@example.com', code)
check('TC-36.8 a code works once', first is not None and again is None)

# ---- TC-36.9 two signups from one invitation at the same moment make one account
with app.app_context():
    from store import users as user_store
    invitation, token = user_store.create_invitation('twin@example.com', 'cashier', by=1)
    user_store.save_pending_signup(invitation, 'twin', g('Kape-2026-twin'))
    first = user_store.finish_signup(invitation)
    second = user_store.finish_signup(invitation)
    count = User.query.filter_by(email='twin@example.com').count()
check('TC-36.9 the invitation is used in one conditional step: the second attempt makes nothing',
      first is not None and second is None and count == 1)

finish('INVITATIONS')
