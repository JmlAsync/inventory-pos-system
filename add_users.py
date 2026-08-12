from app import app
from models import db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    admin = User(username='admin', password_hash=generate_password_hash('admin123'), role='admin')
    cashier = User(username='cashier', password_hash=generate_password_hash('cashier123'), role='cashier')
    db.session.add(admin)
    db.session.add(cashier)
    db.session.commit()
    print("Users created!")