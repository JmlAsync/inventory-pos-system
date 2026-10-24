"""The owner, the Users page, switching accounts off, "Require a new password" and the audit log (v0.27.0, F24,
DEC-029), test cases TC-35.x. Who may do what is rule S15; every refusal is a 403 from the server (rule S2)."""
import json
import os
import subprocess
import sys
from datetime import timedelta
from helpers import check, finish, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash as g

from app import app, upgrade_database, MIGRATIONS_FOLDER
from models import db, User, Product, AuditEntry, utc_now
from alembic import command

app.config['CSRF_ENABLED'] = False


def columns(table):
    return {c['name'] for c in db.inspect(db.engine).get_columns(table)}


# ---- TC-35.1 migration 0005: new columns and tables; existing accounts keep working; can be undone
with app.app_context():
    db.drop_all(); upgrade_database()
    config = app.extensions['migrate'].migrate.get_config(MIGRATIONS_FOLDER)
    command.downgrade(config, '0004'); db.session.remove()
    db.session.execute(db.text("INSERT INTO user (id, username, password_hash, role) VALUES (1, 'old', :h, 'admin')"),
                       {'h': g('old-password-1')}); db.session.commit()
    command.upgrade(config, 'head'); db.session.remove()
    tables = set(db.inspect(db.engine).get_table_names())
    check('TC-35.1 migration 0005 adds email, switched-on, must-change, may-invite and created-at to user',
          {'email', 'email_verified_at', 'is_active', 'must_change_password', 'can_invite', 'created_at'} <= columns('user'))
    check('TC-35.1 ... and the invitation, email_code and audit_log tables', {'invitation', 'email_code', 'audit_log'} <= tables)
    old = db.session.get(User, 1)
    check('TC-35.1 an account from before is still an admin, switched on, with no flags and no email',
          old.role == 'admin' and old.is_active and not old.must_change_password and not old.can_invite and old.email is None)
    command.downgrade(config, '0004'); db.session.remove()
    check('TC-35.1 undoing 0005 removes it all again, keeping the account',
          'email' not in columns('user') and 'invitation' not in set(db.inspect(db.engine).get_table_names())
          and db.session.execute(db.text('SELECT username FROM user')).scalar() == 'old')
    command.upgrade(config, 'head'); db.session.remove()

# ---- A shop: owner, two admins (one may invite), two cashiers
with app.app_context():
    db.drop_all(); upgrade_database()
    now = utc_now()
    db.session.add_all([
        User(username='olivia', password_hash=g('owner-pass-1'), role='owner', email='olivia@example.com', email_verified_at=now),
        User(username='adam', password_hash=g('admin-pass-1'), role='admin'),
        User(username='ana', password_hash=g('admin-pass-2'), role='admin', can_invite=True),
        User(username='cara', password_hash=g('cashier-pass-1'), role='cashier'),
        User(username='carl', password_hash=g('cashier-pass-2'), role='cashier')])
    db.session.commit()
    ID = {u.username: u.id for u in User.query}

    # ---- TC-35.2 the database allows one owner only
    db.session.add(User(username='second', password_hash='x', role='owner'))
    try:
        db.session.commit(); two_owners = True
    except IntegrityError:
        db.session.rollback(); two_owners = False
    check('TC-35.2 a second owner is refused by the database itself', not two_owners)


def client(username, password):
    c = app.test_client()
    c.post('/login', data={'username': username, 'password': password})
    return c


def user(name):
    with app.app_context():
        return User.query.filter_by(username=name).first()


owner, adam, ana = client('olivia', 'owner-pass-1'), client('adam', 'admin-pass-1'), client('ana', 'admin-pass-2')
cara = client('cara', 'cashier-pass-1')

# ---- TC-35.3 the owner can do everything an admin can; a cashier gets 403 everywhere here
check('TC-35.3 the owner opens admin pages (Add product, Users, Audit log)',
      all(owner.get(p).status_code == 200 for p in ['/products/add', '/admin/users', '/admin/audit']))
