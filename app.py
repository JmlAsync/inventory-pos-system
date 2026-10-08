from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Product, User, Sale, SaleItem
from functools import wraps
import math
import os
import secrets
from datetime import datetime, date, timedelta
from sqlalchemy import func
from flask import abort

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'


def load_secret_key():
    """The secret key signs the login cookie, so it must never be in the code on GitHub (v0.13.1).
    It comes from the SECRET_KEY environment variable if set; otherwise a random key is created
    once and kept in instance/secret_key.txt (the instance folder is not uploaded to GitHub)."""
    from_environment = os.environ.get('SECRET_KEY')
    if from_environment:
        return from_environment
    os.makedirs(app.instance_path, exist_ok=True)
    key_file = os.path.join(app.instance_path, 'secret_key.txt')
    if not os.path.exists(key_file):
        with open(key_file, 'w') as f:
            f.write(secrets.token_hex(32))   # 64 random characters
    with open(key_file) as f:
        return f.read().strip()


app.config['SECRET_KEY'] = load_secret_key()
# The login cookie is only sent with requests that start on this site (v0.13.2)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# Check the CSRF token on every form (v0.13.2). Automated tests may switch this off.
app.config['CSRF_ENABLED'] = True
# Largest upload allowed (v0.12.0): bigger requests are refused with error 413
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024   # 2 MB
db.init_app(app)

# Upper limits for numbers typed into forms (v0.8.3). Generous for a mini-store,
# café or market, but they stop "nan", "inf" and absurdly large values.
MAX_PRICE = 1_000_000      # pesos
MAX_QUANTITY = 1_000_000   # units
MAX_CASH = 1_000_000       # pesos

# Products with this many units or fewer are flagged as "low stock" (v0.9.0).
# One number for every product keeps the database unchanged; change it here if needed.
LOW_STOCK_THRESHOLD = 5

# The biggest whole number SQLite can store (v0.8.4). Bigger ids can't exist,
# and asking the database for them crashes it, so they count as "not found".
MAX_DB_ID = 2**63 - 1


def find_by_id(model, item_id):
    """Look up one row by its id. Returns None when there is no such row,
    including ids that are missing, below 1, or too big for the database."""
    if item_id is None or item_id < 1 or item_id > MAX_DB_ID:
        return None
    return db.session.get(model, item_id)

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

    # 1b. Text must fit the database columns in models.py (v0.8.6)
    if len(name) > 100 or len(sku) > 50 or len(category or '') > 50:
        return None, 'Name can be at most 100 characters; SKU and category at most 50.'

    # 2. Price and quantity must be numbers (float/int raise ValueError if not)
    try:
        price = float(form.get('price', ''))
        quantity = int(form.get('quantity', ''))
    except ValueError:
        return None, 'Price must be a number and quantity must be a whole number.'

    # 3. No negative values
    if price < 0 or quantity < 0:
        return None, 'Price and quantity cannot be negative.'

    # 4. Realistic numbers only: math.isfinite() is False for "nan" and "inf"
    if not math.isfinite(price) or price > MAX_PRICE or quantity > MAX_QUANTITY:
        return None, f'Price must be at most ₱{MAX_PRICE:,} and quantity at most {MAX_QUANTITY:,}.'

    # 5. SKU must be unique. Look for ANOTHER product that already uses this SKU
    #    (when editing, the product being edited is allowed to keep its own SKU)
    existing = Product.query.filter_by(sku=sku).first()
    if existing and existing.id != current_product_id:
        return None, f'SKU "{sku}" is already used by "{existing.name}".'

    return {'name': name, 'sku': sku, 'price': price,
            'quantity': quantity, 'category': category}, None

@app.template_filter('peso')
def peso(amount):
    """Show money the Philippine way, e.g. 6079.5 -> '₱6,079.50' (v0.11.2).
    Used in templates as {{ sale.total|peso }}."""
    return f'₱{amount:,.2f}'


