"""Sign in with Google, linking it from Profile, and joining with it (v0.29.0, F26, DEC-031), test cases TC-39.x.

Never talks to Google (rule T3): the test makes its own RSA key, signs ID tokens with it, and replaces only the two
network calls (exchanging the code, fetching Google's keys). Every check on the answer (state, signature, issuer,
audience, expiry, nonce, verified email) runs for real. Like test_login_codes.py, it uses the real login: the
emailed code still follows Google (plan D-5)."""
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import timedelta
from urllib.parse import urlparse, parse_qs
from helpers import check, finish, text, FakeMailbox
from werkzeug.security import generate_password_hash as g
from joserfc import jwt
from joserfc.jwk import RSAKey, KeySet

from app import app, upgrade_database, MIGRATIONS_FOLDER
from models import db, User, AuditEntry, utc_now
from alembic import command
import google_signin

app.config['CSRF_ENABLED'] = False
mailbox = FakeMailbox(app)
CLIENT_ID = 'test-client.apps.googleusercontent.com'

# ---------- A pretend Google: our own key, and the two network calls replaced ----------
KEY = RSAKey.generate_key(2048, parameters={'kid': 'test-key'})
OTHER_KEY = RSAKey.generate_key(2048, parameters={'kid': 'test-key'})   # same name, wrong key: a forgery
google = {'id_token': '', 'seen': {}, 'down': False}


def fake_exchange(values, code, verifier):
    if google['down']:
        import requests
        raise requests.ConnectionError('no internet (fake)')
    google['seen'] = {'code': code, 'verifier': verifier, 'client_id': values['client_id']}
    return {'access_token': 'x', 'id_token': google['id_token']}


google_signin.exchange_code = fake_exchange
google_signin.fetch_keys = lambda: KeySet([KEY]).as_dict(private=False)


def id_token(trip_nonce, key=KEY, **changes):
    """An ID token as Google would send it for the trip with this nonce; changes alter or remove (None) claims."""
    now = int(time.time())
    claims = {'iss': 'https://accounts.google.com', 'aud': CLIENT_ID, 'sub': '1001', 'email': 'cara@example.com',
              'email_verified': True, 'iat': now, 'exp': now + 3600, 'nonce': trip_nonce}
    claims.update(changes)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode({'alg': 'RS256', 'kid': 'test-key'}, claims, key)


def go_to_google(client, path='/login/google'):
    """Start the trip; return (status, query of Google's address)."""
    r = client.get(path) if isinstance(path, str) else client.post(path[0], data=path[1])   # (page, form) = a POST
    location = r.headers.get('Location', '')
    return r.status_code, parse_qs(urlparse(location).query), location


def back_from_google(client, query, key=KEY, state=None, **changes):
    """Google sends the browser back: an ID token for this trip's nonce, and the state (or another one)."""
    google['id_token'] = id_token(query['nonce'][0], key=key, **changes)
    return client.get('/auth/google/callback?code=one-time-code&state=' + (state or query['state'][0]))


def user(name):
    with app.app_context():
        return User.query.filter_by(username=name).first()


def logged_in(client):
    return client.get('/sales/new').status_code == 200


def message(response_or_client):
    """The page after a redirect, as text (follows the redirect)."""
    return text(response_or_client)


# ---- TC-39.1 migration 0007
with app.app_context():
    db.drop_all(); upgrade_database()
    config = app.extensions['migrate'].migrate.get_config(MIGRATIONS_FOLDER)
    command.downgrade(config, '0006'); db.session.remove()
    gone = 'google_sub' not in {c['name'] for c in db.inspect(db.engine).get_columns('user')}
    command.upgrade(config, 'head'); db.session.remove()
    check('TC-39.1 migration 0007 adds user.google_sub (unique) and invitation.pending_google_sub; undo removes them',
          gone and 'google_sub' in {c['name'] for c in db.inspect(db.engine).get_columns('user')}
          and 'pending_google_sub' in {c['name'] for c in db.inspect(db.engine).get_columns('invitation')})
    db.drop_all(); upgrade_database()
    now = utc_now()
    db.session.add_all([
        User(username='olivia', password_hash=g('owner-pass-1'), role='owner', email='olivia@example.com', email_verified_at=now),
        User(username='cara', password_hash=g('cashier-pass-1'), role='cashier', email='cara@example.com', email_verified_at=now),
        User(username='carl', password_hash=g('cashier-pass-2'), role='cashier', email='carl@example.com'),   # not confirmed
        User(username='lino', password_hash=g('cashier-pass-3'), role='cashier', email='lino@example.com',
             email_verified_at=now, google_sub='2002')])   # already linked
    db.session.commit()

