"""Silly and huge numbers never crash the app or get saved (DEF-14, DEF-15, DEF-17)."""
import math
from werkzeug.security import generate_password_hash as g
from helpers import check, finish
from app import app
from models import db, Product, User

app.config['CSRF_ENABLED'] = False
app.config['PROPAGATE_EXCEPTIONS'] = False
with app.app_context():
    db.drop_all(); db.create_all()
    db.session.add_all([User(username='c', password_hash=g('p'), role='cashier'), User(username='a', password_hash=g('p'), role='admin'),
                        Product(name='X', sku='X', price=10, quantity=50)]); db.session.commit()

c = app.test_client(); c.post('/login', data={'username': 'c', 'password': 'p'})
# 200 = refused with a message, 302 = accepted (sale saved, receipt opens)
for cash, expected in [('nan', 200), ('inf', 200), ('-inf', 200), ('1e308', 200), ('1000000.01', 200), ('1000000', 302), ('10', 302)]:
    c.post('/sales/new', data={'product_id': '1', 'quantity': '1'})
    status = c.post('/sales/complete', data={'cash_received': cash}).status_code
    check(f'cash "{cash}": {"accepted" if expected == 302 else "refused"}', status == expected)
    c.post('/sales/remove/1')

a = app.test_client(); a.post('/login', data={'username': 'a', 'password': 'p'})
cases = [('nan', '1', 200), ('inf', '1', 200), ('1e400', '1', 200), ('1000000.01', '1', 200), ('1', '99999999999999999999', 200),
         ('1', '1000001', 200), ('1000000', '1000000', 302), ('-1', '1', 200)]
for i, (price, qty, expected) in enumerate(cases):
    status = a.post('/products/add', data={'name': f'P{i}', 'sku': f'S{i}', 'price': price, 'quantity': qty}).status_code
    check(f'product price "{price}", quantity "{qty}": {"accepted" if expected == 302 else "refused"}', status == expected)
check('5,000-character name refused (DEF-17)', a.post('/products/add', data={'name': 'N' * 5000, 'sku': 'LONG', 'price': '1', 'quantity': '1'}).status_code == 200)
check('an id too big for the database is "not found", not a crash (DEF-15)', a.get('/products/edit/99999999999999999999').status_code == 404)
with app.app_context():
    check('no "not a number" or infinite price was saved', all(math.isfinite(p.price) for p in Product.query.all()))

# v0.19.3 (DEF-47, security audit A1): a drink made from a recipe with a 309-digit quantity crashed New Sale
from models import Ingredient, RecipeItem
with app.app_context():
    db.session.add_all([Product(name='Latte', sku='LAT', price=150, quantity=0), Ingredient(name='Milk', unit='ml', quantity=5000, low_at=0)])
    db.session.commit()
    latte = Product.query.filter_by(sku='LAT').first().id
    db.session.add(RecipeItem(product_id=latte, ingredient_id=Ingredient.query.filter_by(name='Milk').first().id, amount=200)); db.session.commit()
for qty in ['9' * 309, '9' * 400, '1000001']:
    r = c.post('/sales/new', data={'product_id': latte, 'quantity': qty})
    check(f'recipe drink, quantity of {len(qty)} digits: refused with a message, no crash (DEF-47)', r.status_code == 200 and 'at most 1,000,000' in r.get_data(as_text=True))
r = c.post('/sales/new', data={'product_id': latte, 'quantity': '3'})
check('recipe drink, normal quantity 3 still added', r.status_code == 302)
page = open('templates/new_sale.html', encoding='utf-8').read()
# v0.20.0: the drink window is gone (one tap adds 1; − / + change it), so only the list form has a quantity box
check('the quantity box on New Sale says max="1000000"', page.count('min="1" max="1000000"') == 1)
finish('LIMITS')