# ---------------- Database upgrades (v0.12.0) ----------------
# db.create_all() creates missing TABLES but never adds COLUMNS to existing ones,
# so columns added by later versions are listed here and added once, automatically.
NEW_COLUMNS = [
    ('sale', 'cash_received', 'FLOAT NOT NULL DEFAULT 0'),   # v0.8.0
    ('sale', 'change_due', 'FLOAT NOT NULL DEFAULT 0'),      # v0.8.0
    ('user', 'avatar', 'VARCHAR(100)'),                      # v0.12.0
]


def upgrade_database():
    """Create missing tables, then add any missing columns from NEW_COLUMNS."""
    db.create_all()
    inspector = db.inspect(db.engine)
    with db.engine.begin() as connection:
        for table, column, column_type in NEW_COLUMNS:
            existing = [c['name'] for c in inspector.get_columns(table)]
            if column not in existing:
                connection.execute(db.text(f'ALTER TABLE "{table}" ADD COLUMN {column} {column_type}'))


# ---------------- CSRF protection (v0.13.2) ----------------
# CSRF = Cross-Site Request Forgery: another website making your browser submit one of
# our forms while you are logged in. Every form we show carries a secret random token
# (a hidden field); a POST without the matching token is refused.

@app.template_global()
def csrf_token():
    """The token for this browser session, created the first time it's needed.
    Used in templates as  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">"""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


@app.before_request
def check_csrf_token():
    """Runs before every request; stops POSTs that don't carry the right token."""
    if request.method != 'POST' or not app.config['CSRF_ENABLED']:
        return
    expected = session.get('_csrf_token')
    sent = request.form.get('csrf_token', '')
    # compare_digest takes the same time whether the first or the last character differs,
    # so the token can't be guessed by measuring response times
    if not expected or not secrets.compare_digest(sent, expected):
        abort(400)


@app.errorhandler(400)
def bad_request(e):
    return render_template('400.html'), 400


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    """Home page. Logged-in users see today's numbers and shortcuts (v0.13.0)."""
    stats = None
    if current_user.is_authenticated:
        start_of_today = datetime.combine(date.today(), datetime.min.time())
        todays_sales = Sale.query.filter(Sale.created_at >= start_of_today).all()
        stats = {
            'products': Product.query.count(),
            'low_stock': Product.query.filter(Product.quantity <= LOW_STOCK_THRESHOLD).count(),
            'sales_today': len(todays_sales),
            'revenue_today': round(sum(sale.total for sale in todays_sales), 2),
        }
    return render_template('home.html', stats=stats, today=date.today())

@app.route('/products')
@login_required
def products():
    all_products = Product.query.all()
    # Products at or below the threshold, lowest stock first, for the warning box
    low_stock = (Product.query.filter(Product.quantity <= LOW_STOCK_THRESHOLD)
                 .order_by(Product.quantity).all())
    return render_template('products.html', products=all_products,
                           low_stock=low_stock, threshold=LOW_STOCK_THRESHOLD)

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
    product = find_by_id(Product, product_id) or abort(404)
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
    product = find_by_id(Product, product_id) or abort(404)
    # A product that has been sold must stay (v0.10.2): reports group sales by product,
    # and SQLite can give a deleted product's id to the next new product, which would
    # then "inherit" the old sales. Setting its quantity to 0 stops it being sold.
    if SaleItem.query.filter_by(product_id=product.id).first():
        flash(f'"{product.name}" has sales history, so it can\'t be deleted. '
              f'Set its quantity to 0 instead to stop selling it.', 'danger')
        return redirect(url_for('products'))
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('products'))

# ---------------- Login attempt limit (v0.13.3) ----------------
# Without a limit, a program can try thousands of passwords a minute. After
# MAX_LOGIN_FAILURES wrong passwords for one username from one computer (IP address),
# that computer must wait LOCKOUT_MINUTES before trying that username again.
# Counting per username AND computer means a stranger can't lock the real owner out.
# The counts live in memory, so restarting the app clears them.
MAX_LOGIN_FAILURES = 5
LOCKOUT_MINUTES = 5
failed_logins = {}   # (username, IP address) -> times of recent wrong passwords


