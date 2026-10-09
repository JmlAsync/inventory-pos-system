"""Product pictures and New Sale tiles (feature F13, v0.14.x, test cases TC-14.x)."""
import os, io, re, sqlite3
from helpers import check, finish, text, fixture
# Start from an OLD database (v0.13 shape: product table without the image column)
os.makedirs('instance', exist_ok=True)
c = sqlite3.connect('instance/inventory.db'); c.executescript("""
CREATE TABLE product (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, sku VARCHAR(50) NOT NULL UNIQUE, price FLOAT NOT NULL, quantity INTEGER, category VARCHAR(50));
INSERT INTO product VALUES (1,'Old Coke','OC1',20,5,'Drinks');"""); c.commit(); c.close()
from app import app, upgrade_database, PRODUCT_IMAGE_FOLDER
app.config['CSRF_ENABLED'] = False
from models import db, User, Product, Sale, SaleItem
from werkzeug.security import generate_password_hash as g
with app.app_context():
    upgrade_database()
    check('old database gets the image column automatically', 'image' in [col['name'] for col in db.inspect(db.engine).get_columns('product')])
    db.session.add_all([User(username='admin', password_hash=g('a'), role='admin'), User(username='cashier', password_hash=g('c'), role='cashier')]); db.session.commit()
files = lambda: sorted(os.listdir(PRODUCT_IMAGE_FOLDER)) if os.path.isdir(PRODUCT_IMAGE_FOLDER) else []
for f in files(): os.remove(os.path.join(PRODUCT_IMAGE_FOLDER, f))
a = app.test_client(); a.post('/login', data={'username': 'admin', 'password': 'a'})
def add(name, sku, cat, qty=10, pic=None, fname='x.png'):
    data = {'name': name, 'sku': sku, 'price': '150', 'quantity': str(qty), 'category': cat}
    if pic is not None: data['picture'] = (io.BytesIO(pic), fname)
    return a.post('/products/add', data=data, content_type='multipart/form-data')
PNG = fixture('cup.png'); JPG = fixture('cup.jpg')
BIG = b'\x89PNG\r\n\x1a\n' + b'\x00' * (3 * 1024 * 1024)   # a 3 MB "picture"
r = add('Iced Latte (16oz)', 'IC1', 'Iced Coffee', pic=PNG)
with app.app_context(): p = Product.query.filter_by(sku='IC1').first(); img1 = p.image
check('add with PNG: product saved with a picture', r.status_code == 302 and img1 and img1.startswith('product_') and img1.endswith('.png'))
check('picture file exists in static/products', files() == [img1])
check('products list shows the <img>', f'products/{img1}' in a.get('/products').get_data(as_text=True))
r = add('Fake', 'FK1', 'Cakes', pic=b'not an image at all', fname='cake.png')
with app.app_context(): check('fake picture refused, product NOT saved', 'must be a PNG, JPG or WebP' in r.get_data(as_text=True) and Product.query.filter_by(sku='FK1').count() == 0)
r = add('No Pic', 'NP1', 'Hot Coffee', pic=b'', fname='')
with app.app_context(): check('empty file box = no picture (allowed)', r.status_code == 302 and Product.query.filter_by(sku='NP1').first().image is None)
for name, sku, cat in [('Butter Croissant', 'B1', 'Pastries'), ('Chocolate Cake (slice)', 'B2', 'Cakes'), ('Americano (12oz)', 'B3', 'Hot Coffee'), ('Hot Chocolate (12oz)', 'B4', 'Non-Coffee'), ('Bottled Water', 'B5', 'Beverages'), ('Ube Cheesecake (slice)', 'B6', 'Cakes')]:
    add(name, sku, cat, qty=0 if sku == 'B6' else 10)
from app import product_icon
with app.app_context():
    icons = {p.sku: product_icon(p)[0] for p in Product.query.all()}
check('icons: iced->straw, croissant->cookie, cake->cake, americano->hot cup, hot chocolate->cup, other->box',
      [icons[k] for k in ['IC1', 'B1', 'B2', 'B3', 'B4', 'B5']] == ['bi-cup-straw', 'bi-cookie', 'bi-cake2', 'bi-cup-hot', 'bi-cup', 'bi-box-seam'])
with app.app_context(): pid = Product.query.filter_by(sku='IC1').first().id
def edit(pid, extra):
    data = {'name': 'Iced Latte (16oz)', 'sku': 'IC1', 'price': '150', 'quantity': '10', 'category': 'Iced Coffee'}; data.update(extra)
    return a.post(f'/products/edit/{pid}', data=data, content_type='multipart/form-data')
