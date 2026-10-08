"""Fill the database with realistic demo data for the presentation (v0.11.0).
Since v0.14.0 the demo shop is a café (coffee and pastries).

Run it once with:   python seed_demo_data.py
It is safe to run again: products and users that already exist are skipped,
and demo sales are only added when the database has no sales yet.

To start over with ONLY the café demo:   python seed_demo_data.py --fresh
That first renames the current database to instance/inventory_backup_<date-time>.db
(nothing is deleted), then creates a new one.
Run it shortly before presenting: today's demo sales stop at the current time.
"""
import math
import os
import random
import sys
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from app import app, upgrade_database
from models import db, Product, User, Sale, SaleItem

# (name, SKU, price in pesos, quantity in stock, category)
# A small café menu (v0.14.0). For drinks, "quantity" means cups that can still be
# made today (limited by beans, milk and cups); for pastries it's pieces on the shelf.
DEMO_PRODUCTS = [
    # Hot coffee (12oz)
    ("Americano (12oz)",               "HC-001", 110.00, 40, "Hot Coffee"),
    ("Cafe Latte (12oz)",              "HC-002", 140.00, 35, "Hot Coffee"),
    ("Cappuccino (12oz)",              "HC-003", 140.00, 30, "Hot Coffee"),
    ("Spanish Latte (12oz)",           "HC-004", 155.00, 25, "Hot Coffee"),
    ("Caramel Macchiato (12oz)",       "HC-005", 160.00, 25, "Hot Coffee"),
    # Iced coffee (16oz)
    ("Iced Americano (16oz)",          "IC-001", 120.00, 40, "Iced Coffee"),
    ("Iced Latte (16oz)",              "IC-002", 150.00, 35, "Iced Coffee"),
    ("Iced Spanish Latte (16oz)",      "IC-003", 165.00, 30, "Iced Coffee"),
    ("Iced Caramel Macchiato (16oz)",  "IC-004", 170.00, 25, "Iced Coffee"),
    ("Iced Mocha (16oz)",              "IC-005", 170.00, 20, "Iced Coffee"),
    # Non-coffee
    ("Matcha Latte (12oz)",            "NC-001", 160.00, 20, "Non-Coffee"),
    ("Iced Matcha Latte (16oz)",       "NC-002", 170.00, 20, "Non-Coffee"),
    ("Hot Chocolate (12oz)",           "NC-003", 130.00, 20, "Non-Coffee"),
    ("Iced Strawberry Milk (16oz)",    "NC-004", 150.00, 15, "Non-Coffee"),
    # Pastries
    ("Butter Croissant",               "PA-001",  95.00,  5, "Pastries"),   # low stock (5 = threshold)
    ("Ensaymada",                      "PA-002",  65.00, 12, "Pastries"),
    ("Chocolate Chip Cookie",          "PA-003",  60.00, 18, "Pastries"),
    ("Banana Bread (slice)",           "PA-004",  75.00, 10, "Pastries"),
    ("Cinnamon Roll",                  "PA-005", 110.00,  4, "Pastries"),   # low stock
    # Cakes
    ("Basque Burnt Cheesecake (slice)", "CK-001", 180.00, 8, "Cakes"),
    ("Chocolate Cake (slice)",         "CK-002", 150.00,  3, "Cakes"),      # low stock
    ("Ube Cheesecake (slice)",         "CK-003", 165.00,  0, "Cakes"),      # sold out
]

DEMO_USERS = [("admin", "admin123", "admin"), ("cashier", "cashier123", "cashier")]


def add_users():
    for username, password, role in DEMO_USERS:
        if User.query.filter_by(username=username).first() is None:
            db.session.add(User(username=username,
                                password_hash=generate_password_hash(password), role=role))
            print(f"  + user {username}")


def add_products():
    for name, sku, price, quantity, category in DEMO_PRODUCTS:
        if Product.query.filter_by(sku=sku).first() is None:   # SKU must be unique
            db.session.add(Product(name=name, sku=sku, price=price,
                                   quantity=quantity, category=category))
            print(f"  + product {name}")


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
            for product in random.sample(products, random.randint(1, 3)):  # 1 to 3 different items
                quantity = random.randint(1, 2)
                sale.items.append(SaleItem(product_id=product.id, product_name=product.name,
                                           unit_price=product.price, quantity=quantity))
                total += round(product.price * quantity, 2)
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
    add_users()
    add_products()
    db.session.commit()    # save users and products first, so they have ids
    add_past_sales()
    db.session.commit()
    print("Demo data ready.")