# ---- TC-39.2 not set up / not on an address Google accepts
app.config['GOOGLE'] = {}
r = app.test_client().get('/login/google', follow_redirects=True)
check('TC-39.2 not set up: no Google button, and /login/google says so',
      'Sign in with Google' not in text(app.test_client().get('/login')) and 'not set up' in text(r))
app.config['GOOGLE'] = {'client_id': CLIENT_ID, 'client_secret': 'test-secret'}
LAN = 'http://127.0.0.1:5000'
page = text(app.test_client().get('/login', base_url=LAN))
check('TC-39.2 on 127.0.0.1 the login page says where it works (http://localhost:5000) instead of a button that fails',
      'works at' in page and 'http://localhost:5000' in page and 'href="/login/google' not in page)
r = app.test_client().get('/login/google', base_url=LAN)
check('TC-39.2 ... and /login/google there goes back to the login page', r.headers['Location'].endswith('/login'))

# ---- TC-39.3 the trip starts correctly (localhost)
c = app.test_client()
check('TC-39.3 on localhost the login page shows "Sign in with Google"', 'Sign in with Google' in text(c.get('/login')))
status, query, location = go_to_google(c)
challenge = query.get('code_challenge', [''])[0]
check('TC-39.3 the browser goes to Google\'s sign-in address', status == 302 and location.startswith(google_signin.AUTHORIZE_URL))
check('TC-39.3 asking only for openid, email and profile (no access to Gmail)', query.get('scope') == ['openid email profile']
      and query.get('response_type') == ['code'] and query.get('client_id') == [CLIENT_ID])
check('TC-39.3 with a random state and nonce, and a PKCE challenge (S256)',
      len(query['state'][0]) >= 40 and len(query['nonce'][0]) >= 40 and query.get('code_challenge_method') == ['S256']
      and len(challenge) == 43)
check('TC-39.3 returning to /auth/google/callback on this address',
      query.get('redirect_uri') == ['http://localhost/auth/google/callback'])
back_from_google(c, query, sub='9999')
verifier = google['seen'].get('verifier', '')
check('TC-39.3 the code is exchanged with the PKCE secret that matches the challenge',
      base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode() == challenge)

# ---- TC-39.4 Google's answer is checked, not trusted
cases = [({'state': 'someone-elses-state'}, 'didn\'t start here'),
         ({'key': OTHER_KEY}, 'could not be checked'),
         ({'aud': 'another-shop.apps.googleusercontent.com'}, 'could not be checked'),
         ({'iss': 'https://evil.example.com'}, 'could not be checked'),
         ({'exp': int(time.time()) - 600, 'iat': int(time.time()) - 4200}, 'too old'),
         ({'nonce': 'not-this-trip'}, 'could not be checked'),
         ({'sub': None}, 'could not be checked'),
         ({'email_verified': False}, 'not verified')]
for changes, words in cases:
    c = app.test_client()
    _, query, _ = go_to_google(c)
    r = back_from_google(c, query, **changes)
    page = message(c.get(r.headers.get('Location', '/login')))
    check(f'TC-39.4 refused ({", ".join(changes)}): "{words}", not logged in',
          words in page.replace('&#39;', "'") and not logged_in(c))
