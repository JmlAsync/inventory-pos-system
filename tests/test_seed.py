"""Demo data (seed_demo_data.py, v0.11.x and v0.17.3): it must work with the built-in menu and with a
shop's own local_demo/menu.json, never make an empty or ₱0 sale (DEF-42), and back up before --fresh."""
import os
import shutil
import subprocess
import sys
from helpers import check, finish, fixture, FIXTURES

COUNT = """
import logging; logging.disable(50)
from app import app
from models import Sale, Product, Ingredient
with app.app_context():
    sales = Sale.query.all()
    pictures = sorted(p.sku for p in Product.query.filter(Product.image.isnot(None)))
    print(len(sales), sum(1 for s in sales if s.total <= 0 or not s.items), Product.query.count(), Ingredient.query.count(), ','.join(pictures) or '-')
"""


def seed(*options):
    return subprocess.run([sys.executable, 'seed_demo_data.py', *options], capture_output=True, text=True, encoding='utf-8', errors='replace')


def counts():
    out = subprocess.run([sys.executable, '-c', COUNT], capture_output=True, text=True).stdout.split()
    return int(out[0]), int(out[1]), int(out[2]), int(out[3]), out[4]


# 1. Built-in generic menu
seed()
sales, empty, products, ingredients, pictures = counts()
check(f'built-in menu: {sales} demo sales, none empty or ₱0', sales > 20 and empty == 0)
check('running it a second time adds nothing ("already exist")', 'already exist' in seed().stdout and counts()[0] == sales)

# 2. A shop's own menu in local_demo/ (drinks made from recipes have quantity 0)
os.makedirs('local_demo/photos')
shutil.copy(os.path.join(FIXTURES, 'menu.json'), 'local_demo/menu.json')
shutil.copy(os.path.join(FIXTURES, 'cup.png'), 'local_demo/photos/cup.png')
with open('local_demo/photos/not_a_picture.png', 'w') as f:
    f.write('this is text, not a picture')
r = seed('--fresh')
sales, empty, products, ingredients, pictures = counts()
check(f'local menu with recipes: {sales} demo sales, none empty or ₱0 (DEF-42)', r.returncode == 0 and sales > 20 and empty == 0)
check('local menu: all 14 products and 14 ingredients loaded', (products, ingredients) == (14, 14))
check('a real photo is copied to the product; a fake one is skipped with a message',
      pictures == 'HC-002' and 'not a PNG, JPG or WebP' in r.stdout and any(f.endswith('.png') for f in os.listdir('static/products')))
backups = [f for f in os.listdir('instance') if f.startswith('inventory') and f.endswith('.db') and f != 'inventory.db']
check('--fresh first saved a backup copy of the old database', len(backups) == 1)
finish('SEED')
