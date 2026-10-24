"""Sending email (v0.26.0, F23, DEC-028), with Python's own smtplib, so no extra package is needed (rule D1).

The settings are the [mail] part of instance/config.toml, written by setup_shop.py (rule P1: the mail password
lives there, never in Git). The MAIL_PASSWORD environment variable wins over the file, for hosting services.
Every connection is encrypted ("starttls" on port 587 or "ssl" on port 465) and the server's certificate is
checked, so the mail password never crosses the network readable. Messages are plain text.

    error = send_mail('maria@example.com', 'Subject', 'Text')   # None = the mail server accepted it

Invitations (v0.27.0) and sign-in codes (v0.28.0) will be sent with send_mail(). For now only the test button
on Settings > Email uses it.
"""
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from flask import current_app

SECURITY_PORTS = {'starttls': 587, 'ssl': 465}   # the usual port for each kind of encrypted connection
TIMEOUT_SECONDS = 15        # give up on a mail server that doesn't answer, instead of freezing the page
MAX_EMAIL_LENGTH = 254      # the longest email address the email standard allows
MAX_HOST_LENGTH = 253       # the longest server name
MAX_PASSWORD_LENGTH = 200
NOT_SET_UP = ('Email sending isn\'t set up yet. On the shop\'s computer, run "python setup_shop.py" '
              'and answer the email questions.')


def check_email_address(text):
    """The address without spaces around it, or None if it can't be an email address (v0.26.0).
    Kept simple on purpose: one @, a dot in the part after it, no spaces or brackets. The real proof is
    the message arriving."""
    address = (text or '').strip()
    if not address or len(address) > MAX_EMAIL_LENGTH or address.count('@') != 1:
        return None
    name, domain = address.split('@')
    if not name or '.' not in domain or domain.startswith('.') or domain.endswith('.') or '..' in domain:
        return None
    # No spaces, control characters or the signs that have a special meaning in an email header
    if any(c.isspace() or ord(c) < 32 or c in '<>()[],;:"\\' for c in address):
        return None
    return address


def clean_mail_settings(values):
    """Check mail settings typed into setup_shop.py, or found in config.toml (it may have been edited by hand).
    Returns (settings, None) with clean values, or (None, a plain message saying what is wrong)."""
    host = str(values.get('host') or '').strip()
    if not host or len(host) > MAX_HOST_LENGTH or not all(c.isalnum() or c in '.-' for c in host) or not host.isascii():
        return None, 'The mail server must be a name like smtp.gmail.com (letters, numbers, dots and dashes).'
    security = str(values.get('security') or 'starttls').strip().lower()
    if security not in SECURITY_PORTS:
        return None, 'Security must be "starttls" (usually port 587) or "ssl" (usually port 465).'
    try:
        port = int(str(values.get('port') or SECURITY_PORTS[security]).strip())
    except ValueError:
        port = 0
    if not 1 <= port <= 65535:
        return None, f'The mail port must be a whole number from 1 to 65535 ({SECURITY_PORTS[security]} is usual for {security}).'
    from_address = check_email_address(values.get('from_address'))
    if from_address is None:
        return None, 'The "send from" address must be an email address, like cafe@gmail.com.'
    username = str(values.get('username') or '').strip()
    password = str(values.get('password') or '')
    if len(username) > MAX_EMAIL_LENGTH:
        return None, f'The mail account username can be at most {MAX_EMAIL_LENGTH} characters.'
    if username and not password:
        return None, 'The mail account needs its password (for Gmail, an App Password).'
    if len(password) > MAX_PASSWORD_LENGTH or any(ord(c) < 32 for c in password):
        return None, f'The mail password can be at most {MAX_PASSWORD_LENGTH} characters, with no line breaks.'
    return {'host': host, 'port': port, 'security': security, 'from_address': from_address,
            'username': username, 'password': password}, None


def mail_settings():
    """The shop's mail settings (app.config['MAIL'], read from config.toml in app.py), or None if email isn't
    set up. Returns (settings, problem): a hand-edited file with a mistake gives a problem to show."""
    values = current_app.config.get('MAIL') or {}
    if not values.get('host'):
        return None, NOT_SET_UP
    settings, problem = clean_mail_settings(values)
    if problem:
        return None, 'The email settings in instance/config.toml have a mistake: ' + problem
    return settings, None


