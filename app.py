from flask import Flask, render_template, request, redirect, url_for, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Product, User, Sale, SaleItem
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

# ---------------- Sale processing (v0.8.0) ----------------
# The basket is kept in the session (a small storage area Flask keeps for each
# logged-in browser) as a dictionary: {"product_id": quantity}.
# Nothing is saved to the database until the sale is completed.

def get_basket():
    return session.get('basket', {})

def save_basket(basket):
    session['basket'] = basket

def show_sale_page(error=None):
    """Build the basket lines and total, then show the New Sale page."""
    lines = []
    total = 0
    for key, quantity in get_basket().items():
        product = db.session.get(Product, int(key))
        if product is None:
            continue  # product was deleted after being added; skip it
        subtotal = round(product.price * quantity, 2)
        total += subtotal
        lines.append({'product': product, 'quantity': quantity, 'subtotal': subtotal})
    # Products that can still be added: stock minus what is already in the basket.
    # (The real stock in the database only goes down when the sale is completed.)
    basket = get_basket()
    choices = []
    for product in Product.query.filter(Product.quantity > 0).order_by(Product.name).all():
        available = product.quantity - basket.get(str(product.id), 0)
        if available > 0:
            choices.append({'product': product, 'available': available})
    return render_template('new_sale.html', choices=choices, lines=lines,
                           total=round(total, 2), error=error)


@app.route('/sales/new', methods=['GET', 'POST'])
@login_required
def new_sale():
    if request.method == 'POST':
        # The "Add to basket" form was submitted
        product = db.session.get(Product, request.form.get('product_id', type=int) or 0)
        quantity = request.form.get('quantity', type=int)  # None if not a whole number

        if product is None:
            return show_sale_page('Please choose a product.')
        if quantity is None or quantity < 1:
            return show_sale_page('Quantity must be a whole number of at least 1.')

        basket = get_basket()
        key = str(product.id)  # session data is stored as text, so keys are strings
        in_basket = basket.get(key, 0)
        available = product.quantity - in_basket   # what can still be added
        if quantity > available:
            return show_sale_page(f'Not enough stock for {product.name}: only {available} more can be added.')

        basket[key] = in_basket + quantity
        save_basket(basket)
        return redirect(url_for('new_sale'))

    return show_sale_page()


@app.route('/sales/remove/<int:product_id>', methods=['POST'])
@login_required
def remove_from_basket(product_id):
    basket = get_basket()
    basket.pop(str(product_id), None)  # remove it if it is there
    save_basket(basket)
    return redirect(url_for('new_sale'))


@app.route('/sales/complete', methods=['POST'])
@login_required
def complete_sale():
    basket = get_basket()
    if not basket:
        return show_sale_page('The basket is empty.')

    # Step 1: check EVERY item first and work out the total. Stock may have changed
    # since it was added (for example, another cashier sold the last one).
    total = 0
    for key, quantity in basket.items():
        product = db.session.get(Product, int(key))
        if product is None or quantity > product.quantity:
            name = product.name if product else 'A product in the basket'
            return show_sale_page(f'{name} no longer has enough stock. Please remove it or lower the quantity.')
        total += round(product.price * quantity, 2)
    total = round(total, 2)

    # Step 2: check the cash the customer paid
    cash = request.form.get('cash_received', type=float)  # None if not a number
    if cash is None or cash < total:
        return show_sale_page(f'Cash received must be a number of at least ₱{total:.2f}.')

    # Step 3: everything is fine, so create the sale and deduct stock
    sale = Sale(user_id=current_user.id, total=total,
                cash_received=round(cash, 2), change_due=round(cash - total, 2))
    for key, quantity in basket.items():
        product = db.session.get(Product, int(key))
        name = product.name
        # Deduct stock in ONE database step that only succeeds if enough is still left
        # (an "atomic update"). This is safe even if another cashier sold some of it
        # a moment ago, after our check in Step 1. It returns how many rows it changed.
        updated = (Product.query
                   .filter(Product.id == product.id, Product.quantity >= quantity)
                   .update({Product.quantity: Product.quantity - quantity},
                           synchronize_session=False))
        if updated == 0:
            db.session.rollback()   # cancel the whole sale: nothing is saved
            return show_sale_page(f'{name} was just sold by another sale and there is no longer '
                                  f'enough stock. Please check the basket again.')
        item = SaleItem(product_id=product.id, product_name=name,
                        unit_price=product.price, quantity=quantity)
        sale.items.append(item)

    db.session.add(sale)
    db.session.commit()   # saves the sale, its items and the new stock levels together
    save_basket({})       # empty the basket for the next customer
    return redirect(url_for('receipt', sale_id=sale.id))


@app.route('/sales/<int:sale_id>')
@login_required
def receipt(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template('receipt.html', sale=sale)


@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

@app.route('/logout')
@login_required
def logout():
    session.pop('basket', None)  # empty the basket so the next user starts fresh
    logout_user()
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

