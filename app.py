from flask import Flask, render_template
from models import db, Product

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
db.init_app(app)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/products')
def products():
    all_products = Product.query.all()
    return render_template('products.html', products=all_products)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)