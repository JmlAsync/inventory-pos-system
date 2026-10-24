"""Email sending (v0.26.0, F23, DEC-028), test cases TC-34.x: mail.py with a fake mail server (no internet,
rule T3), the Email settings page and its test message, the [mail] settings in config.toml and setup_shop.py.
The fake replaces smtplib's two connection classes and records every step, so the tests can check the order
(encryption before the password) and make each kind of failure happen on purpose."""
import json
import logging
import os
import smtplib
import socket
import ssl
import subprocess
import sys
import tomllib
from helpers import check, finish, make_users, text

from app import app, upgrade_database
from models import db, User, ShopProfile
import mail

app.config['CSRF_ENABLED'] = False
PASSWORD = 'app-pass "quote" \\ wörd'   # quotes, a backslash and a non-English letter, to test how it is stored


# ---------- The fake mail server ----------
steps, sent, fail = [], [], {}


class FakeSMTP:
    """Stands in for smtplib.SMTP: records each step; fail['connect' / 'starttls' / 'login' / 'send'] raises."""
    def __init__(self, host, port, timeout=None, context=None):
        steps.append(('connect', type(self).__name__, host, port, timeout))
        if context is not None:
            steps.append(('certificate checked', context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname))
        if 'connect' in fail:
            raise fail['connect']

    def __enter__(self):
        return self

    def __exit__(self, *details):
        steps.append(('quit',))
        return False

    def starttls(self, context=None):
        steps.append(('starttls',))
        steps.append(('certificate checked', context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname))
        if 'starttls' in fail:
            raise fail['starttls']

    def login(self, user, password):
        steps.append(('login', user, password))
        if 'login' in fail:
            raise fail['login']

    def send_message(self, message):
        if 'send' in fail:
            raise fail['send']
        steps.append(('send',))
        sent.append(message)


class FakeSMTP_SSL(FakeSMTP):
    pass


smtplib.SMTP, smtplib.SMTP_SSL = FakeSMTP, FakeSMTP_SSL


def reset(**failures):
    steps.clear(); sent.clear(); fail.clear(); fail.update(failures)


GMAIL = {'host': 'smtp.example.com', 'port': 587, 'security': 'starttls', 'from_address': 'cafe@example.com',
         'username': 'cafe@example.com', 'password': PASSWORD}

with app.app_context():
    db.drop_all(); upgrade_database(); make_users(db, User)
    db.session.add(ShopProfile(id=1, name='Sample Café')); db.session.commit()


def send(to='maria@example.com'):
    with app.app_context():
        return mail.send_mail(to, 'Hello', 'Body text', sender_name='Sample Café')


# ---- TC-34.1 nothing set up: a plain message, nothing sent
app.config['MAIL'] = {}
reset()
check('TC-34.1 without [mail] settings: "isn\'t set up yet", with what to do', 'setup_shop.py' in (send() or '') and steps == [])

# ---- TC-34.2 STARTTLS: encrypted first, then the login, then the message
app.config['MAIL'] = dict(GMAIL)
reset()
check('TC-34.2 sent: send_mail() returns None', send() is None)
check('TC-34.2 connects to the server and port, with a time limit',
      steps[0] == ('connect', 'FakeSMTP', 'smtp.example.com', 587, mail.TIMEOUT_SECONDS))
check('TC-34.2 the connection is encrypted (and the certificate checked) BEFORE the password is sent',
      [s[0] for s in steps] == ['connect', 'starttls', 'certificate checked', 'login', 'send', 'quit']
      and ('certificate checked', True) in steps)
check('TC-34.2 logs in with the account\'s username and password', ('login', 'cafe@example.com', PASSWORD) in steps)
message = sent[0]
check('TC-34.2 the message is from the shop\'s name and address',
      message['From'].addresses[0].display_name == 'Sample Café' and message['From'].addresses[0].addr_spec == 'cafe@example.com')
check('TC-34.2 to the address, with the subject, a date and a message id',
      message['To'] == 'maria@example.com' and message['Subject'] == 'Hello' and message['Date'] and message['Message-ID'])
