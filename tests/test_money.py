"""Money stored as whole centavos (v0.23.2, DEF-68, audit R5, DEC-025), test cases TC-30.x.
Prices and totals are INTEGER centavos in the database (₱75.50 = 7550) and exact Decimal pesos in Python."""
import os
import sqlite3
from decimal import Decimal
from helpers import check, finish, make_users, text

from app import app, upgrade_database, MIGRATIONS_FOLDER
app.config['TEST_PLAIN_LOGIN'] = True   # v0.28.0: password-only login; this file isn't about the login code (DEC-030)
from models import db, User, Product, Sale, SaleItem, MenuOption
from alembic import command

app.config['CSRF_ENABLED'] = False

# ---- TC-30.6: migration 0003 turns money stored as decimals (REAL) into whole centavos, and back when undone
with app.app_context():
    config = app.extensions['migrate'].migrate.get_config(MIGRATIONS_FOLDER)
    command.upgrade(config, '0002')        # the database as v0.23.1 left it: money as REAL
    db.session.execute(db.text("INSERT INTO user (id, username, password_hash, role) VALUES (1, 'u', 'x', 'admin')"))
    db.session.execute(db.text("INSERT INTO product (id, name, sku, price, quantity, has_options) VALUES "
                               "(1, 'A', 'A1', 75.5, 1, 0), (2, 'B', 'B1', 19.99, 1, 0), (3, 'C', 'C1', 0.1, 1, 0)"))
    db.session.execute(db.text("INSERT INTO sale (id, created_at, user_id, total, cash_received, change_due, payment_method) "
                               "VALUES (1, '2026-10-20 01:15:00', 1, 95.59, 100, 4.41, 'cash')"))
    db.session.execute(db.text("INSERT INTO sale_item (sale_id, product_id, product_name, unit_price, quantity) VALUES (1, 2, 'B', 19.99, 1)"))
    db.session.execute(db.text("INSERT INTO menu_option (kind, name, price, active, sort_order, scale) VALUES ('addon', 'Oat', 40.5, 1, 1, 1)"))
    db.session.commit()
    upgrade_database()

    def raw(sql):
        return db.session.execute(db.text(sql)).fetchall()
    check('TC-30.6 migration 0003: product prices become whole centavos (7550, 1999, 10) (DEF-68)',
          raw('SELECT price FROM product ORDER BY id') == [(7550,), (1999,), (10,)])
    check('TC-30.6 ... and sale total, cash, change, item price and option price too',
          raw('SELECT total, cash_received, change_due FROM sale') == [(9559, 10000, 441)]
          and raw('SELECT unit_price FROM sale_item') == [(1999,)] and raw('SELECT price FROM menu_option') == [(4050,)])
    check('TC-30.6 they are stored as INTEGER, not REAL', raw("SELECT typeof(price) FROM product") == [('integer',)] * 3)
    check('TC-30.7 Python gets exact pesos back (Decimal 75.50, 19.99, 0.10)',
          [p.price for p in Product.query.order_by(Product.id)] == [Decimal('75.50'), Decimal('19.99'), Decimal('0.10')]
          and all(isinstance(p.price, Decimal) for p in Product.query))
    command.downgrade(config, '0002')
    check('TC-30.6 undoing 0003 gives back the old decimal amounts', raw('SELECT price FROM product ORDER BY id') == [(75.5,), (19.99,), (0.1,)])
    command.upgrade(config, 'head')

# ---- A clean shop for the rest
with app.app_context():
    db.drop_all(); upgrade_database(); make_users(db, User)
admin = app.test_client(); admin.post('/login', data={'username': 'admin', 'password': 'admin123'})
admin.post('/products/add', data={'name': 'Latte', 'sku': 'L1', 'price': '75.50', 'quantity': '50', 'category': 'Coffee'})
admin.post('/products/add', data={'name': 'Candy', 'sku': 'C1', 'price': '0.125', 'quantity': '50', 'category': 'Snacks'})
with app.app_context():
    stored = dict(db.session.execute(db.text('SELECT sku, price FROM product')).fetchall())
check('TC-30.1 a price typed as 75.50 is stored as 7550 centavos', stored.get('L1') == 7550)
check('TC-30.3 a price with three decimals (0.125) is rounded once, half up, to 13 centavos', stored.get('C1') == 13)

# ---- TC-30.3 every page then uses that one rounded price, so a receipt always adds up
admin.post('/sales/new', data={'product_id': '2', 'quantity': '3'})
r = admin.post('/sales/complete', data={'cash_received': '1'}, follow_redirects=True)
receipt = text(r)
check('TC-30.3 receipt: unit price ₱0.13, three of them ₱0.39 (before: ₱0.12 each but ₱0.38 for three)',
      '₱0.13' in receipt and '₱0.39' in receipt and '₱0.38' not in receipt)
with app.app_context():
    sale = Sale.query.first()
    check('TC-30.4 total, cash and change are exact: ₱0.39, ₱1.00, ₱0.61', (sale.total, sale.cash_received, sale.change_due) ==
          (Decimal('0.39'), Decimal('1.00'), Decimal('0.61')))
    check('TC-30.4 the total is exactly the sum of its lines', sale.total == sum(item.subtotal for item in sale.items))

# ---- TC-30.5 many small amounts add up exactly (floats drift: 0.1 added 1,000 times is 99.9999999999986)
with app.app_context():
    uid = User.query.filter_by(username='admin').first().id
    for _ in range(1000):
        s = Sale(user_id=uid, total='0.10', cash_received='0.10', change_due=0)
        s.items.append(SaleItem(product_id=1, product_name='Latte', unit_price='0.10', quantity=1))
        db.session.add(s)
    db.session.commit()
    exact = db.session.execute(db.text('SELECT SUM(total) FROM sale')).scalar()
    check('TC-30.5 1,000 sales of ₱0.10 sum to exactly 100.39 pesos in the database (10039 centavos)', exact == 10039)
report = text(admin.get('/reports/sales'))
check('TC-30.5 the report shows ₱100.39', '₱100.39' in report)

# ---- TC-30.8 limits and checks are unchanged
r = admin.post('/products/add', data={'name': 'Big', 'sku': 'B1', 'price': '1000000', 'quantity': '1', 'category': 'X'})
check('TC-30.8 a price of exactly ₱1,000,000 is still accepted', r.status_code == 302)
for bad in ['1000000.01', 'nan', 'inf', '-1', 'abc']:
    r = admin.post('/products/add', data={'name': 'Bad', 'sku': 'X' + bad, 'price': bad, 'quantity': '1', 'category': 'X'})
    check(f'TC-30.8 price "{bad}" is still refused', r.status_code == 200 and 'Bad' not in text(admin.get('/products')))
admin.post('/options', data={'kind': 'addon', 'name': 'Shot', 'price': '30.5'})
with app.app_context():
    option = MenuOption.query.filter_by(name='Shot').first()
    check('TC-30.8 an add-on price is stored in centavos too (₱30.50 = 3050)', option is not None and
          db.session.execute(db.text('SELECT price FROM menu_option WHERE id = :i'), {'i': option.id}).scalar() == 3050)

finish('MONEY')
