"""Ingredients and recipes (feature F16, v0.17.x, test cases TC-17.x)."""
import os, re, sqlite3
from helpers import check, finish, text, fixture
from app import app, upgrade_database
app.config['CSRF_ENABLED'] = False
from models import db, User, Product, Sale, SaleItem, MenuOption, Ingredient, RecipeItem, IngredientMovement
from werkzeug.security import generate_password_hash as g
import sqlalchemy.orm
with app.app_context():
    db.drop_all(); upgrade_database()
    check('scale column on sizes', 'scale' in [c['name'] for c in db.inspect(db.engine).get_columns('menu_option')])
    db.session.add_all([User(username='admin', password_hash=g('a'), role='admin'), User(username='cashier', password_hash=g('c'), role='cashier'),
        Product(name='Sea Salt', sku='D1', price=180, quantity=0, category='Lattes', has_options=True),
        Product(name='Croffle', sku='C1', price=150, quantity=3, category='Croffles'),
        MenuOption(kind='size', name='12oz', price=0, sort_order=1), MenuOption(kind='size', name='16oz', price=20, sort_order=2),
        MenuOption(kind='addon', name='Sub Oat', price=40, sort_order=1)]); db.session.commit()
    o = {m.name: m.id for m in MenuOption.query.all()}
a = app.test_client(); a.post('/login', data={'username': 'admin', 'password': 'a'})
c = app.test_client(); c.post('/login', data={'username': 'cashier', 'password': 'c'})
def ing(**d): return a.post('/ingredients', data=d, follow_redirects=True).get_data(as_text=True)
for name, unit, low in [('Espresso beans', 'g', '200'), ('Fresh milk', 'ml', '1000'), ('Oat milk', 'ml', '500'), ('Cream', 'ml', '100')]:
    ing(action='add', name=name, unit=unit, low_at=low)
with app.app_context(): I = {i.name: i.id for i in Ingredient.query.all()}
check('admin adds 4 ingredients (start at 0)', len(I) == 4)
check('duplicate ingredient name refused', 'already an ingredient' in ing(action='add', name='fresh MILK', unit='ml', low_at='0'))
check('unknown unit refused', 'Choose a unit' in ing(action='add', name='Salt', unit='kg', low_at='0'))
check('negative warn-at refused', 'Warn at' in ing(action='add', name='Salt', unit='g', low_at='-1'))
for name, amt in [('Espresso beans', '1000'), ('Fresh milk', '1000'), ('Oat milk', '2000'), ('Cream', '400')]:
    ing(action='restock', ingredient_id=I[name], amount=amt)
with app.app_context():
    check('restock ADDS and is written in the history', db.session.get(Ingredient, I['Fresh milk']).quantity == 1000 and IngredientMovement.query.filter_by(reason='restock').count() == 4)
for bad in ['0', '-5', 'nan', 'abc', '1e12']:
    check(f'restock amount "{bad}" refused', 'how much was received' in ing(action='restock', ingredient_id=I['Cream'], amount=bad))
ing(action='count', ingredient_id=I['Cream'], counted='380')
with app.app_context():
    m = IngredientMovement.query.order_by(IngredientMovement.id.desc()).first()
    check('stock count sets the amount; history shows -20', db.session.get(Ingredient, I['Cream']).quantity == 380 and m.reason == 'count' and m.change == -20)
# recipes
def rec(kind, iid, **d): return a.post(f'/recipe/{kind}/{iid}', data=d, follow_redirects=True).get_data(as_text=True)
with app.app_context(): sid = Product.query.filter_by(sku='D1').first().id; cid = Product.query.filter_by(sku='C1').first().id
rec('product', sid, ingredient_id=I['Espresso beans'], amount='18'); rec('product', sid, ingredient_id=I['Fresh milk'], amount='180'); rec('product', sid, ingredient_id=I['Cream'], amount='40')
check('negative amount refused in a product recipe', 'more than 0' in rec('product', sid, ingredient_id=I['Oat milk'], amount='-5'))
check('same ingredient twice refused', 'already in this recipe' in rec('product', sid, ingredient_id=I['Cream'], amount='5'))
rec('option', o['Sub Oat'], ingredient_id=I['Fresh milk'], amount='-180'); rec('option', o['Sub Oat'], ingredient_id=I['Oat milk'], amount='180')
with app.app_context(): check('negative amount allowed for an add-on (replace milk)', RecipeItem.query.filter_by(option_id=o['Sub Oat']).count() == 2)
a.post('/options', data={'option_id': o['16oz'], 'name': '16oz', 'price': '20', 'scale': '1.5', 'active': '1'})
with app.app_context(): check('16oz recipe scale saved (1.5)', db.session.get(MenuOption, o['16oz']).scale == 1.5)
a.post('/options', data={'option_id': o['12oz'], 'name': '12oz', 'price': '0', 'scale': '-3', 'active': '1'})
with app.app_context(): check('silly scale (-3) falls back to 1', db.session.get(MenuOption, o['12oz']).scale == 1.0)
h = a.get('/products').get_data(as_text=True)
check('products list: Sea Salt "5 can make" (milk 1000/180) with Low badge', re.search(r'5\s*<span[^>]*>can make</span>\s*<span class="badge[^"]*text-bg-warning', h) is not None)
check('product quantity field is not used for recipe products (still 0, but sellable)', 'Sea Salt' in c.get('/sales/new').get_data(as_text=True))
check('New Sale tile: "5 left"', re.search(r'Sea Salt</span>.*?5 left', c.get('/sales/new').get_data(as_text=True), re.S) is not None)
c.post('/sales/new', data={'product_id': sid, 'quantity': '2', 'size_id': o['16oz']})   # 2 x 270 ml = 540 ml milk
check('after 2 × 16oz in the basket: "2 left" (460 ml / 180)', re.search(r'Sea Salt</span>.*?2 left', c.get('/sales/new').get_data(as_text=True), re.S) is not None)
r = c.post('/sales/new', data={'product_id': sid, 'quantity': '2', 'size_id': o['16oz']})
check('too much for the milk on hand -> clear message', 'Not enough Fresh milk' in r.get_data(as_text=True) and '1,080 ml' in r.get_data(as_text=True))
c.post('/sales/new', data={'product_id': sid, 'quantity': '1', 'size_id': o['12oz'], 'addon_ids': [o['Sub Oat']]})
c.post('/sales/new', data={'product_id': cid, 'quantity': '1'})
r = c.post('/sales/complete', data={'cash_received': '2000'})
with app.app_context():
    q = {n: db.session.get(Ingredient, i).quantity for n, i in I.items()}
    s = Sale.query.order_by(Sale.id.desc()).first()
    check('sale saved', r.status_code == 302 and s is not None)
    check('milk 1000 - 540 = 460 (Sub Oat used no fresh milk)', q['Fresh milk'] == 460)
    check('oat milk 2000 - 180 = 1820; beans 1000 - 2×27 - 18 = 928; cream 380 - 2×60 - 40 = 220', (q['Oat milk'], q['Espresso beans'], q['Cream']) == (1820, 928, 220))
    check('each ingredient change is in the history, linked to the receipt', IngredientMovement.query.filter_by(reason='sale', sale_id=s.id).count() == 4)
    check('croffle (no recipe) still uses its own quantity: 3 -> 2', db.session.get(Product, cid).quantity == 2)
    check('recipe product quantity untouched', db.session.get(Product, sid).quantity == 0)
