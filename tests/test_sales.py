"""Process sale, cash and change, receipts and the basket (feature F7, test cases TC-7.x).
Starts from a v0.7.1 database (only the product and user tables) to prove the upgrade keeps the data."""
import os
import sqlite3
from werkzeug.security import generate_password_hash as g
from helpers import check, finish, text

os.makedirs('instance', exist_ok=True)
con = sqlite3.connect('instance/inventory.db')
con.executescript("""
CREATE TABLE product (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, sku VARCHAR(50) NOT NULL UNIQUE, price FLOAT NOT NULL, quantity INTEGER, category VARCHAR(50));
CREATE TABLE user (id INTEGER PRIMARY KEY, username VARCHAR(50) NOT NULL UNIQUE, password_hash VARCHAR(200) NOT NULL, role VARCHAR(20) NOT NULL);
INSERT INTO product VALUES (1,'Coke 1.5L','BEV-001',75.5,5,'Beverages');
INSERT INTO product VALUES (2,'Noodles','FD-001',15,10,'Food');
INSERT INTO product VALUES (3,'Soap','HH-001',30,0,'Household');
""")
con.execute("INSERT INTO user VALUES (1,'admin',?, 'admin')", (g('admin123'),))
con.execute("INSERT INTO user VALUES (2,'cashier',?, 'cashier')", (g('cashier123'),))
con.commit(); con.close()

from app import app, upgrade_database
from models import db, Product, Sale

app.config['CSRF_ENABLED'] = False
app.config['PROPAGATE_EXCEPTIONS'] = False
with app.app_context():
    upgrade_database()   # what "python app.py" does at start-up
    check('old database upgraded: sale tables added, 3 products kept',
          {'sale', 'sale_item'} <= set(db.inspect(db.engine).get_table_names()) and Product.query.count() == 3)

check('visitor is sent to log in for New Sale', app.test_client().get('/sales/new').status_code == 302)
c = app.test_client(); c.post('/login', data={'username': 'cashier', 'password': 'cashier123'})
h = text(c.get('/sales/new'))
check('cashier opens New Sale: empty basket, out-of-stock Soap not offered', 'basket is empty' in h and 'Soap' not in h)
check('Complete Sale with an empty basket: message', 'basket is empty' in text(c.post('/sales/complete')))
c.post('/sales/new', data={'product_id': '1', 'quantity': '2'})
c.post('/sales/new', data={'product_id': '2', 'quantity': '3'})
c.post('/sales/new', data={'product_id': '1', 'quantity': '1'})
check('adding the same product again joins its line; total ₱271.50', '₱271.50' in text(c.get('/sales/new')))
check('more than the stock refused ("only 2 more")', 'only 2 more can be added' in text(c.post('/sales/new', data={'product_id': '1', 'quantity': '3'})))
for qty in ['0', '-2', 'abc']:
    check(f'quantity "{qty}" refused', 'at least 1' in text(c.post('/sales/new', data={'product_id': '2', 'quantity': qty})))
check('no product chosen: message', 'choose a product' in text(c.post('/sales/new', data={'product_id': '', 'quantity': '1'})))
check('product that does not exist: message', 'choose a product' in text(c.post('/sales/new', data={'product_id': '999', 'quantity': '1'})))
check('out-of-stock product sent by a crafted form refused', 'only 0 more can be added' in text(c.post('/sales/new', data={'product_id': '3', 'quantity': '1'})))

# Stock drops between adding and completing
with app.app_context():
    db.session.get(Product, 2).quantity = 2; db.session.commit()
check('stock dropped before Complete Sale: refused', 'no longer has enough stock' in text(c.post('/sales/complete', data={'cash_received': '1000'})))
with app.app_context():
    check('nothing saved, Coke stock untouched', Sale.query.count() == 0 and db.session.get(Product, 1).quantity == 5)
c.post('/sales/remove/2')
check('removing a product that is not in the basket is harmless', c.post('/sales/remove/77').status_code == 302)
check('cash below the total refused', 'at least ₱226.50' in text(c.post('/sales/complete', data={'cash_received': '200'})))
check('cash "abc" refused', 'at least' in text(c.post('/sales/complete', data={'cash_received': 'abc'})))
check('cash missing refused', 'at least' in text(c.post('/sales/complete', data={})))
r = c.post('/sales/complete', data={'cash_received': '500'})
check('Complete Sale with enough cash opens the receipt', r.status_code == 302 and '/sales/' in r.headers['Location'])
receipt = r.headers['Location']
h = text(c.get(receipt))
check('receipt: total, cash, change, item, cashier, print button',
      all(s in h for s in ['₱226.50', '₱500.00', '₱273.50', 'Coke 1.5L', 'cashier', 'window.print()']))
