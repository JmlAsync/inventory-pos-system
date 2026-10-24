"""Setting up and running a shop's own copy (v0.24.0, F22, DEC-026), test cases TC-31.x:
instance/config.toml, setup_shop.py, serve.py (waitress) and start_shop.bat."""
import json
import os
import subprocess
import sys
import threading
import tomllib
import urllib.request
from helpers import check, finish

PY = sys.executable


def run(*args, env=None):
    return subprocess.run([PY, *args], capture_output=True, text=True, encoding='utf-8', errors='replace',
                          env=dict(os.environ, **(env or {})))


def setup(answers):
    with open('answers.json', 'w', encoding='utf-8') as f:
        json.dump(answers, f)
    return run('setup_shop.py', '--answers', 'answers.json')


GOOD = {'network': {'other_devices': True, 'port': 5050},
        'shop': {'name': 'Kapehan sa Kanto', 'address': '12 Rizal St.', 'tin': '123-456-789-000', 'footer': 'Salamat!'},
        'admin': {'username': 'maria', 'password': 'kape-sa-umaga-2026'}}

ASK_DB = """
import logging; logging.disable(50)
from app import app
from models import db, User, ShopProfile
from werkzeug.security import check_password_hash
with app.app_context():
    users = User.query.order_by(User.id).all()
    shop = db.session.get(ShopProfile, 1)
    version = db.session.execute(db.text('SELECT version_num FROM alembic_version')).scalar()
    print([(u.username, u.role) for u in users])
    print(shop.name if shop else None)
    print(any(check_password_hash(u.password_hash, 'kape-sa-umaga-2026') for u in users), version)
    print(app.config['SQLALCHEMY_DATABASE_URI'])
"""

# ---- TC-31.1 without a config file the app uses the defaults
r = run('-c', 'import logging;logging.disable(50);from app import app;print(app.config["SQLALCHEMY_DATABASE_URI"])')
check('TC-31.1 no instance/config.toml: the local SQLite database is used', r.stdout.strip() == 'sqlite:///inventory.db')

# ---- TC-31.3 wrong answers are refused with a plain message, and nothing is created
for answers, message in [
        ({**GOOD, 'admin': {'username': 'maria', 'password': 'short'}}, 'at least 8 characters'),
        ({**GOOD, 'admin': {'username': 'maria', 'password': 'maria'}}, 'at least 8 characters'),
        ({**GOOD, 'admin': {'username': 'mariaclara', 'password': 'mariaclara'}}, 'same as the username'),
        ({**GOOD, 'admin': {'username': '', 'password': 'kape-sa-umaga-2026'}}, 'username'),
        ({**GOOD, 'network': {'other_devices': False, 'port': 80}}, 'port'),
        ({**GOOD, 'network': {'other_devices': False, 'port': 'abc'}}, 'port'),
        ({**GOOD, 'shop': {'name': ''}}, 'Shop name is required')]:
    r = setup(answers)
    check(f'TC-31.3 refused ("{message}"), exit code 1', r.returncode == 1 and message in r.stdout + r.stderr)
check('TC-31.3 ... and no config file or database was made by the refused runs',
      not os.path.exists('instance/config.toml') and not os.path.exists('instance/inventory.db'))

# ---- TC-31.2 a good run
r = setup(GOOD)
check('TC-31.2 setup finishes (exit code 0) and says how to start the system', r.returncode == 0 and 'start_shop.bat' in r.stdout)
with open('instance/config.toml', 'rb') as f:
    config = tomllib.load(f)
check('TC-31.2 instance/config.toml: other devices allowed (0.0.0.0) on port 5050, local SQLite database',
      config['server'] == {'host': '0.0.0.0', 'port': 5050} and config['database']['url'] == 'sqlite:///inventory.db')
text = open('instance/config.toml', encoding='utf-8').read()
keys = [k.lower() for section in config.values() if isinstance(section, dict) for k in section] + [k.lower() for k in config]
check('TC-31.2 the config file holds no password or secret (no such setting, and not the password itself)',
      not any('password' in k or 'secret' in k for k in keys) and 'kape-sa-umaga' not in text)
