"""Log in, roles and product add / edit / delete (features F1-F6, test cases TC-1 to TC-6)."""
from helpers import check, finish, make_users, text
from app import app
from models import db, Product, User

app.config['CSRF_ENABLED'] = False        # forms are posted directly; test_security.py checks tokens
app.config['PROPAGATE_EXCEPTIONS'] = False  # a crash shows up as status 500 instead of stopping the test
with app.app_context():
    db.drop_all(); db.create_all(); make_users(db, User)

# Visitor (not logged in)
v = app.test_client()
check('visitor can open the home page', v.get('/').status_code == 200)
check('visitor is sent to log in for /products', v.get('/products').headers.get('Location', '').startswith('/login'))
check('visitor is sent to log in for /products/add', v.get('/products/add').status_code == 302)

# Log in
c = app.test_client()
check('wrong password: message, not logged in', 'Invalid username or password' in text(c.post('/login', data={'username': 'admin', 'password': 'wrong'})))
check('unknown user: same message (does not reveal which part was wrong)', 'Invalid username or password' in text(c.post('/login', data={'username': 'ghost', 'password': 'x'})))
check('username is case-sensitive (ADMIN is not admin)', c.post('/login', data={'username': 'ADMIN', 'password': 'admin123'}).status_code == 200)
r = c.post('/login', data={'username': 'admin', 'password': 'admin123'})
check('right password logs in and opens Products', r.status_code == 302 and r.headers['Location'].endswith('/products'))
check('admin sees the Add Product button', 'Add Product' in text(c.get('/products')))

# Product add / edit / delete as admin
def add(**data): return c.post('/products/add', data=data)
check('add a valid product', add(name='Coke 1.5L', sku='BEV-001', price='75.50', quantity='24', category='Beverages').status_code == 302)
h = text(c.get('/products'))
check('list shows it with a peso price', 'Coke 1.5L' in h and '₱75.50' in h)
check('category is optional', add(name='Noodles', sku='FD-001', price='15', quantity='10').status_code == 302)
check('duplicate SKU refused with a message, no crash (DEF-01)', add(name='Dup', sku='BEV-001', price='1', quantity='1').status_code == 200)
check('non-number price refused, no crash (DEF-02)', add(name='Bad', sku='X-1', price='abc', quantity='1').status_code == 200)
check('negative price and quantity refused (DEF-03)', add(name='Neg', sku='X-2', price='-5', quantity='-3').status_code == 200)
check('empty name refused even without the browser check (DEF-04)', add(name='', sku='X-3', price='1', quantity='1').status_code == 200)
with app.app_context():
    check('only the 2 valid products were saved', sorted(p.sku for p in Product.query.all()) == ['BEV-001', 'FD-001'])
check('edit form is filled in', 'value="Coke 1.5L"' in text(c.get('/products/edit/1')))
c.post('/products/edit/1', data={'name': 'Coke 1.5L', 'sku': 'BEV-001', 'price': '80', 'quantity': '20', 'category': 'Beverages'})
with app.app_context():
    p = db.session.get(Product, 1)
    check('edit saves the new price and quantity', (p.price, p.quantity) == (80.0, 20))
check('edit to an SKU already used refused', c.post('/products/edit/1', data={'name': 'Coke', 'sku': 'FD-001', 'price': '80', 'quantity': '20'}).status_code == 200)
check('editing a product that does not exist: 404', c.get('/products/edit/999').status_code == 404)
check('delete by plain link (GET) not allowed: 405', c.get('/products/delete/2').status_code == 405)
check('delete by button (POST) works', c.post('/products/delete/2').status_code == 302)
with app.app_context():
    check('deleted product is gone', [p.id for p in Product.query.all()] == [1])
check('deleting a product that does not exist: 404', c.post('/products/delete/999').status_code == 404)
check('log out', c.post('/logout').status_code == 302)
check('after log out, Products needs log in again', c.get('/products').status_code == 302)

# Cashier: can look, cannot change (F6)
k = app.test_client()
check('cashier logs in', k.post('/login', data={'username': 'cashier', 'password': 'cashier123'}).status_code == 302)
h = text(k.get('/products'))
check('cashier sees "View only" and no Add button', '>Add Product<' not in h and 'View only' in h)
r = k.get('/products/add')
check('cashier opening Add Product gets the 403 page', r.status_code == 403 and 'Access Denied' in text(r))
check('cashier POST to Add Product: 403', k.post('/products/add', data={'name': 'h', 'sku': 'H', 'price': '1', 'quantity': '1'}).status_code == 403)
check('cashier opening Edit: 403', k.get('/products/edit/1').status_code == 403)
check('cashier POST to Delete: 403', k.post('/products/delete/1').status_code == 403)
with app.app_context():
    check('product still exists after the cashier tried', db.session.get(Product, 1) is not None)
    u = User.query.filter_by(username='admin').first()
    check('passwords are stored hashed, never as plain text', u.password_hash != 'admin123' and u.password_hash.startswith(('scrypt:', 'pbkdf2:')))
finish('PRODUCTS')