check('TC-34.2 plain text only', message.get_content_type() == 'text/plain' and 'Body text' in message.get_content())

# ---- TC-34.3 SSL (port 465) and a server that needs no login
app.config['MAIL'] = dict(GMAIL, security='ssl', port=465)
reset(); send()
check('TC-34.3 "ssl" connects with SMTP_SSL on port 465, certificate checked, no STARTTLS',
      steps[0][:4] == ('connect', 'FakeSMTP_SSL', 'smtp.example.com', 465) and ('certificate checked', True) in steps
      and ('starttls',) not in steps and len(sent) == 1)
app.config['MAIL'] = dict(GMAIL, username='', password='')
reset(); send()
check('TC-34.3 no username: no login step, the message is still sent', not any(s[0] == 'login' for s in steps) and len(sent) == 1)

# ---- TC-34.4 each failure is one plain sentence (C6); the password never appears in it or in the log
app.config['MAIL'] = dict(GMAIL)
log_lines = []
handler = logging.Handler(); handler.emit = lambda record: log_lines.append(record.getMessage())
from flask.logging import default_handler   # Flask's own handler prints to the screen: off while capturing
logging.disable(logging.NOTSET); app.logger.removeHandler(default_handler); app.logger.addHandler(handler)
app.logger.propagate = False   # and so does the one the migrations set up (alembic.ini)
cases = [
    ('login', smtplib.SMTPAuthenticationError(535, b'5.7.8 Username and Password not accepted'), 'App Password'),
    ('send', smtplib.SMTPRecipientsRefused({'maria@example.com': (550, b'No such user')}), 'refused the address maria@example.com'),
    ('send', smtplib.SMTPSenderRefused(553, b'Not allowed', 'cafe@example.com'), 'send from cafe@example.com'),
    ('send', smtplib.SMTPDataError(554, b'Rejected'), 'did not accept the message'),
    ('starttls', smtplib.SMTPNotSupportedError('STARTTLS extension not supported'), 'encrypted connection'),
    ('starttls', ssl.SSLError('wrong version number'), 'secure connection'),
    ('connect', socket.gaierror(11001, 'getaddrinfo failed'), 'Could not reach the mail server smtp.example.com'),
    ('connect', TimeoutError('timed out'), 'Could not reach the mail server'),
    ('connect', ConnectionRefusedError(10061, 'refused'), 'Could not reach the mail server'),
    ('connect', smtplib.SMTPServerDisconnected('Connection unexpectedly closed'), 'Could not reach the mail server'),
]
for step, error, words in cases:
    reset(**{step: error})
    answer = send() or ''
    check(f'TC-34.4 {type(error).__name__} during {step}: "{words}", nothing sent', words in answer and sent == [])
check('TC-34.4 no internet: the message says selling still works', 'Selling and everything else still works' in answer)
logging.disable(logging.CRITICAL); app.logger.removeHandler(handler); app.logger.addHandler(default_handler)
app.logger.propagate = True
check(f'TC-34.4 every failure is in the server log ({len(log_lines)} lines), never the password',
      len(log_lines) == len(cases) and not any('app-pass' in line for line in log_lines))

# ---- TC-34.5 addresses are checked; a line break can't add a hidden second recipient
for address in ['', 'maria', 'maria@example', '@example.com', 'maria@.com', 'ma ria@example.com',
                'a@b@example.com', 'maria@example.com\r\nBcc: other@example.com', '<maria@example.com>', 'x' * 250 + '@example.com']:
    check(f'TC-34.5 not an address: {address[:40]!r}', mail.check_email_address(address) is None)
check('TC-34.5 spaces around an address are removed', mail.check_email_address(' maria@example.com ') == 'maria@example.com')
reset()
check('TC-34.5 send_mail() refuses a header trick and sends nothing',
      'not an email address' in send('maria@example.com\nBcc: other@example.com') and steps == [])

