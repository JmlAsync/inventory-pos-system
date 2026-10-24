"""Set up the system for a shop, once per computer (v0.24.0, F22, DEC-026).

    python setup_shop.py                        asks the questions
    python setup_shop.py --answers answers.json for installers and tests (see the example at the bottom)

It writes instance/config.toml (how the server listens, which database and, if wanted, how to send email),
brings the database up to date (with a backup first), saves the shop's details for the receipts and creates
the first admin account with the owner's own password. It never creates the demo accounts (admin / admin123),
which are for the demo only.
Running it again is safe: data is kept, an existing admin is left as it is, email settings are kept unless new
ones are given (v0.26.0), and the old config.toml is kept as config.toml.bak.
"""
import getpass
import json
import os
import shutil
import sys
import tomllib
from mail import clean_mail_settings, SECURITY_PORTS   # the same checks the app uses (v0.26.0)

HERE = os.path.dirname(os.path.abspath(__file__))
INSTANCE = os.path.join(HERE, 'instance')
CONFIG_FILE = os.path.join(INSTANCE, 'config.toml')
MIN_PASSWORD_LENGTH = 8      # the same rule as Change password in app.py
MAX_USERNAME_LENGTH = 50     # the user table's limit


class Refused(Exception):
    """An answer that can't be used; the message says why, in plain words."""


# ---------- Checking each answer (the same rules as the app's own forms) ----------
def check_port(value):
    try:
        port = int(str(value).strip())
    except ValueError:
        raise Refused('The port must be a whole number from 1024 to 65535 (5000 is usual).')
    if not 1024 <= port <= 65535:
        raise Refused('The port must be a whole number from 1024 to 65535 (5000 is usual).')
    return port


def check_admin(username, password, repeated=None):
    username = (username or '').strip()
    if not username or len(username) > MAX_USERNAME_LENGTH:
        raise Refused(f'The admin username is required and can be at most {MAX_USERNAME_LENGTH} characters.')
    if repeated is not None and password != repeated:
        raise Refused('The two passwords are not the same.')
    if len(password or '') < MIN_PASSWORD_LENGTH:
        raise Refused(f'The password must be at least {MIN_PASSWORD_LENGTH} characters long.')
    if password.lower() == username.lower():
        raise Refused('The password can\'t be the same as the username.')
    return username, password


def toml_text(value):
    """A TOML text value. JSON's quoting is valid TOML for plain text."""
    return json.dumps(value, ensure_ascii=False)


def existing_mail_settings():
    """The [mail] part of the current config.toml, checked, or None (v0.26.0): kept when setup runs again without
    new ones. Settings with a mistake (the file may have been edited by hand) are left out, with a note; the old
    file is still there as config.toml.bak."""
    try:
        with open(CONFIG_FILE, 'rb') as f:
            old = tomllib.load(f).get('mail')
    except (OSError, tomllib.TOMLDecodeError):
        return None
    if not old:
        return None
    mail, problem = clean_mail_settings(old)
    if problem:
        print(f'The old email settings had a mistake ({problem}), so they were left out. '
              f'Run setup again and answer the email questions to set email up.')
    return mail