users, shop, rest, uri = run('-c', ASK_DB).stdout.strip().split('\n')
check('TC-31.2 the first admin is created, and no demo accounts', users == "[('maria', 'admin')]")
check('TC-31.2 the password is stored only as a hash that matches it', rest.startswith('True'))
check('TC-31.2 the database is at the newest migration', rest.endswith('0003'))
check('TC-31.2 the shop details are saved for the receipts', shop == 'Kapehan sa Kanto')

# ---- TC-31.4 running it again keeps everything
r = setup({**GOOD, 'network': {'other_devices': False, 'port': 5000}})
users, shop, rest, uri = run('-c', ASK_DB).stdout.strip().split('\n')
check('TC-31.4 a second run: the admin is not added twice and keeps the password', users == "[('maria', 'admin')]" and rest.startswith('True'))
check('TC-31.4 ... it says so', 'already exists' in r.stdout)
with open('instance/config.toml', 'rb') as f:
    check('TC-31.4 ... the new network choice is saved (this computer only: 127.0.0.1:5000)',
          tomllib.load(f)['server'] == {'host': '127.0.0.1', 'port': 5000})
check('TC-31.4 ... and the previous config was kept as config.toml.bak', os.path.exists('instance/config.toml.bak'))

# ---- TC-31.10 an answers file saved by PowerShell 5 or older Notepad (UTF-8 with a byte-order mark) is read too
with open('answers.json', 'w', encoding='utf-8-sig') as f:
    json.dump({**GOOD, 'network': {'other_devices': False, 'port': 5000}}, f)   # the same choice as TC-31.4
r = run('setup_shop.py', '--answers', 'answers.json')
check('TC-31.10 an answers file with a byte-order mark is accepted', r.returncode == 0)

# ---- TC-31.6 an environment variable can point to another database (for hosting)
r = run('-c', 'import logging;logging.disable(50);from app import app;print(app.config["SQLALCHEMY_DATABASE_URI"])',
        env={'DATABASE_URL': 'sqlite:///other.db'})
check('TC-31.6 DATABASE_URL overrides the config file', r.stdout.strip() == 'sqlite:///other.db')

# ---- TC-31.5 a config file with a mistake gives a plain message, not a crash
good_config = open('instance/config.toml', encoding='utf-8').read()
with open('instance/config.toml', 'w', encoding='utf-8') as f:
    f.write('[server\nport = 5000\n')
r = run('-c', 'from app import app')
check('TC-31.5 a broken config.toml: a plain message naming the file, and how to fix it',
      r.returncode != 0 and 'config.toml' in r.stderr + r.stdout and 'setup_shop.py' in r.stderr + r.stdout and 'Traceback' not in r.stderr)
with open('instance/config.toml', 'w', encoding='utf-8') as f:
    f.write(good_config)

# ---- TC-31.7 / 31.8 serve.py: the settings are checked, and waitress really answers
import serve
check('TC-31.8 server settings come from config.toml (127.0.0.1:5000)', serve.server_settings(serve.CONFIG) == ('127.0.0.1', 5000))
check('TC-31.8 a missing [server] section means this computer only, port 5000', serve.server_settings({}) == ('127.0.0.1', 5000))
for bad in [{'server': {'host': '8.8.8.8', 'port': 5000}}, {'server': {'host': '0.0.0.0', 'port': 99999}},
            {'server': {'host': '0.0.0.0', 'port': 'x'}}]:
    try:
        serve.server_settings(bad); refused = False
    except SystemExit as error:
        refused = 'config.toml' in str(error)
    check(f'TC-31.8 refused with a plain message: {bad["server"]}', refused)
from waitress.server import create_server
server = create_server(serve.app, host='127.0.0.1', port=0)
threading.Thread(target=server.run, daemon=True).start()
page = urllib.request.urlopen(f'http://127.0.0.1:{server.effective_port}/login', timeout=10)
body = page.read().decode()
check('TC-31.7 waitress serves the login page (200) with the security headers',
      page.status == 200 and 'Login' in body and page.headers['X-Frame-Options'] == 'DENY')
server.close()

# ---- TC-31.9 start_shop.bat
bat = open('start_shop.bat', encoding='utf-8').read()
check('TC-31.9 start_shop.bat runs serve.py with the project\'s own venv, from its own folder',
      'serve.py' in bat and r'venv\Scripts\python.exe' in bat and '%~dp0' in bat)

finish('SETUP')
