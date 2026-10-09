"""Number boxes never contain a thousands separator (DEF-43, v0.17.4)."""
import re
from helpers import check, finish, text, fixture
from app import app, upgrade_database
app.config['CSRF_ENABLED'] = False
from models import db, User, Ingredient, Product, RecipeItem
from werkzeug.security import generate_password_hash as g
with app.app_context():
    db.drop_all(); upgrade_database()
    db.session.add_all([User(username='admin', password_hash=g('a'), role='admin'), Ingredient(name='Fresh milk', unit='ml', quantity=12000, low_at=2000),
                        Product(name='Big Latte', sku='B1', price=1500, quantity=2000)]); db.session.commit()
    db.session.add(RecipeItem(ingredient_id=1, product_id=1, amount=1500)); db.session.commit()
a = app.test_client(); a.post('/login', data={'username': 'admin', 'password': 'a'})
bad = []   # every 1,000+ amount below must appear in its box as 1000, never 1,000
for page in ['/ingredients', '/ingredients/1', '/recipe/product/1', '/options', '/products/edit/1']:
    h = a.get(page).get_data(as_text=True)
    bad += [(page, m) for m in re.findall(r'<input[^>]*type="number"[^>]*value="([^"]*,[^"]*)"', h)]
    bad += [(page, m) for m in re.findall(r'<input[^>]*value="([^"]*,[^"]*)"[^>]*type="number"', h)]
    check(f'{page}: no number box shows a comma, like value="2,000"', not bad)
    bad.clear()
finish('NUMBER BOXES')