c = app.test_client()
_, query, _ = go_to_google(c)
back_from_google(c, query, sub='2002', email='lino@example.com')
r = c.get('/auth/google/callback?code=x&state=' + query['state'][0])
check('TC-39.4 the same answer can\'t be used twice (the trip is used up)',
      'didn\'t start here' in message(c.get(r.headers['Location'])).replace('&#39;', "'"))
r = app.test_client().get('/auth/google/callback?code=x&state=abc')
check('TC-39.4 a browser that never started a trip is refused', r.headers['Location'].endswith('/login'))
c = app.test_client(); _, query, _ = go_to_google(c)
r = c.get('/auth/google/callback?error=access_denied&state=' + query['state'][0])
check('TC-39.4 "Cancel" on Google\'s page: a plain "cancelled"', 'cancelled' in message(c.get(r.headers['Location'])))
c = app.test_client(); _, query, _ = go_to_google(c)
with c.session_transaction() as s:
    trip = dict(s['google']); trip['at'] -= 11 * 60; s['google'] = trip
r = back_from_google(c, query, sub='2002', email='lino@example.com')
check('TC-39.4 a trip older than 10 minutes is refused', not logged_in(c))
google['down'] = True
c = app.test_client(); _, query, _ = go_to_google(c)
r = back_from_google(c, query)
check('TC-39.4 no internet: "Could not reach Google", with the password as the way in (D2)',
      'Could not reach Google' in message(c.get(r.headers['Location'])))
google['down'] = False

# ---- TC-39.5 logging in with Google: by Google's id, then the code (plan D-5)
c = app.test_client(); _, query, _ = go_to_google(c)
r = back_from_google(c, query, sub='7777', email='nobody@example.com')
check('TC-39.5 a Google account linked to nobody: told how to link it or get an invitation',
      'isn\'t linked' in message(c.get(r.headers['Location'])).replace('&#39;', "'") and not logged_in(c))
c = app.test_client(); _, query, _ = go_to_google(c)
r = back_from_google(c, query, sub='2002', email='lino@example.com')
check('TC-39.5 a linked Google account goes to /verify: the code is still asked', r.headers['Location'].endswith('/verify')
      and not logged_in(c) and mailbox.code_for('lino@example.com'))
c.post('/verify', data={'code': mailbox.code_for('lino@example.com'), 'trust': '1'})
check('TC-39.5 the code logs in', logged_in(c))
c.post('/logout'); _, query, _ = go_to_google(c)
r = back_from_google(c, query, sub='2002', email='lino@example.com')
check('TC-39.5 on a trusted browser Google alone logs in', r.headers['Location'].endswith('/products') and logged_in(c))
c.post('/logout')
c2 = app.test_client(); _, query, _ = go_to_google(c2)
r = back_from_google(c2, query, sub='2002', email='somebody-else@example.com')
check('TC-39.5 accounts are found by Google\'s id, not the email (a changed Google address still opens lino\'s)',
      r.headers['Location'].endswith('/verify'))
with app.app_context():
    db.session.get(User, user('lino').id).is_active = False; db.session.commit()
c = app.test_client(); _, query, _ = go_to_google(c)
r = back_from_google(c, query, sub='2002', email='lino@example.com')
check('TC-39.5 a switched-off account is refused', 'switched off' in message(c.get(r.headers['Location'])) and not logged_in(c))
with app.app_context():
    db.session.get(User, user('lino').id).is_active = True; db.session.commit()


def full_login(name, password):
    client = app.test_client()
    client.post('/login', data={'username': name, 'password': password})
    client.post('/verify', data={'code': mailbox.code_for(user(name).email)})
    return client


def wait_a_minute():
    with app.app_context():
        from models import EmailCode, LoginAttempt
        for row in EmailCode.query:
            row.created_at -= timedelta(hours=2)
        LoginAttempt.query.delete(); db.session.commit()


# ---- TC-39.6 linking Google from Profile: password + a fresh code, the same email (owner's decision 2)
cara = full_login('cara', 'cashier-pass-1')
check('TC-39.6 Profile offers linking Google for the account\'s confirmed email',
      'Link the Google account for <strong>cara@example.com' in text(cara.get('/profile')))