def recent_failures(key):
    """Wrong-password times for this key within the lockout window (older ones are forgotten)."""
    cutoff = datetime.now() - timedelta(minutes=LOCKOUT_MINUTES)
    recent = [moment for moment in failed_logins.get(key, []) if moment > cutoff]
    if recent:
        failed_logins[key] = recent
    else:
        failed_logins.pop(key, None)
    return recent


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        key = (username.strip().lower(), request.remote_addr)
        if len(recent_failures(key)) >= MAX_LOGIN_FAILURES:
            # 429 = "Too Many Requests"
            return render_template('login.html', error=f'Too many failed attempts. Please wait '
                                   f'{LOCKOUT_MINUTES} minutes and try again.'), 429
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            failed_logins.pop(key, None)   # a correct password resets the count
            login_user(user)
            return redirect(url_for('products'))
        failed_logins.setdefault(key, []).append(datetime.now())
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
    basket = get_basket()
    lines = []
    total = 0
    for key, quantity in list(basket.items()):   # list(): we may remove items while looping
        product = db.session.get(Product, int(key))
        if product is None:
            # The product was deleted after it was added: take it out of the basket,
            # otherwise the sale could never be completed (v0.8.5)
            basket.pop(key)
            error = error or ('A product in the basket was deleted from the product list, '
                              'so it was taken out of the basket. Please check the total.')
            continue
        subtotal = round(product.price * quantity, 2)
        total += subtotal
        lines.append({'product': product, 'quantity': quantity, 'subtotal': subtotal})
    save_basket(basket)
    # Products that can still be added: stock minus what is already in the basket.
    # (The real stock in the database only goes down when the sale is completed.)
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
        product = find_by_id(Product, request.form.get('product_id', type=int))
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
        if product is None:
            return show_sale_page()   # takes the deleted product out and explains why
        if quantity > product.quantity:
            return show_sale_page(f'{product.name} no longer has enough stock. '
                                  f'Please remove it and add it again with a smaller quantity.')
        total += round(product.price * quantity, 2)
    total = round(total, 2)

    # Step 2: check the cash the customer paid
    cash = request.form.get('cash_received', type=float)  # None if not a number
    if cash is None or not math.isfinite(cash) or cash < total or cash > MAX_CASH:
        return show_sale_page(f'Cash received must be a number of at least ₱{total:,.2f} '
                              f'(and at most ₱{MAX_CASH:,}).')

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
    sale = find_by_id(Sale, sale_id) or abort(404)
    return render_template('receipt.html', sale=sale)


# ---------------- Sales report (v0.10.0) ----------------

# Dates the report accepts (v0.10.0)
EARLIEST_DATE = date(2000, 1, 1)
LATEST_DATE = date(2100, 12, 31)


