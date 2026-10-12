"""Logins that can be ended (DEF-51, v0.20.3, test cases TC-23.4-23.10): a copied cookie stops working after
log-out and after a password change; 8 idle hours end a login; other tills on the same account are not affected."""
from datetime import datetime, timedelta
from flask.sessions import SecureCookieSessionInterface
from helpers import check, finish, make_users, text
from app import app, upgrade_database
app.config['CSRF_ENABLED'] = False   # this file tests logins, not the form token (test_security does that)
from models import db, User

with app.app_context():
    db.drop_all(); upgrade_database(); make_users(db, User)

def login(user='admin', password='admin123'):
    client = app.test_client()
    client.post('/login', data={'username': user, 'password': password})
    return client
def copy_of(client):
    """A second browser holding a stolen copy of the first one's cookie."""
    thief = app.test_client(); thief.set_cookie('session', client.get_cookie('session').value)
    return thief
def can_open(client, page='/reports/sales'): return client.get(page).status_code == 200

# ---- TC-23.4 a copied cookie stops working after log-out
a = login(); thief = copy_of(a)
check('TC-23.4 setup: the copied cookie opens the Sales Report (that is how cookies work)', can_open(thief))
a.post('/logout')
check('TC-23.4 after the owner logs out, the copied cookie is refused (sent to log in)', not can_open(thief)
      and '/login' in thief.get('/reports/sales').headers.get('Location', ''))

# ---- TC-23.5 another till logged in as the same user is not affected by that log-out
till1, till2 = login('cashier', 'cashier123'), login('cashier', 'cashier123')
till1.post('/logout')
check('TC-23.5 two tills share "cashier": logging out on one leaves the other logged in', can_open(till2, '/sales/new'))

# ---- TC-23.6 a password change ends every OTHER login of that user
a = login(); thief = copy_of(a); other = login()
r = a.post('/profile/password', data={'current_password': 'admin123', 'new_password': 'NewPass#2026', 'confirm_password': 'NewPass#2026'}, follow_redirects=True)
check('TC-23.6 password changed; the message says other devices were logged out', 'Password changed' in text(r) and 'logged out' in text(r))
check('TC-23.6 the copied cookie is refused after the password change', not can_open(thief))
check('TC-23.6 another browser logged in as admin is logged out too', not can_open(other))
check('TC-23.6 the browser that changed the password stays logged in', can_open(a))

# ---- TC-23.7 a cookie signed with the REAL key but without a login from this server is refused
forged = SecureCookieSessionInterface().get_signing_serializer(app).dumps({'_user_id': '1', '_fresh': True})
f = app.test_client(); f.set_cookie('session', forged)
check('TC-23.7 a cookie made with the real secret key but no login record is refused', not can_open(f))

from models import LoginSession   # (v0.20.3) one row per logged-in browser
def age_logins(username, hours):
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        for row in LoginSession.query.filter_by(user_id=user.id):
            row.last_seen = datetime.now() - timedelta(hours=hours)
        db.session.commit()

# ---- TC-23.8 8 idle hours end a login; activity keeps it alive
k = login('cashier', 'cashier123'); k.post('/sales/new', data={'product_id': '999', 'quantity': '1'})
with k.session_transaction() as s: s['basket'] = {'1': 2}   # something left in the basket
age_logins('cashier', 7)
check('TC-23.8 7 idle hours: still logged in', can_open(k, '/sales/new'))
with app.app_context():
    seen = max(r.last_seen for r in LoginSession.query.all())
check('TC-23.8 ... and the visit counts as activity (last seen is now)', datetime.now() - seen < timedelta(minutes=1))
age_logins('cashier', 9)
check('TC-23.8 9 idle hours: logged out', not can_open(k, '/sales/new'))
with k.session_transaction() as s: left = dict(s)
check('TC-23.8 ... and the old basket is gone, so the next person starts fresh', 'basket' not in left)
app.config['CSRF_ENABLED'] = True   # the real way: the login page's own form token
page = text(k.get('/login'))
token = page.split('name="csrf_token" value="')[1].split('"')[0]
r = k.post('/login', data={'username': 'cashier', 'password': 'cashier123', 'csrf_token': token})
app.config['CSRF_ENABLED'] = False
check('TC-23.8 logging in again from the login page works (form token still valid)', r.status_code == 302 and can_open(k, '/sales/new'))

# ---- TC-23.9 the table stays small: log-out removes the row, old idle rows are cleaned at the next log-in
with app.app_context(): before = LoginSession.query.count()
k.post('/logout')
with app.app_context(): after = LoginSession.query.count()
check('TC-23.9 log-out deletes that browser\'s row', after == before - 1)
age_logins('admin', 30)
login('cashier', 'cashier123')
with app.app_context():
    admin = User.query.filter_by(username='admin').first()
    check('TC-23.9 rows idle for more than 8 hours are removed at the next log-in', LoginSession.query.filter_by(user_id=admin.id).count() == 0)

# ---- TC-23.10 the login record keeps nothing secret: only a random token, never the password
with app.app_context():
    row = LoginSession.query.first()
    check('TC-23.10 the token is 64 random hex characters; the password is not stored in it', len(row.token) == 64
          and all(ch in '0123456789abcdef' for ch in row.token) and 'cashier123' not in row.token)

finish('SESSIONS')
