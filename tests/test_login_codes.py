"""A code at every login, trusted devices, backup codes, the authenticator app and demo mode (v0.28.0, F25, rules S13
and S14, DEC-005, DEC-017, DEC-030), test cases TC-38.x. This file does NOT use TEST_PLAIN_LOGIN: it tests the real
login. Mail goes to a fake mailbox (rule T3)."""
import base64
import io
import os
import re
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import timedelta
from helpers import check, finish, text, FakeMailbox
from werkzeug.security import generate_password_hash as g

from app import app, upgrade_database, MIGRATIONS_FOLDER
from models import db, User, TrustedDevice, BackupCode, utc_now
from alembic import command
import totp

app.config['CSRF_ENABLED'] = False
mailbox = FakeMailbox(app)

# ---- TC-38.1 the code calculation follows RFC 6238 (its published examples, last 6 digits)
rfc_key = base64.b32encode(b'12345678901234567890').decode()
check('TC-38.1 TOTP codes match RFC 6238 at 59, 1111111109, 1111111111, 1234567890 and 2000000000 seconds',
      [totp.code_at(rfc_key, t // 30) for t in (59, 1111111109, 1111111111, 1234567890, 2000000000)]
      == ['287082', '081804', '050471', '005924', '279037'])
check('TC-38.1 a code is accepted one step either side, not two', totp.matching_step(rfc_key, '287082', now=59 + 30) == 1
      and totp.matching_step(rfc_key, '287082', now=59 + 60) is None)

# ---- TC-38.2 migration 0006 and the starting method
with app.app_context():
    db.drop_all(); upgrade_database()
    config = app.extensions['migrate'].migrate.get_config(MIGRATIONS_FOLDER)
    command.downgrade(config, '0005'); db.session.remove()
    db.session.execute(db.text("INSERT INTO user (id, username, password_hash, role, is_active, must_change_password, "
                               "can_invite) VALUES (1, 'old', 'x', 'cashier', 1, 0, 0)")); db.session.commit()
    command.upgrade(config, 'head'); db.session.remove()
    tables = set(db.inspect(db.engine).get_table_names())
    check('TC-38.2 migration 0006 adds trusted_device and backup_code; existing accounts get emailed codes',
          {'trusted_device', 'backup_code'} <= tables and db.session.get(User, 1).second_step == 'email')
    command.downgrade(config, '0005'); db.session.remove()
    check('TC-38.2 undoing it removes them again', 'trusted_device' not in set(db.inspect(db.engine).get_table_names()))
    command.upgrade(config, 'head'); db.session.remove()

    db.drop_all(); upgrade_database()
    now = utc_now()
    db.session.add_all([
        User(username='olivia', password_hash=g('owner-pass-1'), role='owner', email='olivia@example.com', email_verified_at=now),
        User(username='adam', password_hash=g('admin-pass-1'), role='admin', email='adam@example.com', email_verified_at=now),
        User(username='cara', password_hash=g('cashier-pass-1'), role='cashier', email='cara@example.com', email_verified_at=now),
        User(username='carl', password_hash=g('cashier-pass-2'), role='cashier', email='carl@example.com', email_verified_at=now),
        User(username='old', password_hash=g('cashier-pass-3'), role='cashier'),                     # no email (before v0.27.0)
        User(username='demo', password_hash=g('cashier123'), role='cashier', email='demo@example.com')])   # a demo password
    db.session.commit()


def user(name):
    with app.app_context():
        return User.query.filter_by(username=name).first()


def password_step(client, name, password):
    return client.post('/login', data={'username': name, 'password': password})


def logged_in(client):
    return client.get('/sales/new').status_code == 200


def full_login(name, password, trust=False, client=None):
    client = client or app.test_client()
    password_step(client, name, password)
    client.post('/verify', data={'code': mailbox.code_for(user(name).email), 'trust': '1' if trust else ''})
    return client


def wait_a_minute(address):
    """Pretend time has passed for the sending limits (v0.27.0): earlier codes were sent long ago, so the one-a-minute
    and 5-an-hour limits don't stop this test's many logins. The limits themselves are tested in test_invitations.py."""
    with app.app_context():
        from models import EmailCode, LoginAttempt
        for row in EmailCode.query.filter_by(email=address):
            row.created_at -= timedelta(hours=2)
        LoginAttempt.query.delete()
        db.session.commit()


# ---- TC-38.3 the right password alone is not a login: a code is emailed and /verify asks for it (S13)
c = app.test_client()
r = password_step(c, 'cara', 'cashier-pass-1')
check('TC-38.3 the right password goes to /verify', r.status_code == 302 and r.headers['Location'].endswith('/verify'))
check('TC-38.3 ... and is not a login yet: other pages still go to the login page', not logged_in(c))
check('TC-38.3 a login code was emailed, saying what it is for', mailbox.code_for('cara@example.com')
      and 'log in to your' in mailbox.last_to('cara@example.com').get_content())
page = text(c.get('/verify'))
check('TC-38.3 /verify shows the address hidden (c•••@example.com) and the trust box for 30 days',
      'c•••@example.com' in page and 'cara@example.com' not in page and 'Trust this device for 30 days' in page)
r = c.post('/verify', data={'code': '000000' if mailbox.code_for('cara@example.com') != '000000' else '111111'})
check('TC-38.3 a wrong code is refused', 'not right' in text(r) and not logged_in(c))
c.post('/verify', data={'code': mailbox.code_for('cara@example.com')})
check('TC-38.3 the right code logs in', logged_in(c))
first_code, before = mailbox.code_for('cara@example.com'), len(mailbox)
c.post('/logout'); password_step(c, 'cara', 'cashier-pass-1')
check('TC-38.3 logging out and in again within a minute sends a new code (found in the browser check)',
      len(mailbox) == before + 1 and 'could not be sent' not in text(c.get('/verify')))
c.post('/verify', data={'code': mailbox.code_for('cara@example.com')})
check('TC-38.3 ... which logs in', logged_in(c))
check('TC-38.3 /verify with no password typed goes back to the login page',
      app.test_client().get('/verify').headers.get('Location', '').endswith('/login'))
c = app.test_client(); wait_a_minute('cara@example.com'); password_step(c, 'cara', 'cashier-pass-1')
with c.session_transaction() as s:
    pending = dict(s['pending_login']); pending['at'] -= 6 * 60; s['pending_login'] = pending
r = c.post('/verify', data={'code': mailbox.code_for('cara@example.com')})
check('TC-38.3 after 5 minutes the code page no longer works: log in again', r.headers.get('Location', '').endswith('/login')
      and not logged_in(c))

# ---- TC-38.4 limits: 5 wrong codes, then wait; a new code once a minute
c = app.test_client(); wait_a_minute('carl@example.com'); password_step(c, 'carl', 'cashier-pass-2')
statuses = [c.post('/verify', data={'code': f'99999{i}'}).status_code for i in range(6)]
check('TC-38.4 5 wrong codes, then "too many" (429)', statuses[-1] == 429 and 'Too many' in text(c.post('/verify', data={'code': '1'})))
r = c.post('/verify/resend', follow_redirects=True)
check('TC-38.4 a new code within a minute is refused', 'less than a minute ago' in text(r))
with app.app_context():   # the 5-minute wait is over (as the login tests do, test_security.py)
    from models import LoginAttempt
    LoginAttempt.query.delete(); db.session.commit()

# ---- TC-38.5 trusting this device (DEC-005)
cara = full_login('cara', 'cashier-pass-1', trust=True)
cookie = cara.get_cookie('trusted')
with app.app_context():
    rows = TrustedDevice.query.filter_by(user_id=user('cara').id).all()
check('TC-38.5 "Trust this device" stores only a keyed hash of the cookie\'s token',
      len(rows) == 1 and cookie is not None and cookie.value not in rows[0].token_hash and len(rows[0].token_hash) == 64)
check('TC-38.5 the cookie is HttpOnly, SameSite=Lax, for 30 days (a cashier)',
      cookie.http_only and cookie.same_site == 'Lax' and timedelta(days=29) < rows[0].expires_at - rows[0].created_at <= timedelta(days=30))
cara.post('/logout')
before = len(mailbox)
r = password_step(cara, 'cara', 'cashier-pass-1')
check('TC-38.5 on that browser the password alone logs in, no code sent', r.headers['Location'].endswith('/products')
      and logged_in(cara) and len(mailbox) == before)
cara.post('/logout')
r = password_step(cara, 'cara', 'wrong-password')
check('TC-38.5 trust skips only the code, never the password', not logged_in(cara))
wait_a_minute('carl@example.com')
r = password_step(cara, 'carl', 'cashier-pass-2')
check('TC-38.5 another cashier on the same browser still needs a code', r.headers['Location'].endswith('/verify'))
cara.post('/verify', data={'code': mailbox.code_for('carl@example.com'), 'trust': '1'})
cara.post('/logout')
check('TC-38.5 ... and can trust it too: the cookie then holds both, each for its own user',
      len(cara.get_cookie('trusted').value.split('.')) == 2
      and password_step(cara, 'cara', 'cashier-pass-1').headers['Location'].endswith('/products'))
cara.post('/logout')
thief = app.test_client(); thief.set_cookie('trusted', cookie.value); wait_a_minute('carl@example.com')
check('TC-38.5 cara\'s trust cookie copied to another browser doesn\'t help carl',
      password_step(thief, 'carl', 'cashier-pass-2').headers['Location'].endswith('/verify'))
forged = app.test_client(); forged.set_cookie('trusted', 'x' * 43); wait_a_minute('cara@example.com')
check('TC-38.5 a made-up token is ignored', password_step(forged, 'cara', 'cashier-pass-1').headers['Location'].endswith('/verify'))
adam = full_login('adam', 'admin-pass-1', trust=True)
with app.app_context():
    row = TrustedDevice.query.filter_by(user_id=user('adam').id).first()
check('TC-38.5 an admin\'s trust lasts 7 days', row.expires_at - row.created_at <= timedelta(days=7))


def trusted(client, name, password):
    client.post('/logout')
    wait_a_minute(user(name).email)
    ok = password_step(client, name, password).headers['Location'].endswith('/products')
    client.post('/logout')
    return ok


# ---- TC-38.6 every way trust ends (S13)
check('TC-38.6 (before) cara\'s browser is trusted', trusted(cara, 'cara', 'cashier-pass-1'))
c = full_login('cara', 'cashier-pass-1', client=cara)   # trusted: password alone
with app.app_context():
    device = TrustedDevice.query.filter_by(user_id=user('cara').id).first().id
page = text(c.get('/profile'))
check('TC-38.6 Profile lists the trusted device with Remove and Log out everywhere',
      'Trusted devices' in page and 'Remove' in page and 'Log out everywhere' in page)
check('TC-38.6 another person\'s device can\'t be removed (404)', adam.post(f'/profile/devices/{device}/remove').status_code == 404)
c.post(f'/profile/devices/{device}/remove')
check('TC-38.6 Remove: the next login asks for a code again', not trusted(cara, 'cara', 'cashier-pass-1'))


def trust_again(name, password):
    client = app.test_client(); wait_a_minute(user(name).email)
    return full_login(name, password, trust=True, client=client)


c = trust_again('cara', 'cashier-pass-1'); till = trust_again('cara', 'cashier-pass-1')
c.post('/profile/logout-everywhere')
check('TC-38.6 Log out everywhere: every login ends (another till too) and no device stays trusted',
      not logged_in(c) and not logged_in(till) and not trusted(c, 'cara', 'cashier-pass-1'))
c = trust_again('cara', 'cashier-pass-1')
c.post('/profile/password', data={'current_password': 'cashier-pass-1', 'new_password': 'Kape-2026-cara',
                                  'confirm_password': 'Kape-2026-cara'})
check('TC-38.6 a password change ends trust', not trusted(c, 'cara', 'Kape-2026-cara'))
owner = trust_again('olivia', 'owner-pass-1')
c = trust_again('cara', 'Kape-2026-cara')
owner.post(f'/admin/users/{user("cara").id}/active', data={'active': '0'})
owner.post(f'/admin/users/{user("cara").id}/active', data={'active': '1'})
check('TC-38.6 switching the account off ends trust', not trusted(c, 'cara', 'Kape-2026-cara'))
c = trust_again('carl', 'cashier-pass-2')
owner.post(f'/admin/users/{user("carl").id}/role', data={'role': 'admin'})
check('TC-38.6 a role change ends trust (an admin gets 7 days, not 30)', not trusted(c, 'carl', 'cashier-pass-2'))
owner.post(f'/admin/users/{user("carl").id}/role', data={'role': 'cashier'})
c = trust_again('carl', 'cashier-pass-2')
with app.app_context():
    for row in TrustedDevice.query: row.expires_at = utc_now() - timedelta(minutes=1)
    db.session.commit()
check('TC-38.6 after its days, trust ends by itself', not trusted(c, 'carl', 'cashier-pass-2'))

# ---- TC-38.7 backup codes (plan §2.6)
def shown_codes(html):
    """The backup codes in the list on the page (page words like "card-body" have the same shape, so not anywhere)."""
    return re.findall(r'py-1">([a-z2-9]{4}-[a-z2-9]{4})</span>', html)


c = trust_again('carl', 'cashier-pass-2')
check('TC-38.7 making backup codes needs the password',
      'Current password is wrong' in text(c.post('/profile/backup-codes', data={'current_password': 'x'}, follow_redirects=True)))
r = c.post('/profile/backup-codes', data={'current_password': 'cashier-pass-2'})
codes = shown_codes(text(r))
check('TC-38.7 10 codes like k7mp-29xa, shown on a page the browser must not keep (no-store)',
      len(set(codes)) == 10 and r.headers.get('Cache-Control') == 'no-store')
with app.app_context():
    stored = [b.code_hash for b in BackupCode.query.filter_by(user_id=user('carl').id)]
check('TC-38.7 only keyed hashes are stored', len(stored) == 10 and not any(code.replace('-', '') in ''.join(stored) for code in codes))
c.post('/logout'); wait_a_minute('carl@example.com')
c2 = app.test_client(); password_step(c2, 'carl', 'cashier-pass-2'); c2.post('/verify', data={'code': codes[0].upper().replace('-', ' ')})
check('TC-38.7 a backup code logs in instead of the emailed code (capitals and spaces are fine)', logged_in(c2))
c3 = app.test_client(); wait_a_minute('carl@example.com'); password_step(c3, 'carl', 'cashier-pass-2'); c3.post('/verify', data={'code': codes[0]})
check('TC-38.7 the same backup code works only once', not logged_in(c3))
check('TC-38.7 Profile says 9 are left', '<strong>9</strong> unused backup codes' in text(c2.get('/profile')))
new_codes = shown_codes(text(c2.post('/profile/backup-codes', data={'current_password': 'cashier-pass-2'})))
c4 = app.test_client(); wait_a_minute('carl@example.com'); password_step(c4, 'carl', 'cashier-pass-2'); c4.post('/verify', data={'code': codes[1]})
check('TC-38.7 making new codes cancels the old ones', not logged_in(c4) and len(new_codes) == 10)

# ---- TC-38.8 offline: no email can be sent, a backup code still logs in (rule D2)
mailbox.down = True
c = app.test_client(); wait_a_minute('carl@example.com')
r = password_step(c, 'carl', 'cashier-pass-2')
page = text(c.get('/verify'))
check('TC-38.8 no internet: /verify says the code couldn\'t be sent and offers a backup code',
      'could not be sent' in page and 'backup code' in page)
c.post('/verify', data={'code': new_codes[0]})
check('TC-38.8 ... and the backup code logs in with no internet', logged_in(c))
mailbox.down = False

# ---- TC-38.9 the authenticator app (DEC-017)
check('TC-38.9 setting it up needs the password',
      'Current password is wrong' in text(c.post('/profile/authenticator', data={'current_password': 'x'}, follow_redirects=True)))
r = c.post('/profile/authenticator', data={'current_password': 'cashier-pass-2'})
page = text(r)
key = re.search(r'user-select-all">([A-Z2-7 ]+)<', page).group(1).replace(' ', '')
check('TC-38.9 the page shows a QR code drawn in the page (data: SVG) and the key as text, not kept (no-store)',
      'src="data:image/svg+xml' in page and len(key) == 32 and r.headers.get('Cache-Control') == 'no-store')
with app.app_context():
    pending = user('carl').totp_pending_encrypted
check('TC-38.9 the key is stored encrypted, never as text', pending and key not in pending)
check('TC-38.9 nothing changes yet', user('carl').second_step == 'email')
r = c.post('/profile/authenticator/confirm', data={'code': '000000' if totp.code_at(key, totp.current_step()) != '000000' else '111111'})
check('TC-38.9 a wrong first code: not switched (a mis-scan can\'t lock anyone out)', 'not right' in text(r) and user('carl').second_step == 'email')
before = len(mailbox)
r = c.post('/profile/authenticator/confirm', data={'code': totp.code_at(key, totp.current_step())})
app_backup = shown_codes(text(r))
check('TC-38.9 the right code switches to the app and shows new backup codes',
      user('carl').second_step == 'app' and 'authenticator app is set up' in text(r) and len(app_backup) == 10
      and r.headers.get('Cache-Control') == 'no-store')
check('TC-38.9 ... and an email says the sign-in method changed (S13)',
      len(mailbox) > before and mailbox.last_to('carl@example.com')['Subject'] == 'Your sign-in method changed')
with app.app_context():
    stored = user('carl').totp_key_encrypted
check('TC-38.9 the key is kept encrypted (Fernet), and the encryption key is its own file in instance/',
      stored and key not in stored and os.path.exists(os.path.join('instance', 'totp_key.txt')))
c.post('/logout'); before = len(mailbox)
c = app.test_client(); password_step(c, 'carl', 'cashier-pass-2')
check('TC-38.9 at login no email is sent; /verify asks for the app\'s code',
      len(mailbox) == before and 'authenticator app' in text(c.get('/verify')))
used_step = user('carl').totp_last_step
c.post('/verify', data={'code': totp.code_at(key, used_step)})
check('TC-38.9 the code of a step already used (at set-up) is refused: no replay (S14)', not logged_in(c))
next_code = totp.code_at(key, used_step + 1)
c.post('/verify', data={'code': next_code})
check('TC-38.9 the next step\'s code logs in', logged_in(c))
replay = app.test_client(); password_step(replay, 'carl', 'cashier-pass-2'); replay.post('/verify', data={'code': next_code})
check('TC-38.9 the same code again, in another browser, is refused', not logged_in(replay))
r = c.post('/profile/authenticator/off', data={'current_password': 'cashier-pass-2', 'code': '123'}, follow_redirects=True)
check('TC-38.9 turning it off needs a current code (or a backup code)', 'not right' in text(r) and user('carl').second_step == 'app')
before = len(mailbox)
r = c.post('/profile/authenticator/off', data={'current_password': 'cashier-pass-2', 'code': app_backup[0]},
           follow_redirects=True)
check('TC-38.9 with the password and a backup code (a lost phone): back to email, key deleted, and an email about it',
      user('carl').second_step == 'email' and user('carl').totp_key_encrypted is None and len(mailbox) == before + 1)

# ---- TC-38.10 an admin resets a cashier's app to email (lost phone); never the owner's
with app.app_context():
    carl_row = db.session.get(User, user('carl').id)
    carl_row.second_step, carl_row.totp_key_encrypted = 'app', totp.lock(totp.new_key()); db.session.commit()
adam = trust_again('adam', 'admin-pass-1')
check('TC-38.10 Users offers "Login code by email" for the cashier using an app', 'Login code by email' in text(adam.get('/admin/users')))
before = len(mailbox)
adam.post(f'/admin/users/{user("carl").id}/reset-second-step')
check('TC-38.10 the admin resets it: email codes again, and carl is emailed', user('carl').second_step == 'email' and len(mailbox) == before + 1)
with app.app_context():
    owner_row = db.session.get(User, user('olivia').id); owner_row.second_step = 'app'; db.session.commit()
check('TC-38.10 nobody can reset the owner\'s this way (403)',
      adam.post(f'/admin/users/{user("olivia").id}/reset-second-step').status_code == 403
      and owner.post(f'/admin/users/{user("olivia").id}/reset-second-step').status_code == 403)
with app.app_context():
    owner_row = db.session.get(User, user('olivia').id); owner_row.second_step = 'email'; db.session.commit()

# ---- TC-38.11 an account with no email (owner's decision 1): the owner adds it, the next login confirms it
r = password_step(app.test_client(), 'old', 'cashier-pass-3')
check('TC-38.11 no email yet: the login says to ask the owner (403)', r.status_code == 403 and 'no email yet' in text(r))
check('TC-38.11 a cashier can\'t add one for someone else (403)',
      full_login('cara', 'Kape-2026-cara').post(f'/admin/users/{user("old").id}/email', data={'email': 'o@example.com'}).status_code == 403)
owner.post(f'/admin/users/{user("old").id}/email', data={'email': 'Old@Example.com'})
check('TC-38.11 the owner adds it on Users: saved, not yet confirmed', user('old').email == 'old@example.com' and user('old').email_verified_at is None)
c = full_login('old', 'cashier-pass-3')
check('TC-38.11 the next login sends the code there; typing it logs in and confirms the address',
      logged_in(c) and user('old').email_verified_at is not None)

# ---- TC-38.12 demo passwords and demo mode (rule P3)
r = password_step(app.test_client(), 'demo', 'cashier123')
check('TC-38.12 outside demo mode a published demo password is refused, with what to do (403)',
      r.status_code == 403 and 'only works in the demo' in text(r))
app.config['DEMO_MODE'] = True
before, shown = len(mailbox), io.StringIO()
with redirect_stdout(shown):
    c = app.test_client(); password_step(c, 'demo', 'cashier123')
code = re.search(r'Your code is (\d{3}) (\d{3})', shown.getvalue())
check('TC-38.12 in demo mode the demo password works and the code is printed in the server window, not emailed',
      code is not None and len(mailbox) == before)
c.post('/verify', data={'code': code.group(1) + code.group(2)})
check('TC-38.12 ... and that code logs in', logged_in(c))
app.config['DEMO_MODE'] = False
with open(os.path.join('instance', 'config.toml'), 'w', encoding='utf-8') as f:
    f.write('[mail]\nhost = "smtp.example.com"\nfrom_address = "shop@example.com"\n')
r = subprocess.run([sys.executable, '-c', 'import app'], capture_output=True, text=True, env=dict(os.environ, DEMO_MODE='1'))
check('TC-38.12 the app refuses to start in demo mode when real mail settings exist', r.returncode == 1 and 'DEMO_MODE=1 is for the demo only' in r.stderr)
os.remove(os.path.join('instance', 'config.toml'))

# ---- TC-38.13 the test-only password login can't be switched on outside tests/
with open('planted.py', 'w', encoding='utf-8') as f:
    f.write("from app import app\napp.config['TEST_PLAIN_LOGIN'] = True\n")
r = subprocess.run([sys.executable, os.path.join('tests', 'check_contract.py')], capture_output=True, text=True)
os.remove('planted.py')
check('TC-38.13 the contract check fails if a file outside tests/ turns on the password-only login',
      r.returncode == 1 and 'TEST_PLAIN_LOGIN only switched on in tests (planted.py line 2)' in r.stdout)

finish('LOGIN CODES')