check('TC-35.3 the owner sees the admin part of the sidebar with Users and Audit log',
      'href="/admin/users"' in text(owner.get('/products')) and 'href="/admin/audit"' in text(owner.get('/products')))
cashier_pages = [('get', '/admin/users'), ('get', '/admin/audit'), ('post', '/admin/users/invite'),
                 ('post', f'/admin/users/{ID["carl"]}/role'), ('post', f'/admin/users/{ID["carl"]}/active'),
                 ('post', f'/admin/users/{ID["carl"]}/require-password'), ('post', f'/admin/users/{ID["adam"]}/may-invite'),
                 ('post', '/admin/invitations/1/resend'), ('post', '/admin/invitations/1/cancel')]
check('TC-35.3 a cashier gets 403 on Users, Audit log and every Users button (S15)',
      all(getattr(cara, how)(path, data={'role': 'admin', 'active': '0', 'allowed': '1', 'email': 'x@example.com'})
          .status_code == 403 for how, path in cashier_pages))
check('TC-35.3 ... and nothing changed', user('carl').role == 'cashier' and user('carl').is_active and not user('adam').can_invite)

# ---- TC-35.4 an admin manages cashiers only, and invites only if the owner allowed it
page = text(adam.get('/admin/users'))
check('TC-35.4 an admin without "may invite" sees no invite form', 'Only the owner, or an admin the owner allowed' in page
      and 'action="/admin/users/invite"' not in page)
check('TC-35.4 ... and posting it anyway is refused (403)',
      adam.post('/admin/users/invite', data={'email': 'x@example.com', 'role': 'cashier'}).status_code == 403)
check('TC-35.4 an admin allowed to invite may invite cashiers but not admins (403)',
      ana.post('/admin/users/invite', data={'email': 'x@example.com', 'role': 'admin'}).status_code == 403)
check('TC-35.4 an admin can\'t change roles or give "may invite" (403)',
      adam.post(f'/admin/users/{ID["carl"]}/role', data={'role': 'admin'}).status_code == 403
      and adam.post(f'/admin/users/{ID["adam"]}/may-invite', data={'allowed': '1'}).status_code == 403)
check('TC-35.4 an admin can\'t switch off another admin, themselves, or the owner (403)',
      all(adam.post(f'/admin/users/{ID[name]}/active', data={'active': '0'}).status_code == 403
          for name in ['ana', 'adam', 'olivia']))
check('TC-35.4 ... and nobody can switch off the owner, not even the owner (403)',
      owner.post(f'/admin/users/{ID["olivia"]}/active', data={'active': '0'}).status_code == 403 and user('olivia').is_active)
check('TC-35.4 the buttons match: the admin sees "Switch off" for cashiers only', page.count('Switch off') == 2)

# ---- TC-35.5 the owner changes roles; the owner role can't be given or taken here
r = owner.post(f'/admin/users/{ID["carl"]}/role', data={'role': 'admin'}, follow_redirects=True)
check('TC-35.5 the owner makes a cashier an admin', 'carl is now an admin' in text(r) and user('carl').role == 'admin')
owner.post(f'/admin/users/{ID["ana"]}/role', data={'role': 'cashier'})
check('TC-35.5 an admin made a cashier loses "may invite"', user('ana').role == 'cashier' and not user('ana').can_invite)
check('TC-35.5 "owner" can\'t be given, and the owner\'s own role can\'t be changed (403)',
      owner.post(f'/admin/users/{ID["carl"]}/role', data={'role': 'owner'}).status_code == 403
      and owner.post(f'/admin/users/{ID["olivia"]}/role', data={'role': 'cashier'}).status_code == 403
      and user('olivia').role == 'owner')
