from flask import Flask, render_template, request, redirect, url_for
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

@app.route('/products/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        new_product = Product(
            name=request.form['name'],
            sku=request.form['sku'],
            price=float(request.form['price']),
            quantity=int(request.form['quantity']),
            category=request.form.get('category')
        )
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for('products'))
    return render_template('add_product.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)