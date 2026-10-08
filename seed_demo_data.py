"""Fill the database with realistic demo data for the presentation (v0.11.0).

Run it once with:   python seed_demo_data.py
It is safe to run again: products and users that already exist are skipped,
and demo sales are only added when the database has no sales yet.
"""
import math
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from app import app
from models import db, Product, User, Sale, SaleItem

# (name, SKU, price in pesos, quantity in stock, category)
# A mix for the three target shops: mini-store, coffee shop and market.
DEMO_PRODUCTS = [
    # Mini-store
    ("Coca-Cola 1.5L",          "MS-001",  75.00, 24, "Beverages"),
    ("Bottled Water 500ml",     "MS-002",  15.00, 48, "Beverages"),
    ("Instant Noodles (Beef)",  "MS-003",  14.50, 60, "Food"),
    ("Corned Beef 150g",        "MS-004",  42.00, 18, "Canned Goods"),
    ("Sardines 155g",           "MS-005",  24.00,  4, "Canned Goods"),   # low stock
    ("Bath Soap",               "MS-006",  38.00, 12, "Household"),
    ("Shampoo Sachet",          "MS-007",   8.00,  0, "Household"),      # out of stock
    # Coffee shop
    ("Brewed Coffee (12oz)",    "CF-001",  85.00, 40, "Coffee"),
    ("Iced Latte (16oz)",       "CF-002", 120.00, 30, "Coffee"),
    ("Ensaymada",               "CF-003",  45.00,  3, "Pastry"),         # low stock
    ("Chocolate Chip Cookie",   "CF-004",  35.00, 20, "Pastry"),
    # Market
    ("Rice 1kg (Sinandomeng)",  "MK-001",  52.00, 50, "Grains"),
    ("Eggs (Tray of 30)",       "MK-002", 230.00,  8, "Poultry"),
    ("Tomatoes 1kg",            "MK-003",  80.00,  5, "Vegetables"),     # low stock (5 = threshold)
    ("Onions 1kg",              "MK-004", 120.00, 15, "Vegetables"),
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


def add_past_sales(days=7):
    """Create a few sales per day for the last `days` days, so the Sales Report has history.
    These are past sales, so they do not change today's stock levels."""
    if Sale.query.first() is not None:
        print("  (sales already exist, so no demo sales added)")
        return
    random.seed(42)  # same "random" data every time, so the demo is predictable
    products = Product.query.filter(Product.quantity > 0).all()
    users = User.query.all()
    for days_ago in range(days, 0, -1):
        day = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
        for _ in range(random.randint(3, 6)):                  # 3 to 6 sales per day
            when = day + timedelta(minutes=random.randint(0, 11 * 60))   # between 8 AM and 7 PM
            sale = Sale(user_id=random.choice(users).id, created_at=when)
            total = 0
            for product in random.sample(products, random.randint(1, 3)):  # 1 to 3 different items
                quantity = random.randint(1, 3)
                sale.items.append(SaleItem(product_id=product.id, product_name=product.name,
                                           unit_price=product.price, quantity=quantity))
                total += round(product.price * quantity, 2)
            sale.total = round(total, 2)
            # Pretend the customer paid with the next ₱100 up (math.ceil rounds up: 2.4 -> 3)
            sale.cash_received = math.ceil(sale.total / 100) * 100
            sale.change_due = round(sale.cash_received - sale.total, 2)
            db.session.add(sale)
    print(f"  + demo sales for the last {days} days")


with app.app_context():
    db.create_all()        # make sure every table exists
    add_users()
    add_products()
    db.session.commit()    # save users and products first, so they have ids
    add_past_sales()
    db.session.commit()
    print("Demo data ready.")
