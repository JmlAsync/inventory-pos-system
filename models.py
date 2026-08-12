from flask_sqlalchemy import SQLAlchemy
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