with app.app_context():
    s = Sale.query.first()
    check('sale saved with the right numbers', (s.total, s.cash_received, s.change_due, s.user.username) == (226.5, 500.0, 273.5, 'cashier'))
    check('one receipt line: Coke × 3 at ₱75.50', [(i.product_name, i.quantity, i.unit_price) for i in s.items] == [('Coke 1.5L', 3, 75.5)])
    check('Coke stock 5 - 3 = 2', db.session.get(Product, 1).quantity == 2)
check('basket is empty after the sale', 'basket is empty' in text(c.get('/sales/new')))
check('receipt that does not exist: 404', c.get('/sales/999').status_code == 404)
check('Complete Sale by plain link (GET) not allowed: 405', c.get('/sales/complete').status_code == 405)

# The admin can sell too; old receipts never change
a = app.test_client(); a.post('/login', data={'username': 'admin', 'password': 'admin123'})
a.post('/sales/new', data={'product_id': '1', 'quantity': '2'})
check('admin can complete a sale', a.post('/sales/complete', data={'cash_received': '151'}).status_code == 302)
check('product with 0 stock is not offered', 'Coke' not in text(a.get('/sales/new')))
a.post('/products/edit/1', data={'name': 'Coke 1.5L NEW', 'sku': 'BEV-001', 'price': '99', 'quantity': '10', 'category': 'Beverages'})
h = text(c.get(receipt))
check('renaming / repricing a product does not change old receipts', 'Coke 1.5L' in h and 'NEW' not in h and '₱75.50' in h)
a.post('/products/delete/1')
check('a sold product cannot be deleted, so its receipt still works (DEF-21)', 'Coke 1.5L' in text(c.get(receipt)))

# Each browser has its own basket; logging out empties it (DEF-09)
c2 = app.test_client(); c2.post('/login', data={'username': 'cashier', 'password': 'cashier123'})
c2.post('/sales/new', data={'product_id': '2', 'quantity': '1'})
check("another browser's basket is separate", 'basket is empty' in text(a.get('/sales/new')))
c2.post('/logout'); c2.post('/login', data={'username': 'admin', 'password': 'admin123'})
check('after log out the next user sees an empty basket (DEF-09)', 'basket is empty' in text(c2.get('/sales/new')))

c.post('/sales/new', data={'product_id': '2', 'quantity': '1'})
h = text(c.get('/sales/new'))
check('cash box and live change preview are on the page', 'name="cash_received"' in h and 'change_preview' in h)
c.post('/sales/complete', data={'cash_received': '15'})
with app.app_context():
    s = Sale.query.order_by(Sale.id.desc()).first()
    check('exact cash: change ₱0', (s.total, s.cash_received, s.change_due) == (15.0, 15.0, 0.0))
check('menu is hidden when printing', 'd-print-none' in text(c.get('/')))

# The list shows stock minus what is already in this basket (DEF-10)
with app.app_context():
    db.session.get(Product, 2).quantity = 10; db.session.commit()
d = app.test_client(); d.post('/login', data={'username': 'cashier', 'password': 'cashier123'})
check('list shows "10 available"', '10 available' in text(d.get('/sales/new')))
d.post('/sales/new', data={'product_id': '2', 'quantity': '3'})
h = text(d.get('/sales/new'))
with app.app_context():
    check('after adding 3: "7 available", database still 10', '7 available' in h and db.session.get(Product, 2).quantity == 10)
d.post('/sales/new', data={'product_id': '2', 'quantity': '7'})
h = text(d.get('/sales/new'))
check('all 10 in the basket: gone from the list, still in the basket', 'Noodles (' not in h and 'product-name">Noodles</span>' in h)
check('adding 1 more refused', 'only 0 more can be added' in text(d.post('/sales/new', data={'product_id': '2', 'quantity': '1'})))
d.post('/sales/remove/2')
check('after removing: "10 available" again', '10 available' in text(d.get('/sales/new')))
finish('SALES')
