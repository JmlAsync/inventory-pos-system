"""Shop details on receipts and "This is not an official receipt" (feature F21, v0.22.0), test cases TC-27.x.
SR6 in the report: the receipt must never look like an official sales invoice."""
from helpers import check, finish, make_users, text
from app import app, upgrade_database
from models import db, User, Product, Sale, SaleItem

app.config['CSRF_ENABLED'] = False
with app.app_context():
    db.drop_all(); upgrade_database(); make_users(db, User)
    db.session.add(Product(name='Latte', sku='L1', price=150, quantity=10)); db.session.commit()
    cashier_id = User.query.filter_by(username='cashier').first().id
    sale = Sale(user_id=cashier_id, total=150, cash_received=200, change_due=50)
    sale.items.append(SaleItem(product_id=1, product_name='Latte', unit_price=150, quantity=1))
    db.session.add(sale); db.session.commit()

admin = app.test_client(); admin.post('/login', data={'username': 'admin', 'password': 'admin123'})
cashier = app.test_client(); cashier.post('/login', data={'username': 'cashier', 'password': 'cashier123'})

# ---- The notice is always there (SR6)
receipt = text(cashier.get('/sales/1'))
check('TC-27.1 every receipt says "This is not an official receipt." (SR6)', 'This is not an official receipt.' in receipt)
check('TC-27.1 before any details are set, the receipt uses the default name', 'Inventory &amp; POS' in receipt)

# ---- Who may change the details
check('TC-27.2 a visitor is sent to the login page', app.test_client().get('/settings/shop').status_code == 302)
check('TC-27.2 a cashier gets 403 on the page (S2, C4)', cashier.get('/settings/shop').status_code == 403)
r = cashier.post('/settings/shop', data={'name': 'Hacked Café'})
check('TC-27.2 a cashier gets 403 when sending the form', r.status_code == 403)
check('TC-27.2 the admin can open the page', admin.get('/settings/shop').status_code == 200)
check('TC-27.2 the admin sidebar links to it', '/settings/shop' in text(admin.get('/products')) and '/settings/shop' not in text(cashier.get('/products')))

# ---- Saving and showing the details
r = admin.post('/settings/shop', data={'name': 'Kapehan sa Kanto', 'address': '12 Rizal St., Quezon City',
                                       'tin': '123-456-789-00000', 'footer': 'Thank you! See you again.'}, follow_redirects=True)
check('TC-27.3 valid details are saved with a message', 'Shop details saved' in text(r))
receipt = text(cashier.get('/sales/1'))
check('TC-27.4 the receipt shows the shop name, address, TIN and footer',
      all(s in receipt for s in ['Kapehan sa Kanto', '12 Rizal St., Quezon City', 'TIN: 123-456-789-00000', 'Thank you! See you again.']))
check('TC-27.4 the notice is still there after the details are set', 'This is not an official receipt.' in receipt)
check('TC-27.4 the old fixed name is gone from the receipt', 'Inventory &amp; POS</h1>' not in receipt)

# ---- Checks on every value (S7) with plain messages (C6)
bad = [({'name': '   '}, 'Shop name is required'),
       ({'name': 'x' * 61}, 'Shop name can be at most 60 characters'),
       ({'name': 'Cafe', 'address': 'x' * 121}, 'Address can be at most 120 characters'),
       ({'name': 'Cafe', 'tin': '12345'}, 'TIN must have 9 to 14 digits'),
       ({'name': 'Cafe', 'tin': 'abc-def-ghi'}, 'TIN must have 9 to 14 digits'),
       ({'name': 'Cafe', 'footer': 'x' * 121}, 'Footer can be at most 120 characters')]
for data, message in bad:
    r = admin.post('/settings/shop', data=data)
    check(f'TC-27.5 refused with "{message}"', r.status_code == 200 and message in text(r))
check('TC-27.5 nothing changed after the refused forms', 'Kapehan sa Kanto' in text(cashier.get('/sales/1')))

# ---- Typed text is shown as text, never run (S11)
admin.post('/settings/shop', data={'name': '<script>alert(1)</script>', 'footer': '<b>bold</b>'})
receipt = text(cashier.get('/sales/1'))
check('TC-27.6 a name with HTML is shown as plain text', '<script>alert(1)</script>' not in receipt and '&lt;script&gt;' in receipt)
admin.post('/settings/shop', data={'name': 'Kapehan sa Kanto', 'tin': ''})
check('TC-27.7 TIN left empty: no TIN line on the receipt', 'TIN:' not in text(cashier.get('/sales/1')))

# ---- An existing database gets the new table at start-up (I5)
with app.app_context():
    # A database from before v0.23.0 has no shop_profile table and no migration record (alembic_version)
    db.session.execute(db.text('DROP TABLE shop_profile')); db.session.execute(db.text('DROP TABLE IF EXISTS alembic_version'))
    db.session.commit()
    upgrade_database()
    check('TC-27.8 an older database gets the shop_profile table at start-up, nothing lost',
          db.inspect(db.engine).has_table('shop_profile') and Sale.query.count() == 1)
# v0.23.1: a real older database stores local times, which migration 0002 turns into UTC. This made-up one already
# has UTC login times, so 0002 shifts them by this computer's offset and the login may look idle: log in again.
cashier = app.test_client(); cashier.post('/login', data={'username': 'cashier', 'password': 'cashier123'})
check('TC-27.8 and the receipt still opens with the default name and the notice',
      'This is not an official receipt.' in text(cashier.get('/sales/1')))

finish('SHOP DETAILS')
