from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin

db = SQLAlchemy()

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    price = db.Column(db.Float, nullable=False)
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


class Sale(db.Model):
    """One customer purchase (one 'receipt'). A Sale contains one or more SaleItems."""
    id = db.Column(db.Integer, primary_key=True)
    # When the sale happened. default=datetime.now fills it in automatically.
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    # Which user (cashier or admin) made the sale. ForeignKey links to the user table.
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total = db.Column(db.Float, nullable=False, default=0)
    cash_received = db.Column(db.Float, nullable=False, default=0)  # money the customer handed over
    change_due = db.Column(db.Float, nullable=False, default=0)     # cash_received - total
    # How the customer paid (v0.15.0): 'cash' or 'gcash'. For GCash, the 13-digit reference
    # number from the customer's GCash receipt; unique, so one payment can't be used twice.
    payment_method = db.Column(db.String(10), nullable=False, default='cash')
    payment_reference = db.Column(db.String(20), unique=True)

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
    unit_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    # Size and add-ons chosen, copied as text, e.g. "16oz, Sub Oat" (v0.16.0).
    # unit_price already includes their extra cost.
    options = db.Column(db.String(200))

    @property
    def subtotal(self):
        return round(self.unit_price * self.quantity, 2)


class MenuOption(db.Model):
    """A size (e.g. 16oz) or an add-on (e.g. Sub Oat) that drinks can have (v0.16.0).
    price is the EXTRA cost on top of the product's own price (0 for the base size)."""
    __tablename__ = 'menu_option'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), nullable=False)       # 'size' or 'addon'
    name = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False, default=0)
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
    replace an ingredient, e.g. Sub Oat: fresh milk -180 ml, oat milk +180 ml."""
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
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    ingredient = db.relationship('Ingredient')
    user = db.relationship('User')