# shortage found at checkout
c.post('/sales/new', data={'product_id': sid, 'quantity': '2'})
with app.app_context(): db.session.get(Ingredient, I['Fresh milk']).quantity = 100; db.session.commit()
r = c.post('/sales/complete', data={'cash_received': '2000'})
with app.app_context(): check('milk ran out before checkout -> refused, nothing saved', 'Not enough Fresh milk' in r.get_data(as_text=True) and Sale.query.count() == 1)
# milk used up by another till between the check and the update
with app.app_context(): db.session.get(Ingredient, I['Fresh milk']).quantity = 1000; db.session.commit()
c.post('/sales/remove/' + str(sid)); c.post('/sales/new', data={'product_id': cid, 'quantity': '1'}); c.post('/sales/new', data={'product_id': sid, 'quantity': '1'})
path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
real = sqlalchemy.orm.Query.update; state = {'n': 0}
def patched(self, *a, **k):
    state['n'] += 1
    if state['n'] == 1:   # just before the first stock update: another till uses up every ingredient
        con = sqlite3.connect(os.path.join(app.instance_path, 'inventory.db')); con.execute('UPDATE ingredient SET quantity = 0'); con.commit(); con.close()
    return real(self, *a, **k)
sqlalchemy.orm.Query.update = patched
r = c.post('/sales/complete', data={'cash_received': '2000'}); sqlalchemy.orm.Query.update = real
with app.app_context():
    check('ingredient used up mid-sale -> whole sale cancelled, croffle stock restored', 'just used up' in r.get_data(as_text=True) and Sale.query.count() == 1 and db.session.get(Product, cid).quantity == 2)
check('cashier cannot open Ingredients or recipes (403)', c.get('/ingredients').status_code == 403 and c.get(f'/recipe/product/{sid}').status_code == 403)
with app.app_context(): other = RecipeItem.query.filter_by(option_id=o['Sub Oat']).first().id
check("can't edit another recipe's line through this page (404)", a.post(f'/recipe/product/{sid}', data={'line_id': other, 'amount': '1'}).status_code == 404)
check('unknown recipe kind -> 404', a.get('/recipe/banana/1').status_code == 404)
check('home shows the low-ingredients warning to the admin', 'running low' in a.get('/').get_data(as_text=True))
check('ingredient history lists sales with a link to the receipt', 'Sale <a href="/sales/' in (a.get('/ingredients').get_data(as_text=True) + (a.get('/ingredients/history').get_data(as_text=True) if a.get('/ingredients/history').status_code == 200 else '')))
with app.app_context(): line = RecipeItem.query.filter_by(product_id=sid, ingredient_id=I['Cream']).first().id
rec('product', sid, line_id=line, action='remove')
with app.app_context(): check('remove an ingredient from a recipe', RecipeItem.query.filter_by(product_id=sid).count() == 2)
# v0.17.1: deleting a never-sold product removes its recipe, so a new product can't inherit it
a.post('/products/add', data={'name': 'Temp Drink', 'sku': 'TD1', 'price': '100', 'quantity': '5', 'category': 'X'})
with app.app_context(): tid = Product.query.filter_by(sku='TD1').first().id
rec('product', tid, ingredient_id=I['Espresso beans'], amount='500')
a.post(f'/products/delete/{tid}')
a.post('/products/add', data={'name': 'New Cookie', 'sku': 'NC1', 'price': '50', 'quantity': '20', 'category': 'Pastries'})
with app.app_context():
    n = Product.query.filter_by(sku='NC1').first()
    check(f'v0.17.1: new product (id {n.id}, old id {tid}) has no inherited recipe', RecipeItem.query.filter_by(product_id=n.id).count() == 0)
with app.app_context():
    db.session.add(RecipeItem(ingredient_id=I['Cream'], amount=1, product_id=99999)); db.session.commit()
    upgrade_database()
    check('v0.17.1: start-up removes recipe lines of deleted products', RecipeItem.query.filter_by(product_id=99999).count() == 0)
finish('INGREDIENTS')
