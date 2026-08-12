from flask import Flask
from models import db, Product

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
db.init_app(app)

@app.route('/')
def home():
    return "Inventory & POS System is running!"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)