def deliver(settings, message):
    """Hand one message to the mail server. Encrypted in both cases; create_default_context() checks the server's
    certificate, so a fake server on the network can't collect the password."""
    context = ssl.create_default_context()
    if settings['security'] == 'ssl':
        server = smtplib.SMTP_SSL(settings['host'], settings['port'], timeout=TIMEOUT_SECONDS, context=context)
    else:
        server = smtplib.SMTP(settings['host'], settings['port'], timeout=TIMEOUT_SECONDS)
    with server:
        if settings['security'] == 'starttls':
            server.starttls(context=context)   # switch to an encrypted connection BEFORE logging in
        if settings['username']:
            server.login(settings['username'], settings['password'])
        server.send_message(message)


def send_mail(to, subject, body, sender_name=''):
    """Send one plain-text email to one address. Returns None when the mail server accepted it, or one sentence
    for the screen saying what went wrong and what to do (rule C6). The details go to the server log; the
    password is never written anywhere."""
    address = check_email_address(to)
    if address is None:
        return 'That is not an email address. Type it like name@example.com.'
    if current_app.config.get('DEMO_MODE'):
        # v0.28.0 (rule P3, DEC-030): the demo sends nothing; the message is shown in the server's window instead
        print(f'\n[DEMO_MODE] Email to {address}\nSubject: {subject}\n{body}', flush=True)
        return None
    settings, problem = mail_settings()
    if problem:
        return problem
    message = EmailMessage()
    message['From'] = formataddr((sender_name, settings['from_address']))   # shows the shop's name, e.g. "Sample Café"
    message['To'] = address
    message['Subject'] = subject
    message['Date'] = formatdate(usegmt=True)
    message['Message-ID'] = make_msgid(domain=settings['from_address'].split('@')[1])   # some mail services want one
    message.set_content(body)
    host = settings['host']
    # The order matters: smtplib's errors are also OSErrors, so the specific ones are caught first
    try:
        deliver(settings, message)
        return None
    except smtplib.SMTPAuthenticationError as error:
        current_app.logger.warning('Email not sent: login refused by %s (%s)', host, error.smtp_code)
        return ('The mail server refused the username or password. For Gmail, use an App Password '
                '(Google Account > Security > App passwords), not the normal password.')
    except smtplib.SMTPRecipientsRefused:
        current_app.logger.warning('Email not sent: %s refused the address %s', host, address)
        return f'The mail server refused the address {address}. Check it and try again.'
    except smtplib.SMTPSenderRefused:
        current_app.logger.warning('Email not sent: %s refused the sender %s', host, settings['from_address'])
        return (f'The mail server refused to send from {settings["from_address"]}. It must be an address '
                f'this mail account is allowed to send from.')
    except smtplib.SMTPNotSupportedError:
        current_app.logger.warning('Email not sent: %s offers no STARTTLS on port %s', host, settings['port'])
        return ('The mail server doesn\'t offer an encrypted connection on this port. Check the security '
                'setting: "starttls" usually uses port 587, "ssl" port 465.')
    except ssl.SSLError as error:
        current_app.logger.warning('Email not sent: secure connection to %s failed (%s)', host, error)
        return ('A secure connection to the mail server could not be made. Check the server name and the security '
                'setting: "starttls" usually uses port 587, "ssl" port 465.')
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, TimeoutError, ConnectionError) as error:
        current_app.logger.warning('Email not sent: could not talk to %s (%r)', host, error)
        return (f'Could not reach the mail server {host}. Check the internet connection, then try again. '
                f'Selling and everything else still works without it.')
    except smtplib.SMTPException as error:
        current_app.logger.warning('Email not sent: %s answered %r', host, error)
        return 'The mail server did not accept the message. Check the email settings and try again.'
    except OSError as error:   # no internet, or a server name that doesn't exist
        current_app.logger.warning('Email not sent: could not reach %s (%r)', host, error)
        return (f'Could not reach the mail server {host}. Check the internet connection and the server name, '
                f'then try again. Selling and everything else still works without it.')
