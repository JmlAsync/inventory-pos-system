"""After login, go back to the page the user first asked for (DEF-06, v0.20.6, test cases TC-5.8 and TC-24.1-24.4).
Only a page on this site is allowed, so a crafted link cannot send a user to another website."""
from helpers import check, finish, make_users
from app import app, upgrade_database
app.config['CSRF_ENABLED'] = False   # this file tests where login leads, not the form token
from models import db, User

with app.app_context():
    db.drop_all(); upgrade_database(); make_users(db, User)

def login_to(next_page, user='admin', password='admin123'):
    """Post the login form to /login?next=... and return where the server sends the browser."""
    url = '/login' + ('?next=' + next_page if next_page is not None else '')
    return app.test_client().post(url, data={'username': user, 'password': password}).headers.get('Location', '')

# A visitor who is not logged in is sent to /login?next=<the page they wanted>
r = app.test_client().get('/reports/sales')
check('TC-5.8 setup: an anonymous visitor to the Sales Report is sent to log in with ?next=', 'next=' in r.headers.get('Location', ''))
check('TC-5.8 after login the user lands on the page they asked for', login_to('/reports/sales').endswith('/reports/sales'))
check('TC-24.1 no next: the user lands on Products as before', login_to(None).endswith('/products'))
check('TC-24.2 next to another website is ignored (Products)', login_to('https://evil.example/').endswith('/products'))
check('TC-24.3 next "//evil.example" (same-scheme link to another site) is ignored', login_to('//evil.example').endswith('/products'))
check('TC-24.4 next with a backslash trick "/\evil.example" is ignored', login_to('/%5Cevil.example').endswith('/products'))
finish('LOGIN NEXT')
