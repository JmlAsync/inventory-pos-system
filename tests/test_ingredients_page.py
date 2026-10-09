"""Ingredients page (feature F17, v0.18.x, test cases TC-18.x): groups, full level, detail page, history."""
import os, re, sqlite3
from helpers import check, finish, text, fixture
# Start from a v0.17 database: ingredient table WITHOUT category / full_at
os.makedirs('instance', exist_ok=True)
c = sqlite3.connect('instance/inventory.db'); c.executescript("""
CREATE TABLE ingredient (id INTEGER PRIMARY KEY, name VARCHAR(50) NOT NULL UNIQUE, unit VARCHAR(10) NOT NULL, quantity FLOAT NOT NULL, low_at FLOAT NOT NULL);
INSERT INTO ingredient VALUES (1,'Oat milk','ml',2000,500),(2,'Iced cups','pcs',100,20),(3,'Espresso beans','g',3000,500),
 (4,'Croissant dough','pcs',24,6),(5,'Biscoff spread','g',600,120),(6,'Cocoa powder','g',500,100),(7,'Ice','g',0,1000),(8,'Lotus biscuits','pcs',5,6);"""); c.commit(); c.close()
from app import app, upgrade_database
app.config['CSRF_ENABLED'] = False
from models import db, User, Ingredient, IngredientMovement, Product, RecipeItem
from werkzeug.security import generate_password_hash as g
with app.app_context():
    upgrade_database()
    got = {i.name: i.category for i in Ingredient.query.all()}
    check('old ingredients put into likely groups', got == {'Oat milk': 'Milk & cream', 'Iced cups': 'Cups & packaging', 'Espresso beans': 'Coffee',
          'Croissant dough': 'Bakery', 'Biscoff spread': 'Syrups & sauces', 'Cocoa powder': 'Toppings', 'Ice': 'Other', 'Lotus biscuits': 'Toppings'})
    full = {i.name: i.full_at for i in Ingredient.query.all()}
    check('full level starts at what is on hand (0 when already low/out)', full['Oat milk'] == 2000 and full['Ice'] == 0 and full['Lotus biscuits'] == 0)
    db.session.add_all([User(username='admin', password_hash=g('a'), role='admin'), User(username='cashier', password_hash=g('c'), role='cashier'),
                        Product(name='Sea Salt', sku='S1', price=180, quantity=0, category='Coffee')]); db.session.commit()
    db.session.add(RecipeItem(ingredient_id=1, product_id=1, amount=180)); db.session.commit()