# ---- TC-34.6 the settings are checked like any form (S7), also when config.toml was edited by hand
for values, words in [({**GMAIL, 'host': 'smtp gmail.com'}, 'mail server must be a name'),
                      ({**GMAIL, 'host': ''}, 'mail server must be a name'),
                      ({**GMAIL, 'security': 'tls'}, '"starttls"'),
                      ({**GMAIL, 'port': 'abc'}, 'mail port'),
                      ({**GMAIL, 'port': 70000}, 'mail port'),
                      ({**GMAIL, 'from_address': 'cafe'}, '"send from"'),
                      ({**GMAIL, 'password': ''}, 'needs its password'),
                      ({**GMAIL, 'password': 'two\nlines'}, 'no line breaks')]:
    settings, problem = mail.clean_mail_settings(values)
    check(f'TC-34.6 refused: {words}', settings is None and words in (problem or ''))
settings, _ = mail.clean_mail_settings({'host': 'smtp.example.com', 'security': 'SSL', 'from_address': 'a@example.com'})
check('TC-34.6 the usual port is filled in (465 for ssl), capitals accepted', settings['port'] == 465 and settings['security'] == 'ssl')
app.config['MAIL'] = dict(GMAIL, security='tls')
reset()
check('TC-34.6 a mistake in config.toml is named, and nothing is sent', 'config.toml have a mistake' in (send() or '') and steps == [])

# ---- TC-34.7 the Email settings page: admins only (S2), never shows the password
app.config['MAIL'] = dict(GMAIL)
admin = app.test_client(); admin.post('/login', data={'username': 'admin', 'password': 'admin123'})
cashier = app.test_client(); cashier.post('/login', data={'username': 'cashier', 'password': 'cashier123'})
check('TC-34.7 a visitor is sent to the login page', app.test_client().get('/settings/email').status_code == 302)
reset()
check('TC-34.7 a cashier gets 403, even posting the form, and nothing is sent',
      cashier.get('/settings/email').status_code == 403
      and cashier.post('/settings/email', data={'to': 'x@example.com'}).status_code == 403 and steps == [])
page = text(admin.get('/settings/email'))
check('TC-34.7 the admin sees the server, port, security and sender',
      all(words in page for words in ['smtp.example.com, port 587', 'STARTTLS', 'cafe@example.com']))
check('TC-34.7 the password is never shown, only that it is saved', 'app-pass' not in page and 'Saved (never shown)' in page)
test_form = page[page.index('action="/settings/email"'):]
check('TC-34.7 set up: the Send button is on', 'disabled' not in test_form[:test_form.index('</button>')])
check('TC-34.7 the sidebar has an Email link for the admin, not for the cashier',
      'href="/settings/email"' in page and 'href="/settings/email"' not in text(cashier.get('/products')))

# ---- TC-34.8 the test message
reset()
page = text(admin.post('/settings/email', data={'to': ' maria@example.com '}, follow_redirects=True))
check('TC-34.8 "Test message sent to ..." with a hint about the spam folder', 'Test message sent to maria@example.com' in page and 'spam' in page)
check('TC-34.8 one message, from the shop, naming who sent it',
      len(sent) == 1 and sent[0]['Subject'] == 'Test message from Sample Café' and 'Sent by admin' in sent[0].get_content())
reset()
page = text(admin.post('/settings/email', data={'to': 'not-an-address'}, follow_redirects=True))
check('TC-34.8 a wrong address: asked to type one, nothing sent', 'Type the email address' in page and steps == [])
reset(connect=socket.gaierror(11001, 'getaddrinfo failed'))
page = text(admin.post('/settings/email', data={'to': 'maria@example.com'}, follow_redirects=True))
check('TC-34.8 no internet: the plain message on the page, not an error page', 'Could not reach the mail server' in page)
app.config['MAIL'] = {}
page = text(admin.get('/settings/email'))
test_form = page[page.index('action="/settings/email"'):]
check('TC-34.8 not set up: the page says how (once), and the Send button is off',
      page.count('setup_shop.py') == 1 and 'disabled' in test_form[:test_form.index('</button>')])
