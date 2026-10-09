"""Servings (Hot / Iced) and add-ons (feature F15, v0.16.x, test cases TC-16.x). Starts from a v0.15 database."""
import os, re, sqlite3
from helpers import check, finish, text, fixture
os.makedirs('instance', exist_ok=True)
c = sqlite3.connect('instance/inventory.db'); c.executescript("""
CREATE TABLE user (id INTEGER PRIMARY KEY, username VARCHAR(80) NOT NULL UNIQUE, password_hash VARCHAR(200) NOT NULL, role VARCHAR(20) NOT NULL);
CREATE TABLE product (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, sku VARCHAR(50) NOT NULL UNIQUE, price FLOAT NOT NULL, quantity INTEGER, category VARCHAR(50));
CREATE TABLE sale (id INTEGER PRIMARY KEY, created_at DATETIME NOT NULL, user_id INTEGER NOT NULL, total FLOAT NOT NULL);
CREATE TABLE sale_item (id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL, product_id INTEGER NOT NULL, product_name VARCHAR(100) NOT NULL, unit_price FLOAT NOT NULL, quantity INTEGER NOT NULL);
INSERT INTO product VALUES (1,'Old Croffle','C1',150,10,'Croffles');"""); c.commit(); c.close()
from app import app, upgrade_database
app.config['CSRF_ENABLED'] = False
from models import db, User, Product, Sale, SaleItem, MenuOption
from werkzeug.security import generate_password_hash as g
with app.app_context():
    upgrade_database()
    insp = db.inspect(db.engine)
    check('old database: menu_option table + has_options + options columns', 'menu_option' in insp.get_table_names()
          and 'has_options' in [c['name'] for c in insp.get_columns('product')] and 'options' in [c['name'] for c in insp.get_columns('sale_item')])
    db.session.add_all([User(username='admin', password_hash=g('a'), role='admin'), User(username='cashier', password_hash=g('c'), role='cashier')]); db.session.commit()
a = app.test_client(); a.post('/login', data={'username': 'admin', 'password': 'a'})
c = app.test_client(); c.post('/login', data={'username': 'cashier', 'password': 'c'})
def opt(**d): return a.post('/options', data=d, follow_redirects=True).get_data(as_text=True)
opt(kind='size', name='12oz', price='0'); opt(kind='size', name='16oz', price='20')
opt(kind='addon', name='Sub Oat', price='40'); opt(kind='addon', name='Espresso', price='30'); opt(kind='addon', name='Syrup', price='20')
with app.app_context():
    ids = {o.name: o.id for o in MenuOption.query.all()}
check('admin adds 2 sizes and 3 add-ons', len(ids) == 5)
check('duplicate name refused (any capitals)', 'already a add-on' in opt(kind='addon', name='sub oat', price='1') or 'already an add-on' in opt(kind='addon', name='SUB OAT', price='1') or 'already a' in opt(kind='addon', name='sub oat', price='1'))
check('negative price refused', 'from 0 to' in opt(kind='addon', name='X', price='-5'))
check('nan price refused', 'from 0 to' in opt(kind='addon', name='Y', price='nan'))
check('name longer than 50 refused', '1 to 50' in opt(kind='addon', name='Z' * 51, price='1'))
check('unknown kind refused', a.post('/options', data={'kind': 'colour', 'name': 'Red', 'price': '1'}).status_code == 400)
check('cashier cannot open or change options (403)', c.get('/options').status_code == 403 and c.post('/options', data={'kind': 'size', 'name': 'x', 'price': '0'}).status_code == 403)
# products
a.post('/products/add', data={'name': 'Sea Salt', 'sku': 'D1', 'price': '180', 'quantity': '3', 'category': 'Lattes', 'has_options': '1'})
with app.app_context(): sea = Product.query.filter_by(sku='D1').first(); check('product form tick box saves has_options', sea.has_options); sid = sea.id
h = c.get('/sales/new').get_data(as_text=True)
check('drink tile opens the options window; croffle tile does not', f'data-product-id="{sid}"' in h and 'data-product-id="1"' not in h and 'optionsDialog' in h)
def basket(): return c.get('/sales/new').get_data(as_text=True)
c.post('/sales/new', data={'product_id': sid, 'quantity': '2', 'size_id': ids['16oz'], 'addon_ids': [ids['Espresso'], ids['Sub Oat']]})
h = basket()
check('16oz + Sub Oat + Espresso: one line, ₱270.00 each, ₱540.00', 'Sea Salt' in h and '16oz, Sub Oat, Espresso' in h and '2 × ₱270.00' in h and '₱540.00' in h)
r = c.post('/sales/new', data={'product_id': sid, 'quantity': '1', 'size_id': ids['16oz'], 'addon_ids': [ids['Sub Oat'], ids['Espresso']]}, follow_redirects=True)
check('stock counts every line: 3 in stock, 2 in basket -> only 1 more', 'Not enough stock' not in r.get_data(as_text=True))
h = basket(); check('same choice in another order joins the same line (3 ×)', '3 × ₱270.00' in h)
r = c.post('/sales/new', data={'product_id': sid, 'quantity': '1', 'size_id': ids['12oz']})
check('a 4th Sea Salt (any size) refused: stock 3', 'only 0 more' in r.get_data(as_text=True))
c.post('/sales/remove/' + str(sid))
for data, why in [({'size_id': ids['Sub Oat']}, 'add-on used as size'), ({'size_id': '9999'}, 'unknown size'),
                  ({'size_id': ids['12oz'], 'addon_ids': [ids['16oz']]}, 'size used as add-on'), ({'size_id': ids['12oz'], 'addon_ids': ['x']}, 'non-number add-on')]:
    r = c.post('/sales/new', data=dict(product_id=sid, quantity='1', **data))
    check(f'refused: {why}', r.status_code == 200 and (('sizes offered' in r.get_data(as_text=True) or 'servings offered' in r.get_data(as_text=True)) or 'add-ons from the list' in r.get_data(as_text=True)))