a = app.test_client(); a.post('/login', data={'username': 'admin', 'password': 'a'})
c = app.test_client(); c.post('/login', data={'username': 'cashier', 'password': 'c'})
h = a.get('/ingredients').get_data(as_text=True)
import html as H
order = [H.unescape(x) for x in re.findall(r'<section class="card ing-group mb-3" data-group="([^"]+)"', h)]
check('groups shown in the fixed order', order == ['Coffee', 'Milk & cream', 'Syrups & sauces', 'Toppings', 'Bakery', 'Cups & packaging', 'Other'])
att = re.search(r'data-group="attention".*?</section>', h, re.S).group(0)
check('Needs attention lists Out first, then Low', att.index('Ice') < att.index('Lotus biscuits') and 'Oat milk' not in att)
check('filter buttons with counts', 'All · 8' in h and 'Low or out · 2' in h and 'Toppings · 2' in h)
check('stock bar width: 2000 of 2000 ml = 100%', re.search(r'data-name="oat milk".*?width: 100%', h, re.S) is not None)
check('one Update button per row (8 + 2 in Needs attention)', h.count('js-update"') == 10)
def post(**d): return a.post('/ingredients', data=d, follow_redirects=True).get_data(as_text=True)
r = post(action='edit', ingredient_id='1', name='Oat milk', unit='ml', low_at='500', category='Milk & cream', full_at='4000')
with app.app_context(): check('edit saves group and full level', db.session.get(Ingredient, 1).full_at == 4000)
check('bar now 50%', re.search(r'data-name="oat milk".*?width: 50%', a.get('/ingredients').get_data(as_text=True), re.S) is not None)
check('full at or below "warn at" refused', 'must be more than' in post(action='edit', ingredient_id='1', name='Oat milk', unit='ml', low_at='500', category='Milk & cream', full_at='400'))
check('unknown group refused', 'Choose one of the groups' in post(action='edit', ingredient_id='1', name='Oat milk', unit='ml', low_at='500', category='Drinks', full_at='4000'))
check('full 0 allowed (no bar)', 'Saved Espresso beans' in post(action='edit', ingredient_id='3', name='Espresso beans', unit='g', low_at='500', category='Coffee', full_at='0'))
check('"No full level set" shown for it', re.search(r'data-name="espresso beans".*?No full level set', a.get('/ingredients').get_data(as_text=True), re.S) is not None)
post(action='edit', ingredient_id='4', name='Croissant dough', unit='pcs', low_at='6')     # an older form without group/full
with app.app_context(): i = db.session.get(Ingredient, 4); check('older form without group/full keeps them', i.category == 'Bakery' and i.full_at == 24)
post(action='add', name='Vanilla syrup', unit='ml', low_at='100', category='Syrups & sauces', full_at='1000')
with app.app_context(): v = Ingredient.query.filter_by(name='Vanilla syrup').first(); check('new ingredient with group and full', v and v.category == 'Syrups & sauces' and v.full_at == 1000 and v.quantity == 0)
post(action='add', name='Paper straws', unit='pcs', low_at='50')
with app.app_context(): check('new ingredient without a group gets a guess', Ingredient.query.filter_by(name='Paper straws').first().category == 'Cups & packaging')
d = a.get('/ingredients/1').get_data(as_text=True)
check('detail page: name, Restock/Count/Edit, used in Sea Salt', 'Oat milk' in d and 'Add to stock' in d and 'Save count' in d and 'Save changes' in d and 'Sea Salt' in d)
check('detail page: number boxes have no thousands separator (value="4000", not "4,000")', 'name="full_at" min="0" step="any" value="4000"' in d)
check('detail page: "Fill up to full (+2,000)"', 'Fill up to full (+<span class="js-refill-amount">2,000' in d)
r = a.post('/ingredients', data={'action': 'restock', 'ingredient_id': '1', 'amount': '500', 'return_to': 'detail'})
check('restock from the detail page returns there', r.status_code == 302 and r.headers['Location'].endswith('/ingredients/1'))
r = a.post('/ingredients', data={'action': 'restock', 'ingredient_id': '1', 'amount': '1', 'return_to': 'https://evil.example'})
check('a web address in return_to is ignored', 'evil' not in r.headers['Location'] and '/ingredients' in r.headers['Location'])
r = a.post('/ingredients', data={'action': 'count', 'ingredient_id': '6', 'counted': '500'})
check('v0.18.1: back on the list at the same row (#ing-6)', r.headers['Location'].endswith('/ingredients#ing-6'))
h18 = a.get('/ingredients').get_data(as_text=True)
check('v0.18.1: each row has its anchor once (not repeated in Needs attention)', h18.count('id="ing-8"') == 1 and h18.count('id="ing-') == h18.count('js-update"') - re.search(r'data-group="attention".*?</section>', h18, re.S).group(0).count('js-update"'))
check('unknown ingredient page -> 404', a.get('/ingredients/999').status_code == 404 and a.get('/ingredients/99999999999999999999').status_code == 404)
for page in ['/ingredients', '/ingredients/1', '/ingredients/history']:
    check(f'cashier gets 403 on {page}', c.get(page).status_code == 403)
post(action='count', ingredient_id='6', counted='450')
hist = a.get('/ingredients/history').get_data(as_text=True)
check('History tab lists restock and count', 'Restock' in hist and 'Stock count' in hist)
only = a.get('/ingredients/history?ingredient=6&reason=count').get_data(as_text=True)
check('History filter: Cocoa powder counts only', 'Cocoa powder' in only and '-50 g' in only and 'Oat milk</a>' not in only)
check('History filter with junk values shows everything', a.get('/ingredients/history?ingredient=abc&reason=<b>').status_code == 200)
app.config['CSRF_ENABLED'] = True
for page in ['/ingredients', '/ingredients/1']:
    h = a.get(page).get_data(as_text=True)
    forms = h.count('method="POST"'); check(f'every POST form on {page} carries a token ({forms})', forms > 0 and h.count('name="csrf_token"') == forms)
app.config['CSRF_ENABLED'] = False
rec = a.get('/recipe/product/1').get_data(as_text=True)
check('recipe page groups ingredients (optgroup)', '<optgroup label="Milk &amp; cream">' in rec)
check('home warning links to the Low/out filter', 'filter=attention' in a.get('/').get_data(as_text=True))
finish('INGREDIENTS PAGE')