reset()
page = text(admin.post('/settings/email', data={'to': 'maria@example.com'}, follow_redirects=True))
check('TC-34.8 ... and posting anyway sends nothing', "isn't set up yet" in page.replace('&#39;', "'") and steps == [])

# ---------- config.toml and setup_shop.py (run as programs, like test_setup.py) ----------
PY = sys.executable


def run(*args, env=None):
    return subprocess.run([PY, *args], capture_output=True, text=True, encoding='utf-8', errors='replace',
                          env=dict(os.environ, **(env or {})))


def setup(answers):
    with open('answers.json', 'w', encoding='utf-8') as f:
        json.dump(answers, f)
    return run('setup_shop.py', '--answers', 'answers.json')


def config():
    with open(os.path.join('instance', 'config.toml'), 'rb') as f:
        return tomllib.load(f)


GOOD = {'network': {'other_devices': False, 'port': 5000},
        'shop': {'name': 'Sample Café', 'address': '', 'tin': '', 'footer': ''},
        'admin': {'username': 'maria', 'password': 'kape-sa-umaga-2026', 'email': 'maria@example.com'}}   # email: v0.27.0
READ_MAIL = 'import logging;logging.disable(50);from app import app;print(app.config["MAIL"].get("host"), app.config["MAIL"].get("password"))'

# ---- TC-34.9 setup writes the [mail] part; the app reads it; the password is stored exactly and never printed
r = setup({**GOOD, 'mail': {**GMAIL, 'port': ''}})
check('TC-34.9 setup with email answers succeeds and says how to test it', r.returncode == 0 and 'send a test message' in r.stdout)
check('TC-34.9 [mail] is written: server, the usual port, security, sender, account',
      {k: v for k, v in config()['mail'].items() if k != 'password'} ==
      {'host': 'smtp.example.com', 'port': 587, 'security': 'starttls', 'from_address': 'cafe@example.com', 'username': 'cafe@example.com'})
check('TC-34.9 the password is stored exactly (quotes, backslash, ö) and never printed',
      config()['mail']['password'] == PASSWORD and 'app-pass' not in r.stdout + r.stderr)
check('TC-34.9 the app reads the [mail] settings', run('-c', READ_MAIL).stdout.strip() == f'smtp.example.com {PASSWORD}')
check('TC-34.9 MAIL_PASSWORD (for hosting) wins over the file',
      run('-c', READ_MAIL, env={'MAIL_PASSWORD': 'from-env-123'}).stdout.strip() == 'smtp.example.com from-env-123')

# ---- TC-34.10 wrong email answers change nothing; running setup again keeps or replaces the settings
before = open(os.path.join('instance', 'config.toml'), encoding='utf-8').read()
r = setup({**GOOD, 'mail': {**GMAIL, 'security': 'tls'}})
check('TC-34.10 a wrong email answer is refused with its reason, exit 1', r.returncode == 1 and '"starttls"' in r.stdout)
check('TC-34.10 ... and config.toml is unchanged', open(os.path.join('instance', 'config.toml'), encoding='utf-8').read() == before)
r = setup(GOOD)
check('TC-34.10 setup again without email answers keeps the email settings', r.returncode == 0 and config()['mail']['password'] == PASSWORD)
r = setup({**GOOD, 'mail': {'host': 'mail.example.org', 'security': 'ssl', 'from_address': 'shop@example.org'}})
check('TC-34.10 setup with new email answers replaces them (ssl: port 465)',
      r.returncode == 0 and config()['mail']['host'] == 'mail.example.org' and config()['mail']['port'] == 465
      and config()['mail']['password'] == '')
text_now = open(os.path.join('instance', 'config.toml'), encoding='utf-8').read()
with open(os.path.join('instance', 'config.toml'), 'w', encoding='utf-8') as f:   # a hand edit that removed a line
    f.write('\n'.join(line for line in text_now.splitlines() if not line.startswith('from_address')) + '\n')
r = setup(GOOD)
check('TC-34.10 old email settings with a mistake: setup still finishes, says so, and leaves them out',
      r.returncode == 0 and 'old email settings had a mistake' in r.stdout and 'mail' not in config())

finish('EMAIL')
