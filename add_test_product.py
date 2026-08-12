from app import app
from models import db, Product

with app.app_context():
    test_product = Product(name="Sample Item", sku="SKU001", price=19.99, quantity=50, category="Test")
    db.session.add(test_product)
    db.session.commit()
    print("Test product added!")