def write_config(host, port, mail=None):
    """Write instance/config.toml, keeping the previous one as config.toml.bak. The only password in it is the
    mail account's (v0.26.0), which the server needs to send email; account passwords are never written here."""
    os.makedirs(INSTANCE, exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        shutil.copyfile(CONFIG_FILE, CONFIG_FILE + '.bak')
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        f.write('# Settings for this shop\'s copy of Inventory & POS, written by setup_shop.py (v0.24.0).\n'
                '# Run "python setup_shop.py" again to change them. This file stays on this computer (instance/\n'
                '# never goes to GitHub). The only password in it is the mail account\'s, never a user\'s.\n\n'
                '[server]\n'
                f'# "127.0.0.1" = this computer only; "0.0.0.0" = also phones and computers on the shop\'s network\n'
                f'host = {toml_text(host)}\n'
                f'port = {port}\n\n'
                '[database]\n'
                '# The local package keeps everything in one file: instance/inventory.db\n'
                f'url = {toml_text("sqlite:///inventory.db")}\n')
        if mail:
            # v0.26.0 (DEC-028): how the shop sends email; Settings > Email in the app sends a test message
            f.write('\n[mail]\n'
                    '# "starttls" (usually port 587) or "ssl" (usually port 465); both are encrypted\n'
                    f'host = {toml_text(mail["host"])}\n'
                    f'port = {mail["port"]}\n'
                    f'security = {toml_text(mail["security"])}\n'
                    f'from_address = {toml_text(mail["from_address"])}\n'
                    f'username = {toml_text(mail["username"])}\n'
                    f'password = {toml_text(mail["password"])}\n')


# ---------- Asking (interactive) or reading an answers file ----------
def ask(question, check, default=None):
    """Ask until the answer passes its check."""
    while True:
        shown = f' [{default}]' if default not in (None, '') else ''
        answer = input(f'{question}{shown}: ').strip()
        try:
            return check(answer if answer else (default or ''))
        except Refused as reason:
            print(f'  {reason}')


def ask_answers():
    print('Inventory & POS: setting up this computer for the shop.\n')
    other = ask('Will phones or other computers in the shop use the system? (y/n)',
                lambda a: a.lower().startswith('y'), 'n')
    port = ask('Port number', check_port, '5000')
    print('\nThe shop\'s details for the receipts (you can change them later on the Shop details page).')
    shop = {'name': input('  Shop name: ').strip(), 'address': input('  Address (optional): ').strip(),
            'tin': input('  TIN (optional): ').strip(), 'footer': input('  Receipt footer (optional): ').strip()}
    print('\nThe first admin account (the owner). Choose your own password; it is stored only as a hash.')
    while True:
        try:
            username, password = check_admin(input('  Admin username: '), getpass.getpass('  Password: '),
                                              getpass.getpass('  Password again: '))
            break
        except Refused as reason:
            print(f'  {reason}')
    # v0.26.0: email sending, optional; skipping keeps any email settings from an earlier run
    print('\nEmail sending (optional). Invitations and sign-in codes will be sent by email; you can set it up later.')
    mail = None
    if ask('Set up email sending now? (y/n)', lambda a: a.lower().startswith('y'), 'n'):
        print('  For Gmail: server smtp.gmail.com, security starttls, port 587, and an App Password.')
        while True:
            values = {'host': input('  Mail server: ').strip(),
                      'security': input('  Security, starttls or ssl [starttls]: ').strip() or 'starttls'}
            usual_port = SECURITY_PORTS.get(values['security'].lower(), 587)
            values['port'] = input(f'  Port [{usual_port}]: ').strip() or usual_port
            values['from_address'] = input('  Send from (email address): ').strip()
            values['username'] = input(f'  Mail account username [{values["from_address"]}]: ').strip() or values['from_address']
            values['password'] = getpass.getpass('  Mail account password (hidden): ')
            mail, problem = clean_mail_settings(values)
            if not problem:
                break
            print(f'  {problem}')
    return {'network': {'other_devices': other, 'port': port}, 'shop': shop,
            'admin': {'username': username, 'password': password}, 'mail': mail}


def read_answers(path):
    # utf-8-sig also accepts the byte-order mark that PowerShell 5 and older Notepad put at the start
    with open(path, encoding='utf-8-sig') as f:
        return json.load(f)


# ---------- Doing it ----------
def set_up(answers):
    network, shop, admin = answers.get('network', {}), answers.get('shop', {}), answers.get('admin', {})
    # 1. Check everything first, so a wrong answer changes nothing at all
    port = check_port(network.get('port', 5000))
    host = '0.0.0.0' if network.get('other_devices') else '127.0.0.1'
    username, password = check_admin(admin.get('username'), admin.get('password'))
    from app import validate_shop_form    # the Shop details page's own checks (v0.22.0)
    shop_values, problem = validate_shop_form(shop)
    if problem:
        raise Refused(problem)
    if answers.get('mail'):   # v0.26.0: new email settings, checked like everything else
        mail, problem = clean_mail_settings(answers['mail'])
        if problem:
            raise Refused(problem)
    else:
        mail = existing_mail_settings()   # none given: keep the ones from an earlier run, if any

    # 2. Settings first: the app reads them when it starts
    write_config(host, port, mail)
    from app import app, upgrade_database
    from models import db, User, ShopProfile
    from werkzeug.security import generate_password_hash
    with app.app_context():
        upgrade_database()    # backs up, then runs any missing migrations (v0.23.0)
        profile = db.session.get(ShopProfile, 1) or ShopProfile(id=1)
        for key, value in shop_values.items():
            setattr(profile, key, value)
        db.session.add(profile)
        if User.query.filter_by(username=username).first():
            print(f'The account "{username}" already exists, so it was left as it is '
                  f'(change its password on the Profile page).')
        else:
            db.session.add(User(username=username, password_hash=generate_password_hash(password), role='admin'))
        db.session.commit()

    where = 'this computer and the shop\'s network' if host == '0.0.0.0' else 'this computer only'
    print(f'\nDone. The system will listen on port {port} ({where}).')
    print('Start it by double-clicking start_shop.bat (or: venv\\Scripts\\python.exe serve.py),')
    print(f'then open http://127.0.0.1:{port} and log in as "{username}".')
    if mail:
        print('Email: open Email in the admin menu and send a test message to check it works.')


def main():
    try:
        if len(sys.argv) == 3 and sys.argv[1] == '--answers':
            answers = read_answers(sys.argv[2])
        elif len(sys.argv) == 1:
            answers = ask_answers()
        else:
            print('Use:  python setup_shop.py   or   python setup_shop.py --answers answers.json')
            return 2
        set_up(answers)
        return 0
    except Refused as reason:
        print(f'Setup stopped, nothing was changed: {reason}')
        return 1
    except (OSError, ValueError) as error:
        print(f'Setup stopped, nothing was changed: the answers file could not be read ({error}).')
        return 1


if __name__ == '__main__':
    sys.exit(main())

# Example answers.json (for installers and tests; delete it afterwards, because it holds passwords).
# "mail" is optional (v0.26.0); leave it out to set up email later or to keep the settings already there:
# {"network": {"other_devices": true, "port": 5000},
#  "shop": {"name": "Sample Café", "address": "", "tin": "", "footer": "Thank you!"},
#  "admin": {"username": "maria", "password": "choose-a-long-one"},
#  "mail": {"host": "smtp.gmail.com", "port": 587, "security": "starttls", "from_address": "cafe@gmail.com",
#           "username": "cafe@gmail.com", "password": "the app password"}}
