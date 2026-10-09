"""Cash and GCash payments (feature F14, v0.15.0, test cases TC-15.x). Starts from a v0.14 database."""
import os, sqlite3
from helpers import check, finish, text, fixture
os.makedirs('instance', exist_ok=True)
c = sqlite3.connect('instance/inventory.db'); c.executescript("""
CREATE TABLE user (id INTEGER PRIMARY KEY, username VARCHAR(80) NOT NULL UNIQUE, password_hash VARCHAR(200) NOT NULL, role VARCHAR(20) NOT NULL);
CREATE TABLE product (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, sku VARCHAR(50) NOT NULL UNIQUE, price FLOAT NOT NULL, quantity INTEGER, category VARCHAR(50));
CREATE TABLE sale (id INTEGER PRIMARY KEY, created_at DATETIME NOT NULL, user_id INTEGER NOT NULL, total FLOAT NOT NULL);
CREATE TABLE sale_item (id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL, product_id INTEGER NOT NULL, product_name VARCHAR(100) NOT NULL, unit_price FLOAT NOT NULL, quantity INTEGER NOT NULL);
INSERT INTO product VALUES (1,'Sea Salt','D1',180,20,'Coffee');
INSERT INTO sale VALUES (1,'2026-10-01 10:00:00',1,180);
INSERT INTO sale_item VALUES (1,1,1,'Sea Salt',180,1);"""); c.commit(); c.close()
from app import app, upgrade_database
app.config['CSRF_ENABLED'] = False
from models import db, User, Product, Sale
from werkzeug.security import generate_password_hash as g
from sqlalchemy.exc import IntegrityError
with app.app_context():
    upgrade_database()
    cols = [col['name'] for col in db.inspect(db.engine).get_columns('sale')]
    check('old database: payment columns added', 'payment_method' in cols and 'payment_reference' in cols)
    check('old sales count as cash', db.session.get(Sale, 1).payment_method == 'cash')
    db.session.add(User(id=1, username='cashier', password_hash=g('c'), role='cashier'))
    db.session.add(User(id=2, username='admin', password_hash=g('a'), role='admin')); db.session.commit()
c = app.test_client(); c.post('/login', data={'username': 'cashier', 'password': 'c'})
def stock():
    with app.app_context(): return db.session.get(Product, 1).quantity
def last():
    with app.app_context():
        s = Sale.query.order_by(Sale.id.desc()).first(); return (s.id, s.payment_method, s.payment_reference, s.cash_received, s.change_due, s.total)
def sell(data):
    c.post('/sales/new', data={'product_id': '1', 'quantity': '2'})
    return c.post('/sales/complete', data=data)
r = sell({'cash_received': '400'})
check('cash sale without choosing a method still works (old form)', r.status_code == 302 and last()[1:] == ('cash', None, 400.0, 40.0, 360.0))
before = stock()
r = sell({'payment_method': 'gcash', 'gcash_reference': '1234 567 890123'})
sid = last()[0]
check('GCash with spaces: saved as 13 digits, exact amount, no change', r.status_code == 302 and last()[1:] == ('gcash', '1234567890123', 360.0, 0.0, 360.0))
check('GCash sale deducts stock', stock() == before - 2)
h = c.get(f'/sales/{sid}').get_data(as_text=True)
check('receipt: "Paid by GCash" + reference, no Change line', 'Paid by GCash' in h and '1234567890123' in h and '>Change<' not in h)
c.post('/sales/new', data={'product_id': '1', 'quantity': '2'})   # basket for the refused attempts below
for bad, why in [('123456789012', '12 digits'), ('12345678901234', '14 digits'), ('12345678901ab', 'letters'), ('١٢٣٤٥٦٧٨٩٠١٢٣', 'Arabic digits'), ('', 'empty')]:
    n0 = last()[0]; s0 = stock()
    r = c.post('/sales/complete', data={'payment_method': 'gcash', 'gcash_reference': bad})
    check(f'GCash reference refused ({why}); nothing saved', '13 digits' in r.get_data(as_text=True) and last()[0] == n0 and stock() == s0)
r = c.post('/sales/complete', data={'payment_method': 'gcash', 'gcash_reference': '1234567890123'})
check('same reference twice refused, names the first receipt', f'already used on receipt #{sid}' in r.get_data(as_text=True))
r = c.post('/sales/complete', data={'payment_method': 'card', 'cash_received': '999'})
check('unknown method refused', 'Cash or GCash' in r.get_data(as_text=True))
r = c.post('/sales/complete', data={'payment_method': 'gcash', 'gcash_reference': '9999999999999', 'cash_received': 'abc'})
check('GCash ignores a junk cash box', r.status_code == 302 and last()[1] == 'gcash')
c.post('/sales/new', data={'product_id': '1', 'quantity': '1'})
r = c.post('/sales/complete', data={'payment_method': 'cash', 'cash_received': '100'})
check('cash below total still refused', 'at least' in r.get_data(as_text=True))
c.post('/sales/remove/1')
with app.app_context():
    db.session.add_all([Sale(user_id=1, total=1, payment_method='gcash', payment_reference='5555555555555'),
                        Sale(user_id=1, total=1, payment_method='gcash', payment_reference='5555555555555')])
    try: db.session.commit(); dup = False
    except IntegrityError: db.session.rollback(); dup = True
check('database itself refuses a duplicate reference (two sales at once)', dup)
with app.app_context():
    db.session.add_all([Sale(user_id=1, total=1), Sale(user_id=1, total=1)]); db.session.commit()
check('many cash sales without a reference are fine', True)
h = c.get('/sales/1').get_data(as_text=True)
check('pre-v0.8 receipt still says "not recorded"', 'not recorded' in h)
a = app.test_client(); a.post('/login', data={'username': 'admin', 'password': 'a'})
h = a.get('/reports/sales?start=2026-01-01&end=2026-12-31').get_data(as_text=True)
check('report splits revenue: cash and GCash', 'GCash ₱720.00' in h and 'Paid by' in h and '>GCash</td>' in h)
finish('PAYMENT')