r = cara.post('/profile/google', data={'current_password': 'cashier-pass-1', 'code': '123456'}, follow_redirects=True)
check('TC-39.6 without the right code: refused, not sent to Google', 'code is not right' in text(r))
r = cara.post('/profile/google', data={'current_password': 'wrong', 'code': '123456'}, follow_redirects=True)
check('TC-39.6 without the right password: refused', 'Current password is wrong' in text(r))
wait_a_minute()
cara.post('/profile/google/code')
check('TC-39.6 "Send me a code" emails a code for linking', 'link your Google account' in mailbox.last_to('cara@example.com').get_content())
status, query, location = go_to_google(cara, ('/profile/google', {'current_password': 'cashier-pass-1',
                                                                  'code': mailbox.code_for('cara@example.com')}))
check('TC-39.6 password + code: on to Google', location.startswith(google_signin.AUTHORIZE_URL))
r = back_from_google(cara, query, sub='3003', email='cara.other@gmail.com')
check('TC-39.6 a Google account with another email is refused, saying which addresses differ',
      'cara.other@gmail.com' in message(cara.get(r.headers['Location'])) and user('cara').google_sub is None)
wait_a_minute(); cara.post('/profile/google/code')
_, query, _ = go_to_google(cara, ('/profile/google', {'current_password': 'cashier-pass-1', 'code': mailbox.code_for('cara@example.com')}))
r = back_from_google(cara, query, sub='2002', email='cara@example.com')
check('TC-39.6 a Google account already linked to another account is refused',
      'already linked to another account' in message(cara.get(r.headers['Location'])) and user('cara').google_sub is None)
wait_a_minute(); cara.post('/profile/google/code')
_, query, _ = go_to_google(cara, ('/profile/google', {'current_password': 'cashier-pass-1', 'code': mailbox.code_for('cara@example.com')}))
before = len(mailbox)
r = back_from_google(cara, query, sub='3003', email='Cara@Example.com')
check('TC-39.6 the same email (capitals don\'t matter): linked by Google\'s id',
      'Google is linked' in message(cara.get(r.headers['Location'])) and user('cara').google_sub == '3003')
check('TC-39.6 ... cara is emailed about it, and the audit log has it',
      len(mailbox) == before + 1 and 'logged in to with Google' in mailbox.last_to('cara@example.com').get_content())
with app.app_context():
    check('TC-39.6 (audit)', AuditEntry.query.filter_by(action='user.google-link').count() == 1)
carl = full_login('carl', 'cashier-pass-2')
with app.app_context():   # the login code confirmed carl's address (v0.28.0); make it unconfirmed again for this case
    db.session.get(User, user('carl').id).email_verified_at = None; db.session.commit()
page = text(carl.get('/profile'))
check('TC-39.7 an unconfirmed email can\'t be linked: the card says to confirm it first',
      'Confirm your email above first' in page)
check('TC-39.7 ... and posting anyway is refused', 'Confirm your email first' in
      text(carl.post('/profile/google', data={'current_password': 'cashier-pass-2', 'code': '1'}, follow_redirects=True)))
r = cara.post('/profile/google/unlink', data={'current_password': 'wrong'}, follow_redirects=True)
check('TC-39.7 unlinking needs the password', 'Current password is wrong' in text(r) and user('cara').google_sub == '3003')
r = cara.post('/profile/google/unlink', data={'current_password': 'cashier-pass-1'}, follow_redirects=True)
check('TC-39.7 with it: unlinked, and Google no longer opens the account',
      user('cara').google_sub is None and 'no longer linked' in text(r))