owner.post(f'/admin/users/{ID["carl"]}/role', data={'role': 'cashier'})
owner.post(f'/admin/users/{ID["ana"]}/role', data={'role': 'admin'})
r = owner.post(f'/admin/users/{ID["adam"]}/may-invite', data={'allowed': '1'}, follow_redirects=True)
check('TC-35.5 the owner lets an admin invite cashiers', 'adam may invite cashiers' in text(r) and user('adam').can_invite)
check('TC-35.5 "may invite" is only for admins (403 for a cashier)',
      owner.post(f'/admin/users/{ID["carl"]}/may-invite', data={'allowed': '1'}).status_code == 403)

# ---- TC-35.6 switching off: logged out at once, can't log in, never deleted; switching on again
carl = client('carl', 'cashier-pass-2')
check('TC-35.6 (before) carl is logged in', carl.get('/sales/new').status_code == 200)
r = adam.post(f'/admin/users/{ID["carl"]}/active', data={'active': '0'}, follow_redirects=True)
check('TC-35.6 an admin switches a cashier off', 'carl is switched off' in text(r) and not user('carl').is_active)
check('TC-35.6 carl\'s open login ends at once', carl.get('/sales/new').status_code == 302)
r = app.test_client().post('/login', data={'username': 'carl', 'password': 'cashier-pass-2'})
check('TC-35.6 the right password now says the account is switched off (403)',
      r.status_code == 403 and 'switched off' in text(r))
check('TC-35.6 the account still exists (receipts name their cashier)', user('carl') is not None)
check('TC-35.6 the Users page shows "Switched off" and "Switch on"', 'Switched off' in text(adam.get('/admin/users')))
adam.post(f'/admin/users/{ID["carl"]}/active', data={'active': '1'})
check('TC-35.6 switched on again, carl can log in', client('carl', 'cashier-pass-2').get('/sales/new').status_code == 200)

# ---- TC-35.7 "Require a new password" (audit A5)
owner.post(f'/admin/users/{ID["cara"]}/require-password')
check('TC-35.7 every page sends cara to Choose a new password',
      all(cara.get(p).headers.get('Location', '').endswith('/password/new') for p in ['/', '/products', '/sales/new', '/profile']))
check('TC-35.7 ... the page itself opens, and logging out still works',
      cara.get('/password/new').status_code == 200 and 'Log out instead' in text(cara.get('/password/new')))
r = cara.post('/password/new', data={'current_password': 'wrong', 'new_password': 'Kape-2026-new', 'confirm_password': 'Kape-2026-new'})
check('TC-35.7 the current password is asked (a stolen login can\'t choose one)', 'Current password is wrong' in text(r))
r = cara.post('/password/new', data={'current_password': 'cashier-pass-1', 'new_password': 'short', 'confirm_password': 'short'})
check('TC-35.7 the usual password rules apply', 'at least 8' in text(r))
r = cara.post('/password/new', data={'current_password': 'cashier-pass-1', 'new_password': 'Kape-2026-new',
                                     'confirm_password': 'Kape-2026-new'}, follow_redirects=True)
check('TC-35.7 a good one is saved and the flag is cleared', 'Password changed' in text(r) and not user('cara').must_change_password)
check('TC-35.7 ... pages open normally again, with the new password', cara.get('/sales/new').status_code == 200
      and client('cara', 'Kape-2026-new').get('/sales/new').status_code == 200)

# ---- TC-35.8 the audit log: who changed what, old and new values
owner.post('/products/add', data={'name': 'Latte', 'sku': 'L1', 'price': '150', 'quantity': '20', 'category': 'Coffee'})
with app.app_context():
    latte = Product.query.filter_by(sku='L1').first().id
adam.post(f'/products/edit/{latte}', data={'name': 'Latte', 'sku': 'L1', 'price': '160', 'quantity': '18', 'category': 'Coffee'})
adam.post(f'/products/edit/{latte}', data={'name': 'Latte', 'sku': 'L1', 'price': '160', 'quantity': '18', 'category': 'Coffee'})
adam.post('/settings/shop', data={'name': 'Sample Café', 'address': '', 'tin': '', 'footer': ''})
owner.post('/products/add', data={'name': 'Gone', 'sku': 'G1', 'price': '10', 'quantity': '1', 'category': 'Snacks'})
with app.app_context():
    gone = Product.query.filter_by(sku='G1').first().id
