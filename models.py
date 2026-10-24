from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from flask_login import UserMixin

db = SQLAlchemy()


def utc_now():
    """The current time in UTC, without a time-zone label, as every time is stored (v0.23.1, DEC-024).
    The pages show it in the shop's time (UTC+8) with the shop_time filter in app.py."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


CENT = Decimal('0.01')


def to_money(amount):
    """An amount in pesos as an exact Decimal rounded to the centavo, half up: 0.125 -> 0.13 (v0.23.2).
    Accepts what forms and code give: text, int, float or Decimal."""
    return Decimal(str(amount)).quantize(CENT, rounding=ROUND_HALF_UP)


class Money(db.TypeDecorator):
    """A money column (v0.23.2, DEF-68, DEC-025): stored as whole centavos (INTEGER: P75.50 -> 7550), so sums are
    exact on every database; Python sees exact Decimal pesos (75.50), never a float that could drift."""
    impl = db.Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else int(to_money(value) * 100)

    def process_result_value(self, value, dialect):
        return None if value is None else (Decimal(value) / 100).quantize(CENT)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    price = db.Column(Money, nullable=False)   # whole centavos in the database (v0.23.2)
    quantity = db.Column(db.Integer, default=0)
    category = db.Column(db.String(50))
    # File name of the product's picture in static/products/, or None (v0.14.0)
    image = db.Column(db.String(100))
    # True for drinks: the cashier picks a size and may add add-ons (v0.16.0)
    has_options = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        return f"<Product {self.name}>"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    # File name of the profile picture inside static/avatars, or None (v0.12.0)
    avatar = db.Column(db.String(100))

    @property
    def initials(self):
        """Up to two letters for the round avatar when there's no picture,
        e.g. 'admin' -> 'AD', 'maria.santos' -> 'MS'."""
        parts = self.username.replace('.', ' ').replace('_', ' ').split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return self.username[:2].upper()


class LoginSession(db.Model):
    """One logged-in browser (v0.20.3, DEF-51). The login cookie only carries this row's random token.
    Logging out deletes the row, so a copied cookie stops working; a password change deletes the
    user's other rows; a row that has been idle for 8 hours no longer counts."""
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)   # 64 random characters, nothing secret about the user
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    last_seen = db.Column(db.DateTime, default=utc_now, nullable=False)


class ShopProfile(db.Model):
    """The shop's own details for receipts (v0.22.0, F21, DEC-022). One row only (id 1); the owner
    edits it on Shop details. Kept in the database so it moves with the shop's data."""
    __tablename__ = 'shop_profile'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False, default='Inventory & POS')
    address = db.Column(db.String(120), nullable=False, default='')
    tin = db.Column(db.String(20), nullable=False, default='')       # Tax Identification Number, optional
    footer = db.Column(db.String(120), nullable=False, default='')   # e.g. "Thank you! See you again."


class Sale(db.Model):
    """One customer purchase (one 'receipt'). A Sale contains one or more SaleItems."""
    id = db.Column(db.Integer, primary_key=True)
    # When the sale happened. default=utc_now fills it in automatically.
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    # Which user (cashier or admin) made the sale. ForeignKey links to the user table.
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total = db.Column(Money, nullable=False, default=0)   # Money: whole centavos (v0.23.2)
    cash_received = db.Column(Money, nullable=False, default=0)  # money the customer handed over
    change_due = db.Column(Money, nullable=False, default=0)     # cash_received - total
    # How the customer paid (v0.15.0): 'cash' or 'gcash'. For GCash, the 13-digit reference
    # number from the customer's GCash receipt; unique, so one payment can't be used twice.
    payment_method = db.Column(db.String(10), nullable=False, default='cash')
    payment_reference = db.Column(db.String(20), unique=True)
    # The basket's one-time sale ticket (v0.20.4, DEF-48): unique, so one basket makes one receipt
    ticket = db.Column(db.String(32), unique=True)

    # Relationships: let us write sale.items and sale.user in Python
    items = db.relationship('SaleItem', backref='sale', lazy=True)
    movements = db.relationship('IngredientMovement', backref='sale', lazy=True)   # v0.17.0
    user = db.relationship('User')


class SaleItem(db.Model):
    """One line on a receipt: a product, how many were sold, and the price at that moment."""
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    # Copies of the name and price AT THE TIME OF SALE, so old receipts stay correct
    # even if the product is later renamed, repriced or deleted.
    product_name = db.Column(db.String(100), nullable=False)
    unit_price = db.Column(Money, nullable=False)   # whole centavos (v0.23.2)
    quantity = db.Column(db.Integer, nullable=False)
    # Size and add-ons chosen, copied as text, e.g. "16oz, Oat Milk" (v0.16.0).
    # unit_price already includes their extra cost.
    options = db.Column(db.String(200))

    @property
    def subtotal(self):
        return round(self.unit_price * self.quantity, 2)


class MenuOption(db.Model):
    """A size (e.g. 16oz) or an add-on (e.g. Oat Milk) that drinks can have (v0.16.0).
    price is the EXTRA cost on top of the product's own price (0 for the base size)."""
    __tablename__ = 'menu_option'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), nullable=False)       # 'size' or 'addon'
    name = db.Column(db.String(50), nullable=False)
    price = db.Column(Money, nullable=False, default=0)   # whole centavos (v0.23.2)
    active = db.Column(db.Boolean, nullable=False, default=True)   # hidden options aren't offered
    sort_order = db.Column(db.Integer, nullable=False, default=0)  # smaller numbers first
    # Sizes only (v0.17.0): how much of every ingredient this size uses compared with the
    # recipe, e.g. 1.33 for a 16oz when recipes are written for a 12oz
    scale = db.Column(db.Float, nullable=False, default=1.0)


class Ingredient(db.Model):
    """Something the café uses up to make products: beans, milk, croissant dough... (v0.17.0)"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    unit = db.Column(db.String(10), nullable=False, default='g')    # g, ml or pcs
    quantity = db.Column(db.Float, nullable=False, default=0)       # how much is on hand
    low_at = db.Column(db.Float, nullable=False, default=0)         # warn at or below this
    # v0.18.0: a group for the Ingredients page, and the amount when the shelf is full
    # (0 = not set). The stock bar shows quantity / full_at.
    category = db.Column(db.String(30), nullable=False, default='Other')
    full_at = db.Column(db.Float, nullable=False, default=0)


class RecipeItem(db.Model):
    """How much of one ingredient ONE product (at the default size) or ONE option uses (v0.17.0).
    Exactly one of product_id / option_id is set. Option amounts may be negative to
    replace an ingredient, e.g. Oat Milk: fresh milk -180 ml, oat milk +180 ml."""
    id = db.Column(db.Integer, primary_key=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    option_id = db.Column(db.Integer, db.ForeignKey('menu_option.id'))
    amount = db.Column(db.Float, nullable=False)
    ingredient = db.relationship('Ingredient')
    product = db.relationship('Product')        # v0.18.0: for "Used in" on an ingredient's page
    option = db.relationship('MenuOption')


class IngredientMovement(db.Model):
    """One change to an ingredient's stock, so every change can be traced (v0.17.0):
    'sale' (used up by a sale), 'restock' (delivery received) or 'count' (stock count)."""
    id = db.Column(db.Integer, primary_key=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    change = db.Column(db.Float, nullable=False)               # + added, - used
    reason = db.Column(db.String(10), nullable=False)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    ingredient = db.relationship('Ingredient')
    user = db.relationship('User')