c.post('/sales/new', data={'product_id': sid, 'quantity': '1'})
check('list form / no size chosen -> smallest size (12oz), base price', '12oz' in basket() and '1 × ₱180.00' in basket())
c.post('/sales/new', data={'product_id': '1', 'quantity': '1', 'size_id': ids['16oz'], 'addon_ids': [ids['Espresso']]})
check('product without options ignores size/add-ons', '1 × ₱150.00' in basket())
c.post('/sales/new', data={'product_id': sid, 'quantity': '1', 'size_id': ids['16oz'], 'addon_ids': [ids['Syrup']]})
h = basket(); check('two Sea Salt lines with different options', h.count('product-name">Sea Salt</span>') == 2)
keys = re.findall(r'name="line" value="([^"]+)"', h)
c.post('/sales/remove-line', data={'line': [k for k in keys if k.startswith(f'{sid}:') and k.endswith(str(ids['Syrup']))][0]})
h = basket(); check('remove-line removes only that line', h.count('product-name">Sea Salt</span>') == 1 and 'Syrup' not in h.split('Basket')[1].split('optionsDialog')[0])
c.post('/sales/remove-line', data={'line': 'does-not-exist'}); check('removing an unknown line is harmless', basket().count('product-name">Sea Salt</span>') == 1)
# complete
c.post('/sales/new', data={'product_id': sid, 'quantity': '2', 'size_id': ids['16oz'], 'addon_ids': [ids['Sub Oat']]})
r = c.post('/sales/complete', data={'cash_received': '1000'})
with app.app_context():
    s = Sale.query.order_by(Sale.id.desc()).first(); items = sorted((i.product_name, i.options, i.unit_price, i.quantity) for i in s.items)
    check('sale saved: total 180 + 150 + 2×240 = ₱810.00', r.status_code == 302 and s.total == 810.0)
    check('receipt lines keep options text and full unit price', items == [('Old Croffle', None, 150.0, 1), ('Sea Salt', '12oz', 180.0, 1), ('Sea Salt', '16oz, Sub Oat', 240.0, 2)])
    check('stock: Sea Salt 3 -> 0, Croffle 10 -> 9', db.session.get(Product, sid).quantity == 0 and db.session.get(Product, 1).quantity == 9)
    sale_id = s.id
h = c.get(f'/sales/{sale_id}').get_data(as_text=True); check('receipt shows "16oz, Sub Oat" under the name', '16oz, Sub Oat' in h)
opt(option_id=ids['Sub Oat'], name='Sub Oat', price='55', active='1')
h = c.get(f'/sales/{sale_id}').get_data(as_text=True); check('changing an add-on price later does not change old receipts', '₱240.00' in h and '₱810.00' in h)
a2 = a.get('/reports/sales').get_data(as_text=True); check('report: Sea Salt counted once with 3 units', re.search(r'Sea Salt</td>\s*<td>3</td>', a2) is not None)
# option hidden while in basket
with app.app_context(): p = db.session.get(Product, sid); p.quantity = 5; db.session.commit()
c.post('/sales/new', data={'product_id': sid, 'quantity': '1', 'size_id': ids['16oz'], 'addon_ids': [ids['Espresso']]})
opt(option_id=ids['Espresso'], name='Espresso', price='30')   # no 'active' -> hidden
h = basket(); check('hidden add-on: its basket line is taken out with a message', 'no longer offered' in h and 'Espresso' not in h.split('Basket')[1].split('optionsDialog')[0])
check('hidden add-on not offered in the window', f'id="addon{ids["Espresso"]}"' not in basket())
with c.session_transaction() as sess: sess['basket'] = {'abc:x': 1, '1': 1}
h = basket(); check('broken basket key removed without a crash; old-style key "1" still works', 'not understood' in h and '1 × ₱150.00' in h)
# v0.16.1 edge cases
with c.session_transaction() as sess: sess['basket'] = {}
with app.app_context(): p = db.session.get(Product, sid); p.quantity = 5; db.session.commit()
c.post('/sales/new', data={'product_id': sid, 'quantity': '1', 'size_id': ids['16oz']})
with app.app_context(): p = db.session.get(Product, sid); p.has_options = False; db.session.commit()
r = c.post('/sales/complete', data={'cash_received': '1000'})
check('v0.16.1: product unticked while a 16oz line is in the basket -> line taken out, not sold with a size', ('no longer has sizes or add-ons' in r.get_data(as_text=True) or 'no longer has servings or add-ons' in r.get_data(as_text=True)) and '16oz' not in basket().split('Basket')[1].split('optionsDialog')[0])
with app.app_context():
    p = db.session.get(Product, sid); p.has_options = True
    for n in range(6): db.session.add(MenuOption(kind='addon', name=f'Long{n}-' + 'x' * 43, price=1))
    db.session.commit(); long_ids = [o.id for o in MenuOption.query.filter(MenuOption.name.like('Long%'))]
c.post('/sales/new', data={'product_id': sid, 'quantity': '1', 'size_id': ids['16oz'], 'addon_ids': long_ids})
r = c.post('/sales/complete', data={'cash_received': '10000'})
with app.app_context(): o = Sale.query.order_by(Sale.id.desc()).first().items[0].options
check('v0.16.1: very long add-on list shortened to 200 characters on the receipt', r.status_code == 302 and len(o) == 200 and o.endswith('…'))
finish('OPTIONS')