edit(pid, {'picture': (io.BytesIO(b''), '')})
with app.app_context(): check('edit without a new file keeps the picture', db.session.get(Product, pid).image == img1 and files() == [img1])
edit(pid, {'picture': (io.BytesIO(JPG), 'new.jpg')})
with app.app_context(): img2 = db.session.get(Product, pid).image
check('replace: new JPG saved, old file deleted', img2.endswith('.jpg') and files() == [img2])
edit(pid, {'remove_picture': '1'})
with app.app_context(): check('remove tick box: picture gone, file deleted', db.session.get(Product, pid).image is None and files() == [])
r = edit(pid, {'picture': (io.BytesIO(b'GIF89a....'), 'x.gif')})
check('GIF on edit refused with message', 'must be a PNG, JPG or WebP' in r.get_data(as_text=True))
r = a.post('/products/add', data={'name': 'Big', 'sku': 'BG1', 'price': '1', 'quantity': '1', 'picture': (io.BytesIO(BIG), 'big.png')}, content_type='multipart/form-data')
check('3 MB picture on Add Product: back to the add form with a message', r.status_code == 302 and r.headers['Location'].endswith('/products/add') and 'too big' in a.get('/products/add').get_data(as_text=True))
# delete removes file; sold product keeps it
add('Temp', 'TM1', 'Pastries', pic=PNG)
with app.app_context(): t = Product.query.filter_by(sku='TM1').first(); tid, timg = t.id, t.image
a.post(f'/products/delete/{tid}')
check('deleting a never-sold product deletes its picture', timg not in files())
add('Sold', 'SD1', 'Pastries', pic=PNG)
with app.app_context():
    s = Product.query.filter_by(sku='SD1').first(); sid, simg = s.id, s.image
    sale = Sale(user_id=1, total=150); sale.items.append(SaleItem(product_id=sid, product_name='Sold', unit_price=150, quantity=1)); db.session.add(sale); db.session.commit()
a.post(f'/products/delete/{sid}')
check('sold product kept, picture kept', simg in files())
# missing file / path tricks
with app.app_context():
    p = db.session.get(Product, sid); os.remove(os.path.join(PRODUCT_IMAGE_FOLDER, simg))
    from app import product_image_url
    with app.test_request_context(): check('missing picture file -> icon tile instead', product_image_url(p) is None)
    p.image = '../../app.py'
    with app.test_request_context(): check('"../../app.py" as picture name is not served', product_image_url(p) is None)
    db.session.commit()
check('app.py still exists after deleting a product named ../../app.py picture', (a.post(f'/products/delete/{sid}'), os.path.exists('app.py'))[1])
# New Sale tiles
h = a.get('/sales/new').get_data(as_text=True)
with app.app_context(): in_stock = Product.query.filter(Product.quantity > 0).count()
check(f'New Sale shows one tile per product in stock ({in_stock})', h.count('class="menu-tile w-100') == in_stock)
check('sold-out product has no tile', 'Ube Cheesecake' not in h)
cats = re.findall(r'<div class="col" data-category="([^"]*)"', h)
check('menu tiles grouped by category (v0.14.2)', cats == sorted(cats, key=lambda c: (c == 'Other', c)))
check('chosen category remembered after a tap (v0.14.2)', 'pos-menu-category' in h)
check('category buttons shown', 'data-filter="Cakes"' in h and 'data-filter="Iced Coffee"' in h and 'data-filter="all"' in h)
r = a.post('/sales/new', data={'product_id': str(pid), 'quantity': '1'})
check('tapping a tile adds 1 to the basket', r.status_code == 302 and 'Iced Latte (16oz)</span>' in a.get('/sales/new').get_data(as_text=True) and a.get('/sales/new').get_data(as_text=True).count('9 left') >= 1)
c = app.test_client(); c.post('/login', data={'username': 'cashier', 'password': 'c'})
check('cashier cannot add products (403)', c.post('/products/add', data={'name': 'x', 'sku': 'y', 'price': '1', 'quantity': '1', 'picture': (io.BytesIO(PNG), 'a.png')}, content_type='multipart/form-data').status_code == 403)
check('.gitignore excludes static/products/', 'static/products/' in open('.gitignore').read())
for f in files(): os.remove(os.path.join(PRODUCT_IMAGE_FOLDER, f))
finish('PRODUCT PICTURES')