# ---- TC-39.8 joining with Google from an invitation (DEC-003)
owner = full_login('olivia', 'owner-pass-1')
owner.post('/admin/users/invite', data={'email': 'jun@example.com', 'role': 'cashier'})
link = urlparse(mailbox.link_for('jun@example.com')).path
jun = app.test_client()
check('TC-39.8 the invitation page offers "Continue with Google"', 'Continue with Google' in text(jun.get(link)))
r = jun.post(link, data={'step': 'google', 'username': 'j u n'})
check('TC-39.8 the username is checked first', 'no spaces' in text(r))
status, query, location = go_to_google(jun, (link, {'step': 'google', 'username': 'jun', 'role': 'admin'}))
check('TC-39.8 a good username: on to Google', location.startswith(google_signin.AUTHORIZE_URL))
r = back_from_google(jun, query, sub='4004', email='jun.personal@gmail.com')
check('TC-39.8 a Google account for another address is refused', 'the invitation is for jun@example.com'
      in message(jun.get(r.headers['Location'])) and user('jun') is None)
_, query, _ = go_to_google(jun, (link, {'step': 'google', 'username': 'jun'}))
r = back_from_google(jun, query, sub='4004', email='jun@example.com')
page = message(jun.get(r.headers['Location']))
check('TC-39.8 the invited address: the code step follows (DEC-003), no account yet',
      'Check your email' in page and mailbox.code_for('jun@example.com') and user('jun') is None)
jun.post(link, data={'step': 'code', 'code': mailbox.code_for('jun@example.com')})
made = user('jun')
check('TC-39.8 the code makes the account: a cashier (the forged role changed nothing), Google linked, logged in',
      made is not None and made.role == 'cashier' and made.google_sub == '4004' and logged_in(jun))
check('TC-39.8 nobody knows its password (a random one), so a password login fails',
      app.test_client().post('/login', data={'username': 'jun', 'password': 'cashier-pass-1'}).status_code == 200)
jun.post('/logout'); _, query, _ = go_to_google(jun)
r = back_from_google(jun, query, sub='4004', email='jun@example.com')
check('TC-39.8 Google then logs jun in (via the code)', r.headers['Location'].endswith('/verify'))

# ---- TC-39.9 settings: setup_shop.py and the environment
os.makedirs('instance', exist_ok=True)


def setup(google_answers):
    answers = {'network': {'other_devices': False, 'port': 5000}, 'shop': {'name': 'Sample Café'},
               'admin': {'username': 'olivia', 'password': 'owner-pass-1', 'email': 'olivia@example.com'}}
    if google_answers is not None:
        answers['google'] = google_answers
    with open('answers.json', 'w', encoding='utf-8') as f:
        json.dump(answers, f)
    return subprocess.run([sys.executable, 'setup_shop.py', '--answers', 'answers.json'], capture_output=True,
                          text=True, encoding='utf-8', errors='replace')


r = setup({'client_id': 'not-a-google-id', 'client_secret': 's'})
check('TC-39.9 setup refuses a client ID that isn\'t Google\'s', r.returncode == 1 and 'apps.googleusercontent.com' in r.stdout)
r = setup({'client_id': CLIENT_ID, 'client_secret': 'the-secret-1'})
config_text = open(os.path.join('instance', 'config.toml'), encoding='utf-8').read()
check('TC-39.9 good answers: [google] is written, and setup says which redirect address to register in Google Cloud',
      r.returncode == 0 and '[google]' in config_text and 'http://localhost:5000/auth/google/callback' in r.stdout
      and 'the-secret-1' not in r.stdout)
r = setup(None)
check('TC-39.9 setup again without Google answers keeps them', '[google]' in open(os.path.join('instance', 'config.toml'), encoding='utf-8').read())
read = 'import logging;logging.disable(50);from app import app;print(app.config["GOOGLE"].get("client_id"))'
r = subprocess.run([sys.executable, '-c', read], capture_output=True, text=True,
                   env=dict(os.environ, GOOGLE_CLIENT_ID='from-env.apps.googleusercontent.com'))
check('TC-39.9 GOOGLE_CLIENT_ID (for hosting) wins over the file', r.stdout.strip() == 'from-env.apps.googleusercontent.com')
os.remove('answers.json')

finish('GOOGLE')
