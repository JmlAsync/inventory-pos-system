"""Fill the database with realistic demo data for the presentation (v0.11.0).
Since v0.14.0 the demo shop is a café; since v0.16.0 drinks have sizes and add-ons.

Run it once with:   python seed_demo_data.py
It is safe to run again: products, options and users that already exist are skipped,
and demo sales are only added when the database has no sales yet.

To start over with ONLY the demo data:   python seed_demo_data.py --fresh
That first renames the current database to instance/inventory_backup_<date-time>.db
(nothing is deleted), then creates a new one.
Run it shortly before presenting: today's demo sales stop at the current time.

A real shop's menu (v0.16.0): put it in local_demo/menu.json (same shape as DEFAULT_MENU
below, and optional photos in local_demo/photos/). The local_demo folder is NOT uploaded
to GitHub, so a shop's own names and photos stay on your computer.
"""
import json
import math
import os
import random
import shutil
import sys
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from app import app, upgrade_database, PRODUCT_IMAGE_FOLDER, detect_image_type
from models import db, Product, User, Sale, SaleItem, MenuOption, Ingredient, RecipeItem

LOCAL_MENU = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'local_demo', 'menu.json')

# A small generic café menu. For drinks, "quantity" means cups that can still be
# made today; for pastries it's pieces on the shelf.
# Products: [name, SKU, price in pesos, quantity, category, has sizes/add-ons, photo file or null]
DEFAULT_MENU = {
    "products": [
        ["Americano",              "HC-001", 110.00, 40, "Hot Coffee",  True,  None],
        ["Cafe Latte",             "HC-002", 140.00, 35, "Hot Coffee",  True,  None],
        ["Cappuccino",             "HC-003", 140.00, 30, "Hot Coffee",  True,  None],
        ["Spanish Latte",          "HC-004", 155.00, 25, "Hot Coffee",  True,  None],
        ["Iced Americano",         "IC-001", 120.00, 40, "Iced Coffee", True,  None],
        ["Iced Latte",             "IC-002", 150.00, 35, "Iced Coffee", True,  None],
        ["Iced Caramel Macchiato", "IC-003", 170.00, 25, "Iced Coffee", True,  None],
        ["Iced Mocha",             "IC-004", 170.00, 20, "Iced Coffee", True,  None],
        ["Matcha Latte",           "NC-001", 160.00, 20, "Non-Coffee",  True,  None],
        ["Hot Chocolate",          "NC-002", 130.00, 20, "Non-Coffee",  True,  None],
        ["Butter Croissant",       "PA-001",  95.00,  5, "Pastries",    False, None],   # low stock (5 = threshold)
        ["Ensaymada",              "PA-002",  65.00, 12, "Pastries",    False, None],
        ["Chocolate Chip Cookie",  "PA-003",  60.00, 18, "Pastries",    False, None],
        ["Cinnamon Roll",          "PA-004", 110.00,  4, "Pastries",    False, None],   # low stock
        ["Basque Burnt Cheesecake (slice)", "CK-001", 180.00, 8, "Cakes", False, None],
        ["Chocolate Cake (slice)", "CK-002", 150.00,  3, "Cakes",       False, None],   # low stock
        ["Ube Cheesecake (slice)", "CK-003", 165.00,  0, "Cakes",       False, None],   # sold out
    ],
    # [name, extra price, recipe scale]. The first size is the default (placeholder sizes:
    # change them on the Sizes & Add-ons page once the owner confirms). Recipes below are
    # for a 12oz; a 16oz uses 1.33 times as much of everything.
    "sizes": [["12oz", 0, 1.0], ["16oz", 20, 1.33]],
    "addons": [["Extra Shot", 30], ["Oat Milk", 40], ["Syrup", 20]],
    # Ingredients (v0.17.0): [name, unit, on hand, warn at]. Estimated amounts.
    "ingredients": [
        ["Espresso beans", "g", 2000, 500], ["Fresh milk", "ml", 8000, 2000],
        ["Oat milk", "ml", 2000, 500], ["Condensed milk", "ml", 1500, 300],
        ["Caramel sauce", "ml", 1000, 200], ["Chocolate sauce", "ml", 1000, 200],
        ["Vanilla syrup", "ml", 1000, 200], ["Matcha powder", "g", 50, 60],   # low on purpose
    ],
    # Recipes (v0.17.0): product SKU, or "size:<name>" / "addon:<name>" -> [[ingredient, amount]].
    # Products without a recipe (the pastries) keep counting their own quantity.
    "recipes": {
        "HC-001": [["Espresso beans", 18]],
        "HC-002": [["Espresso beans", 18], ["Fresh milk", 200]],
        "HC-003": [["Espresso beans", 18], ["Fresh milk", 150]],
        "HC-004": [["Espresso beans", 18], ["Fresh milk", 180], ["Condensed milk", 20]],
        "IC-001": [["Espresso beans", 18]],
        "IC-002": [["Espresso beans", 18], ["Fresh milk", 180]],
        "IC-003": [["Espresso beans", 18], ["Fresh milk", 180], ["Caramel sauce", 20]],
        "IC-004": [["Espresso beans", 18], ["Fresh milk", 160], ["Chocolate sauce", 30]],
        "NC-001": [["Matcha powder", 6], ["Fresh milk", 200]],
        "NC-002": [["Chocolate sauce", 40], ["Fresh milk", 200]],
        "addon:Extra Shot": [["Espresso beans", 18]],
        "addon:Oat Milk": [["Fresh milk", -200], ["Oat milk", 200]],   # replaces the fresh milk
        "addon:Syrup": [["Vanilla syrup", 15]],
    },
}

