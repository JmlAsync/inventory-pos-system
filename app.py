from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Product, User
from functools import wraps
from flask import abort

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SECRET_KEY'] = 'dev-secret-change-this-later'
db.init_app(app)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def validate_product_form(form, current_product_id=None):
    """Check the product form on the server. Returns (data, error).
    If something is wrong, data is None and error is a message for the user."""
    # .strip() removes spaces at the start and end, so "   " counts as empty
    name = form.get('name', '').strip()
    sku = form.get('sku', '').strip()
    category = form.get('category', '').strip() or None

    # 1. Required fields must not be empty
    if not name or not sku:
        return None, 'Name and SKU are required.'

    # 2. Price and quantity must be numbers (float/int raise ValueError if not)
    try:
        price = float(form.get('price', ''))
        quantity = int(form.get('quantity', ''))
    except ValueError:
        return None, 'Price must be a number and quantity must be a whole number.'

    # 3. No negative values
    if price < 0 or quantity < 0:
        return None, 'Price and quantity cannot be negative.'

    # 4. SKU must be unique. Look for ANOTHER product that already uses this SKU
    #    (when editing, the product being edited is allowed to keep its own SKU)
    existing = Product.query.filter_by(sku=sku).first()
    if existing and existing.id != current_product_id:
        return None, f'SKU "{sku}" is already used by "{existing.name}".'

    return {'name': name, 'sku': sku, 'price': price,
            'quantity': quantity, 'category': category}, None

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/products')
@login_required
def products():
    all_products = Product.query.all()
    return render_template('products.html', products=all_products)

@app.route('/products/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_product():
    if request.method == 'POST':
        data, error = validate_product_form(request.form)
        if error:
            # Show the form again with the error message; nothing is saved
            return render_template('add_product.html', error=error)
        new_product = Product(**data)
        db.session.add(new_product)
        db.session.commit()
        return redirect(url_for('products'))
    return render_template('add_product.html')

@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        data, error = validate_product_form(request.form, current_product_id=product.id)
        if error:
            return render_template('edit_product.html', product=product, error=error)
        product.name = data['name']
        product.sku = data['sku']
        product.price = data['price']
        product.quantity = data['quantity']
        product.category = data['category']
        db.session.commit()
        return redirect(url_for('products'))
    return render_template('edit_product.html', product=product)

@app.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
@admin_required
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('products'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('products'))
        return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')

@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