owner.post(f'/products/delete/{gone}')
with app.app_context():
    lines = [(e.user.username if e.user else None, e.action, e.target, json.loads(e.details)) for e in AuditEntry.query.order_by(AuditEntry.id)]
    actions = [line[1] for line in lines]
updates = [line for line in lines if line[1] == 'product.update']
check('TC-35.8 a product added by the owner is logged with its values',
      any(l[0] == 'olivia' and l[1] == 'product.add' and l[3].get('price') == ['', '150.00'] for l in lines))
check('TC-35.8 a price and stock change by an admin: who, old and new values',
      len(updates) == 1 and updates[0][0] == 'adam' and updates[0][3] == {'price': ['150.00', '160.00'], 'quantity': ['20', '18']})
check('TC-35.8 saving without changing anything adds no line', len(updates) == 1)
check('TC-35.8 shop details, a deleted product and account changes are logged too',
      'shop.update' in actions and 'product.delete' in actions
      and {'user.role', 'user.switch-off', 'user.switch-on', 'user.require-password', 'user.may-invite', 'user.password-chosen'} <= set(actions))
page = text(owner.get('/admin/audit'))
check('TC-35.8 the Audit log page shows who and the change in words', 'adam' in page and 'Price' in page and '150.00' in page and '160.00' in page)
page = text(owner.get('/admin/audit?area=user'))
check('TC-35.8 filtered to Accounts: no product lines', 'Price' not in page and 'role changed' in page)
page = text(owner.get(f'/admin/audit?who={ID["adam"]}'))
check('TC-35.8 filtered to one person: only their lines', 'Sample Café' in page and 'Gone (G1)' not in page)
with app.app_context():
    for i in range(60):
        db.session.add(AuditEntry(user_id=ID['olivia'], action='product.update', target=f'Test {i}', details='{}'))
    db.session.commit()
page = text(owner.get('/admin/audit'))
check('TC-35.8 50 lines a page, with a link to older ones', page.count('<tr>') == 51 and 'page=2' in page)
check('TC-35.8 a page number that is far too big is harmless', owner.get('/admin/audit?page=99999999999').status_code == 200)

# ---- TC-35.9 setup_shop.py on a database without an owner (an older shop): an admin becomes the owner
with app.app_context():
    db.drop_all(); upgrade_database()
    db.session.add_all([User(username='admin', password_hash=g('admin123'), role='admin'),
                        User(username='cashier', password_hash=g('cashier123'), role='cashier')]); db.session.commit()


def setup(username, email='maria@example.com'):
    answers = {'network': {'other_devices': False, 'port': 5000}, 'shop': {'name': 'Sample Café'},
               'admin': {'username': username, 'password': 'a-long-password-1', 'email': email}}
    with open('answers.json', 'w', encoding='utf-8') as f:
        json.dump(answers, f)
    return subprocess.run([sys.executable, 'setup_shop.py', '--answers', 'answers.json'], capture_output=True,
                          text=True, encoding='utf-8', errors='replace')


r = setup('cashier')
check('TC-35.9 a cashier can\'t be made the owner: setup stops and says why', r.returncode == 1 and 'is not an admin' in r.stdout)
r = setup('admin')
admin_now = user('admin')
check('TC-35.9 the existing admin becomes the owner, with the email, password unchanged',
      r.returncode == 0 and admin_now.role == 'owner' and admin_now.email == 'maria@example.com'
      and admin_now.email_verified_at is None and 'is now the owner' in r.stdout)
r = setup('someone-new', 'other@example.com')
check('TC-35.9 a later run leaves the owner as it is', r.returncode == 0 and 'left as it is' in r.stdout
      and user('someone-new') is None and user('admin').role == 'owner')
with app.app_context():
    made = AuditEntry.query.filter_by(action='user.owner').first()
check('TC-35.9 the audit log says the owner was made by setup on the computer', made is not None and made.user_id is None)
os.remove('answers.json')

finish('USERS')