DEMO_USERS = [("admin", "admin123", "admin"), ("cashier", "cashier123", "cashier")]


def load_menu():
    """The shop's own menu from local_demo/menu.json if it exists, else the generic one."""
    if os.path.exists(LOCAL_MENU):
        with open(LOCAL_MENU, encoding='utf-8') as f:
            print(f"  using the local menu in {LOCAL_MENU}")
            return json.load(f)
    return DEFAULT_MENU


def add_users():
    for username, password, role in DEMO_USERS:
        if User.query.filter_by(username=username).first() is None:
            db.session.add(User(username=username,
                                password_hash=generate_password_hash(password), role=role))
            print(f"  + user {username}")


def copy_photo(photo):
    """Copy a photo from local_demo/photos/ into static/products/; return its new name or None."""
    if not photo:
        return None
    source = os.path.join(os.path.dirname(LOCAL_MENU), 'photos', os.path.basename(photo))
    if not os.path.exists(source):
        print(f"  (photo {photo} not found, an icon is shown instead)")
        return None
    with open(source, 'rb') as f:
        kind = detect_image_type(f.read(16))
    if kind is None:
        print(f"  (photo {photo} is not a PNG, JPG or WebP picture, so it was skipped)")
        return None
    os.makedirs(PRODUCT_IMAGE_FOLDER, exist_ok=True)
    name = f"product_demo_{os.path.splitext(os.path.basename(photo))[0]}.{kind}"
    shutil.copyfile(source, os.path.join(PRODUCT_IMAGE_FOLDER, name))
    return name


def add_products(menu):
    for name, sku, price, quantity, category, has_options, photo in menu["products"]:
        if Product.query.filter_by(sku=sku).first() is None:   # SKU must be unique
            db.session.add(Product(name=name, sku=sku, price=price, quantity=quantity,
                                   category=category, has_options=has_options,
                                   image=copy_photo(photo)))
            print(f"  + product {name}")


def add_options(menu):
    """Sizes and add-ons (v0.16.0); sizes may have a recipe scale (v0.17.0)."""
    for kind, key in (("size", "sizes"), ("addon", "addons")):
        for order, (name, price, *scale) in enumerate(menu.get(key, []), start=1):
            if MenuOption.query.filter_by(kind=kind, name=name).first() is None:
                db.session.add(MenuOption(kind=kind, name=name, price=price, sort_order=order,
                                          scale=scale[0] if scale else 1.0))
                print(f"  + {kind} {name}")


def add_ingredients_and_recipes(menu):
    """Ingredients and recipes (v0.17.0). Recipes are only added to things that have none yet."""
    for name, unit, on_hand, low_at in menu.get("ingredients", []):
        if Ingredient.query.filter_by(name=name).first() is None:
            db.session.add(Ingredient(name=name, unit=unit, quantity=on_hand, low_at=low_at))
            print(f"  + ingredient {name}")
    db.session.flush()   # give the new ingredients their ids
    for owner, lines in menu.get("recipes", {}).items():
        if owner.startswith(("size:", "addon:")):
            kind, name = owner.split(":", 1)
            option = MenuOption.query.filter_by(kind=kind, name=name).first()
            target = {"option_id": option.id} if option else None
        else:
            product = Product.query.filter_by(sku=owner).first()
            target = {"product_id": product.id} if product else None
        if target is None or RecipeItem.query.filter_by(**target).first():
            continue   # unknown, or it already has a recipe (maybe edited by the admin)
        for ingredient_name, amount in lines:
            ingredient = Ingredient.query.filter_by(name=ingredient_name).first()
            if ingredient:
                db.session.add(RecipeItem(ingredient_id=ingredient.id, amount=amount, **target))
        print(f"  + recipe for {owner}")


