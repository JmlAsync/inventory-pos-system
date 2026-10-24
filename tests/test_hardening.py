"""Phase 1 hardening patches (v0.21.3 onward), test cases TC-26.x: small fixes from the security audit
and the report's known limitations, one per version (docs/upgrade_plan.md, Phase 1)."""
from helpers import check, finish, make_users, text
from app import app
from models import db, User, Product

app.config['CSRF_ENABLED'] = False
with app.app_context():
    db.drop_all(); db.create_all(); make_users(db, User)
    db.session.add(Product(name='Latte', sku='L1', price=150, quantity=10)); db.session.commit()


# ---- v0.21.3 (DEF-61, audit A11): a crash shows a friendly page, not the plain "Internal Server Error"
def crash():
    raise RuntimeError('secret detail that must not reach the browser')


# A pretend page that always crashes, added only inside this test (the real app has no such page)
app.add_url_rule('/test-crash', 'test_crash', crash)
admin = app.test_client(); admin.post('/login', data={'username': 'admin', 'password': 'admin123'})
r = admin.get('/test-crash')
page = text(r)
check('TC-26.1 a crash still answers 500 (the browser and logs know it failed)', r.status_code == 500)
check('TC-26.1 the 500 page is the friendly one, in the normal layout (DEF-61)', 'Something went wrong' in page and 'app-sidebar' in page)
check('TC-26.2 the page says what to do next, in plain words (C6)', 'Nothing was saved' in page and 'try again' in page)
check('TC-26.3 no error details or code reach the browser', 'secret detail' not in page and 'Traceback' not in page and 'RuntimeError' not in page)
check('TC-26.4 the app keeps working after a crash', admin.get('/products').status_code == 200)
check('TC-26.4 a visitor also gets the friendly page', 'Something went wrong' in text(app.test_client().get('/test-crash')))


# ---- v0.21.4 (DEF-62, audit A8): an unknown username takes as long as a wrong password
import app as app_module
hash_checks = []
real_check = app_module.check_password_hash


def counting_check(stored, password):
    hash_checks.append(stored)
    return real_check(stored, password)


app_module.check_password_hash = counting_check
app.test_client().post('/login', data={'username': 'nobody-here', 'password': 'whatever'})
check('TC-26.5 an unknown username still checks a password hash (same time as a real user, DEF-62)', len(hash_checks) == 1)
check('TC-26.5 that hash is made the same slow way as real ones (scrypt)', bool(hash_checks) and hash_checks[0].startswith('scrypt:'))
hash_checks.clear()
r = app.test_client().post('/login', data={'username': 'nobody-here', 'password': 'whatever'})
check('TC-26.6 the message is the same as for a wrong password', 'Invalid username or password' in text(r))
c = app.test_client(); c.post('/login', data={'username': 'admin', 'password': 'wrong'})
check('TC-26.6 a real user with a wrong password: one hash check, as before', len(hash_checks) == 2)
r = app.test_client().post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=False)
check('TC-26.7 the right password still logs in', r.status_code == 302)
app_module.check_password_hash = real_check

finish('HARDENING')
