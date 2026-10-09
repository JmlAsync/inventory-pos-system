"""Security controls (F12, v0.13.1-v0.13.5): secret key, CSRF tokens, login limit, headers, passwords."""
import sys, os, re, subprocess
from datetime import timedelta
from helpers import check, finish, text, fixture
from app import app, upgrade_database
from models import db, User, Product
from werkzeug.security import generate_password_hash as g
from flask.sessions import SecureCookieSessionInterface
with app.app_context():
    db.drop_all(); upgrade_database()
    db.session.add_all([User(username='admin', password_hash=g('admin123'), role='admin'),
                        User(username='cashier', password_hash=g('cashier123'), role='cashier'),
                        Product(name='Latte', sku='L1', price=150, quantity=10)]); db.session.commit()
CSRF = 'CSRF_ENABLED' in app.config
def token(c, path='/login'):
    h = c.get(path).get_data(as_text=True)
    m = re.search(r'name="csrf_token" value="([0-9a-f]+)"', h); return m.group(1) if m else ''
def login(c, u, p):
    return c.post('/login', data={'username': u, 'password': p, 'csrf_token': token(c)})

# ---- v0.13.1 secret key
key = app.config['SECRET_KEY']
check('secret key is not the old public one', key != 'dev-secret-change-this-later')
check('secret key is long and random (64 hex chars)', len(key) == 64)
old = app.secret_key; app.secret_key = 'dev-secret-change-this-later'
forged = SecureCookieSessionInterface().get_signing_serializer(app).dumps({'_user_id': '1', '_fresh': True}); app.secret_key = old
c = app.test_client(); c.set_cookie('session', forged)
check('cookie forged with the old public key is rejected', c.get('/reports/sales').status_code == 302)
again = subprocess.run([sys.executable, '-c', 'import logging;logging.disable(50);from app import app;print(app.config["SECRET_KEY"])'], capture_output=True, text=True).stdout.strip()
check('same key after restart (logins survive)', again == key)
env = dict(os.environ, SECRET_KEY='from-environment-123')
check('SECRET_KEY environment variable wins', subprocess.run([sys.executable, '-c', 'import logging;logging.disable(50);from app import app;print(app.config["SECRET_KEY"])'], capture_output=True, text=True, env=env).stdout.strip() == 'from-environment-123')
check('instance/ folder (secret key, database) is in .gitignore', 'instance/' in open('.gitignore').read().split())
check('no secret key written in app.py', "dev-secret" not in open('app.py').read())

# ---- v0.13.2
c = app.test_client(); login(c, 'admin', 'admin123')
r = c.post('/products/add', data={'name': 'Evil', 'sku': 'EV1', 'price': '1', 'quantity': '1'})
check('POST without CSRF token refused (400)', r.status_code == 400)
r = c.post('/products/add', data={'name': 'Evil', 'sku': 'EV1', 'price': '1', 'quantity': '1', 'csrf_token': 'wrong'})
check('POST with wrong token refused (400)', r.status_code == 400)
with app.app_context(): check('nothing was added', Product.query.filter_by(sku='EV1').count() == 0)
r = c.post('/products/add', data={'name': 'Mocha', 'sku': 'M1', 'price': '160', 'quantity': '5', 'csrf_token': token(c, '/products/add')})
check('POST with the right token works', r.status_code == 302)
check('400 page is friendly', 'expired' in c.post('/products/add', data={}).get_data(as_text=True))
for page in ['/products', '/sales/new', '/profile', '/products/add', '/products/edit/1']:
    h = c.get(page).get_data(as_text=True)
    forms = h.count('method="POST"') + h.count('method="post"')
    check(f'every POST form on {page} carries a token ({forms})', forms > 0 and h.count('name="csrf_token"') == forms)
check('login without token refused', app.test_client().post('/login', data={'username': 'admin', 'password': 'admin123'}).status_code == 400)
check('logout by plain link (GET) no longer allowed', c.get('/logout').status_code == 405)
r = c.post('/logout', data={'csrf_token': token(c, '/products')})
check('logout by button (POST + token) works', r.status_code == 302 and c.get('/products').status_code == 302)
c2 = app.test_client(); r = c2.get('/login'); check('session cookie is SameSite=Lax and HttpOnly', 'SameSite=Lax' in r.headers.get('Set-Cookie', '') and 'HttpOnly' in r.headers.get('Set-Cookie', ''))

# ---- v0.13.3
c = app.test_client()
for i in range(5): login(c, 'cashier', f'wrong{i}')
r = login(c, 'cashier', 'cashier123')
check('after 5 wrong passwords even the right one waits (429)', r.status_code == 429 and 'Too many' in r.get_data(as_text=True))
check('other accounts are not blocked', login(app.test_client(), 'admin', 'admin123').status_code == 302)
import app as A
A.failed_logins.clear()
c = app.test_client(); [login(c, 'cashier', 'bad') for _ in range(4)]
check('4 wrong then right still logs in', login(c, 'cashier', 'cashier123').status_code == 302)
[login(c, 'cashier', 'bad') for _ in range(4)]
check('success resets the counter (4 + 1 more wrong: not locked)', login(c, 'cashier', 'bad').status_code == 200)
A.failed_logins.clear(); c = app.test_client(); [login(c, 'cashier', 'bad') for _ in range(5)]
for k in A.failed_logins: A.failed_logins[k] = [t - timedelta(minutes=6) for t in A.failed_logins[k]]
check('lock ends after 5 minutes', login(c, 'cashier', 'cashier123').status_code == 302)
A.failed_logins.clear()

# ---- v0.13.4
r = app.test_client().get('/login')
check('X-Frame-Options DENY (no clickjacking)', r.headers.get('X-Frame-Options') == 'DENY')
check('X-Content-Type-Options nosniff', r.headers.get('X-Content-Type-Options') == 'nosniff')
check('Referrer-Policy same-origin', r.headers.get('Referrer-Policy') == 'same-origin')
src = open('app.py').read()
check('debug mode off unless FLASK_DEBUG=1', 'app.run(debug=True)' not in src and "FLASK_DEBUG" in src)

# ---- v0.13.5
c = app.test_client(); login(c, 'cashier', 'cashier123')
def change(cur, new, conf):
    return c.post('/profile/password', data={'current_password': cur, 'new_password': new, 'confirm_password': conf, 'csrf_token': token(c, '/profile')}, follow_redirects=True).get_data(as_text=True)
check('wrong current password refused', 'Current password is wrong' in change('nope', 'longenough1', 'longenough1'))
check('short new password refused', 'at least 8' in change('cashier123', 'short', 'short'))
check('mismatched confirmation refused', 'do not match' in change('cashier123', 'longenough1', 'longenough2'))
check('password equal to username refused', 'same as your username' in change('cashier123', 'cashier', 'cashier'))
check('valid change accepted', 'Password changed' in change('cashier123', 'Kape-2026!', 'Kape-2026!'))
check('old password no longer works', login(app.test_client(), 'cashier', 'cashier123').status_code == 200)
check('new password works', login(app.test_client(), 'cashier', 'Kape-2026!').status_code == 302)
check('visitor cannot change a password', app.test_client().post('/profile/password', data={}).status_code in (302, 400))

finish('SECURITY')