OPENING_HOUR = 7    # the café opens at 7 AM ...
CLOSING_HOUR = 21  # ... and closes at 9 PM


def add_past_sales(days=7):
    """Create sales for the last `days` days and for today up to now, so the Sales Report
    and the Home dashboard have data. The stock numbers above are what is left now,
    so these sales don't change them."""
    if Sale.query.first() is not None:
        print("  (sales already exist, so no demo sales added)")
        return
    random.seed(42)  # same "random" data every time, so the demo is predictable
    products = Product.query.filter(Product.quantity > 0).all()
    users = User.query.all()
    sizes = MenuOption.query.filter_by(kind='size', active=True).order_by(MenuOption.sort_order).all()
    addons = MenuOption.query.filter_by(kind='addon', active=True).order_by(MenuOption.sort_order).all()
    now = datetime.now()
    used_references = set()
    for days_ago in range(days, -1, -1):   # ... 2 days ago, yesterday, today (0)
        opening = now.replace(hour=OPENING_HOUR, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
        open_minutes = (CLOSING_HOUR - OPENING_HOUR) * 60
        # 6 to 10 sales per day while the café is open, created in time order so that
        # receipt numbers go up with time, like in a real shop (v0.11.1)
        times = sorted(opening + timedelta(minutes=random.randint(0, open_minutes))
                       for _ in range(random.randint(6, 10)))
        for when in times:
            if when > now:   # today: only sales that already "happened"
                continue
            sale = Sale(user_id=random.choice(users).id, created_at=when)
            total = 0
            for product in random.sample(products, min(len(products), random.randint(1, 3))):  # 1 to 3 different items
                quantity = random.randint(1, 2)
                unit_price, chosen = product.price, []
                if product.has_options and sizes:
                    # Mostly the small size; sometimes an add-on (v0.16.0)
                    size = sizes[0] if random.random() < 0.6 else random.choice(sizes)
                    extras = random.sample(addons, 1) if addons and random.random() < 0.3 else []
                    chosen = [size] + extras
                    unit_price = round(product.price + sum(o.price for o in chosen), 2)
                sale.items.append(SaleItem(product_id=product.id, product_name=product.name,
                                           unit_price=unit_price, quantity=quantity,
                                           options=', '.join(o.name for o in chosen) or None))
                total += round(unit_price * quantity, 2)
            sale.total = round(total, 2)
            if random.random() < 0.35:
                # About a third pay by GCash (v0.15.0): exact amount, a made-up 13-digit reference
                sale.payment_method = 'gcash'
                sale.payment_reference = str(random.randint(10**12, 10**13 - 1))
                while sale.payment_reference in used_references:
                    sale.payment_reference = str(random.randint(10**12, 10**13 - 1))
                used_references.add(sale.payment_reference)
                sale.cash_received, sale.change_due = sale.total, 0
            else:
                # Pretend the customer paid with the next ₱100 up (math.ceil rounds up: 2.4 -> 3)
                sale.cash_received = math.ceil(sale.total / 100) * 100
                sale.change_due = round(sale.cash_received - sale.total, 2)
            db.session.add(sale)
    print(f"  + demo sales for the last {days} days and today")


def start_fresh():
    """--fresh: put the current database aside under a new name (nothing is deleted)."""
    database = os.path.join(app.instance_path, 'inventory.db')
    if os.path.exists(database):
        backup = os.path.join(app.instance_path, f"inventory_backup_{datetime.now():%Y-%m-%d_%H%M%S}.db")
        try:
            os.rename(database, backup)
        except PermissionError:   # Windows won't rename a file that the running app has open
            sys.exit("The database is in use. Stop the app first (Ctrl + C in its terminal), then run this again.")
        print(f"  old database kept as {backup}")


if '--fresh' in sys.argv:
    start_fresh()

with app.app_context():
    upgrade_database()     # make sure every table and column exists (v0.12.0)
    menu = load_menu()
    add_users()
    add_options(menu)
    add_products(menu)
    db.session.commit()    # save users, options and products first, so they have ids
    add_ingredients_and_recipes(menu)
    db.session.commit()
    add_past_sales()
    db.session.commit()
    print("Demo data ready.")