@app.route('/reports/sales')
@login_required
@admin_required
def sales_report():
    """Totals, list of sales and top products for a date range (default: today)."""
    today = date.today()
    error = None
    # Dates arrive in the address as text, e.g. /reports/sales?start=2026-10-08&end=2026-10-08
    try:
        start = datetime.strptime(request.args.get('start', today.isoformat()), '%Y-%m-%d').date()
        end = datetime.strptime(request.args.get('end', today.isoformat()), '%Y-%m-%d').date()
        # Realistic range only: a date like 9999-12-31 has no "next day" and would crash below
        if not (EARLIEST_DATE <= start <= LATEST_DATE and EARLIEST_DATE <= end <= LATEST_DATE):
            raise ValueError
    except ValueError:
        start = end = today
        error = 'Please choose real dates between 2000 and 2100, so showing today instead.'
    if start > end:
        start, end = end, start   # swap them if entered the wrong way round

    # From the start of the first day up to (but not including) the day after the last day
    period_start = datetime.combine(start, datetime.min.time())
    period_end = datetime.combine(end + timedelta(days=1), datetime.min.time())
    in_period = (Sale.created_at >= period_start) & (Sale.created_at < period_end)

    sales = Sale.query.filter(in_period).order_by(Sale.created_at.desc()).all()
    revenue = round(sum(sale.total for sale in sales), 2)

    # Top 5 products by units sold (v0.10.1). Grouped by PRODUCT (its id), not by name,
    # so a product renamed after being sold still counts as one product.
    # The name shown is the one used in its most recent sale.
    totals = {}   # product id -> {'name', 'units', 'revenue', 'last_sold'}
    for sale in sales:
        for item in sale.items:
            row = totals.setdefault(item.product_id, {'name': item.product_name, 'units': 0,
                                                      'revenue': 0, 'last_sold': sale.created_at})
            row['units'] += item.quantity
            row['revenue'] += item.subtotal
            if sale.created_at >= row['last_sold']:   # keep the most recent name
                row['name'], row['last_sold'] = item.product_name, sale.created_at
    best = sorted(totals.values(), key=lambda row: row['units'], reverse=True)[:5]
    top_products = [(row['name'], row['units'], round(row['revenue'], 2)) for row in best]
    # Total units sold in the period (coalesce turns "nothing" into 0 when there are no sales)
    items_sold = (db.session.query(func.coalesce(func.sum(SaleItem.quantity), 0))
                  .join(Sale).filter(in_period).scalar())

    return render_template('sales_report.html', sales=sales, revenue=revenue,
                           items_sold=items_sold, top_products=top_products,
                           start=start, end=end, error=error)


# ---------------- Profile picture (v0.12.0) ----------------
AVATAR_FOLDER = os.path.join(app.static_folder, 'avatars')


def detect_image_type(data):
    """Return 'png', 'jpg' or 'webp' by looking at the file's first bytes
    (its "magic number"), or None if it isn't one of those images.
    The file name can lie; the bytes can't easily."""
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if data.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'webp'
    return None


def delete_avatar_file(user):
    """Remove the user's current picture file, if any."""
    if user.avatar:
        path = os.path.join(AVATAR_FOLDER, os.path.basename(user.avatar))
        if os.path.exists(path):
            os.remove(path)


@app.template_global()
def avatar_url(user):
    """Web address of the user's picture, or None to show initials instead
    (also None if the file has gone missing)."""
    if user.avatar and os.path.exists(os.path.join(AVATAR_FOLDER, os.path.basename(user.avatar))):
        return url_for('static', filename='avatars/' + user.avatar)
    return None


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        file = request.files.get('picture')
        data = file.read() if file else b''
        if not data:
            flash('Choose a picture first.', 'danger')
            return redirect(url_for('profile'))
        kind = detect_image_type(data)
        if kind is None:
            flash('That file isn\'t a PNG, JPG or WebP picture.', 'danger')
            return redirect(url_for('profile'))
        os.makedirs(AVATAR_FOLDER, exist_ok=True)
        # A random file name, so nobody can guess or overwrite another user's picture
        filename = f'user{current_user.id}_{secrets.token_hex(8)}.{kind}'
        with open(os.path.join(AVATAR_FOLDER, filename), 'wb') as f:
            f.write(data)
        delete_avatar_file(current_user)   # remove the old picture
        current_user.avatar = filename
        db.session.commit()
        flash('Profile picture updated.', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html')


@app.route('/profile/remove', methods=['POST'])
@login_required
def remove_avatar():
    delete_avatar_file(current_user)
    current_user.avatar = None
    db.session.commit()
    flash('Profile picture removed.', 'success')
    return redirect(url_for('profile'))


@app.errorhandler(413)
def too_large(e):
    flash('That picture is too big. The limit is 2 MB.', 'danger')
    return redirect(url_for('profile'))


@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403

@app.route('/logout', methods=['POST'])   # a button, not a link, so other sites can't log you out (v0.13.2)
@login_required
def logout():
    session.pop('basket', None)  # empty the basket so the next user starts fresh
    logout_user()
    return redirect(url_for('home'))

if __name__ == '__main__':
    with app.app_context():
        upgrade_database()   # creates tables and adds any new columns (v0.12.0)
    app.run(debug=True)

