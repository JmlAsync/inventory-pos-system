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

    def __repr__(self):
        return f"<Product {self.name}>"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)


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

    # Relationships: let us write sale.items and sale.user in Python
    items = db.relationship('SaleItem', backref='sale', lazy=True)
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

    @property
    def subtotal(self):
        return round(self.unit_price * self.quantity, 2)