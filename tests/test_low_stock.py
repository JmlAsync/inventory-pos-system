"""Low-stock warning on the Products page (feature F8, test cases TC-8.x)."""
from werkzeug.security import generate_password_hash as g
from helpers import check, finish, text
from app import app
from models import db, Product, User

app.config['CSRF_ENABLED'] = False
app.config['PROPAGATE_EXCEPTIONS'] = False
with app.app_context():
    db.drop_all(); db.create_all()
    db.session.add_all([User(username='a', password_hash=g('p'), role='admin'), User(username='c', password_hash=g('p'), role='cashier'),
                        Product(name='Plenty', sku='P1', price=10, quantity=50), Product(name='Edge', sku='P2', price=10, quantity=5),
                        Product(name='Six', sku='P3', price=10, quantity=6), Product(name='Gone', sku='P4', price=10, quantity=0),
                        Product(name='Few', sku='P5', price=10, quantity=2)])
    db.session.commit()

c = app.test_client(); c.post('/login', data={'username': 'c', 'password': 'p'})
h = text(c.get('/products'))
start = h.find('alert-warning'); box = h[start:h.find('</div>', start)]
check('cashier sees the box: "Low stock (3)"', 'Low stock (3)' in h)
check('box lists 5 or less (Edge, Gone, Few), not 6 or more (Six, Plenty)', all(x in box for x in ['Edge', 'Gone', 'Few']) and 'Six' not in box and 'Plenty' not in box)
check('lowest first: Gone (0), Few (2), Edge (5)', box.find('Gone') < box.find('Few') < box.find('Edge'))
check('badges: 1 "Out of stock", 2 "Low"', h.count('Out of stock') >= 1 and h.count('>Low<') == 2)
a = app.test_client(); a.post('/login', data={'username': 'a', 'password': 'p'})
check('admin sees the box too', 'Low stock (3)' in text(a.get('/products')))
for pid, name, qty in [(5, 'Few', 20), (4, 'Gone', 30), (2, 'Edge', 9)]:
    a.post(f'/products/edit/{pid}', data={'name': name, 'sku': f'P{pid}', 'price': '10', 'quantity': str(qty)})
h = text(a.get('/products'))
check('after restocking: no box, no badges', 'alert-warning' not in h and 'Out of stock' not in h and '>Low<' not in h)
a.post('/sales/new', data={'product_id': '3', 'quantity': '1'}); a.post('/sales/complete', data={'cash_received': '10'})
h = text(a.get('/products'))
check('selling 1 "Six" (6 -> 5) puts it in the box', 'Low stock (1)' in h and 'Six (5 left)' in h)
with app.app_context():
    for i in range(8):
        db.session.add(Product(name=f'Low{i}', sku=f'L{i}', price=1, quantity=1))
    db.session.commit()
h = text(a.get('/products'))
check('many low products: 5 shown + "and N more" (DEF-18)', 'and 4 more' in h)
finish('LOW STOCK')
