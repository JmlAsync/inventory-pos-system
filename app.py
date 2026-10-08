from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Product, User, Sale, SaleItem, MenuOption
from functools import wraps
import math
import os
import secrets
from datetime import datetime, date, timedelta
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
import re
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

# Ways to pay (v0.15.0). GCash is only recorded here (the customer pays in their GCash
# app and shows the receipt); connecting to GCash itself needs a merchant account.
PAYMENT_METHODS = {'cash': 'Cash', 'gcash': 'GCash'}
GCASH_REFERENCE_LENGTH = 13
app.jinja_env.globals['PAYMENT_METHODS'] = PAYMENT_METHODS   # labels for templates

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
            'quantity': quantity, 'category': category,
            'has_options': bool(form.get('has_options'))}, None   # tick box (v0.16.0)

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
    ('product', 'image', 'VARCHAR(100)'),                    # v0.14.0
    ('sale', 'payment_method', "VARCHAR(10) NOT NULL DEFAULT 'cash'"),   # v0.15.0
    ('sale', 'payment_reference', 'VARCHAR(20)'),            # v0.15.0
    ('product', 'has_options', 'BOOLEAN NOT NULL DEFAULT 0'),  # v0.16.0
    ('sale_item', 'options', 'VARCHAR(200)'),                # v0.16.0
]
# ALTER TABLE can't add a UNIQUE rule, so it is added as a separate "unique index" (v0.15.0).
# (Empty values don't count as duplicates, so cash sales without a reference are fine.)
NEW_INDEXES = [
    'CREATE UNIQUE INDEX IF NOT EXISTS ix_sale_payment_reference ON sale (payment_reference)',
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
        for statement in NEW_INDEXES:
            connection.execute(db.text(statement))


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


@app.after_request
def add_security_headers(response):
    """Extra instructions for the browser on every page (v0.13.4)."""
    # Other websites may not show our pages inside a frame (stops "clickjacking":
    # tricking you into clicking our buttons through an invisible frame)
    response.headers['X-Frame-Options'] = 'DENY'
    # Treat files exactly as the type we say (an uploaded "picture" is never run as a page)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # Don't tell other websites which of our pages a link was clicked on
    response.headers['Referrer-Policy'] = 'same-origin'
    return response


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
        picture, picture_error = read_uploaded_picture(request.files.get('picture'))
        if error or picture_error:
            # Show the form again with the error message; nothing is saved
            return render_template('add_product.html', error=error or picture_error)
        new_product = Product(**data)
        if picture:
            new_product.image = save_picture(picture, PRODUCT_IMAGE_FOLDER, 'product')
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
        picture, picture_error = read_uploaded_picture(request.files.get('picture'))
        if error or picture_error:
            return render_template('edit_product.html', product=product, error=error or picture_error)
        product.name = data['name']
        product.sku = data['sku']
        product.price = data['price']
        product.quantity = data['quantity']
        product.category = data['category']
        product.has_options = data['has_options']
        # Picture (v0.14.0): a new upload replaces the old one; the tick box removes it
        if picture or request.form.get('remove_picture'):
            delete_picture_file(PRODUCT_IMAGE_FOLDER, product.image)
            product.image = save_picture(picture, PRODUCT_IMAGE_FOLDER, 'product') if picture else None
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
    delete_picture_file(PRODUCT_IMAGE_FOLDER, product.image)   # its picture goes too (v0.14.0)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('products'))

# ---------------- Sizes and add-ons (v0.16.0) ----------------
OPTION_KINDS = {'size': 'size', 'addon': 'add-on'}


@app.route('/options', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_options():
    """Admin page to add, rename, reprice and hide sizes and add-ons.
    Options are hidden rather than deleted, because old receipts and recipes refer to them."""
    if request.method == 'POST':
        option_id = request.form.get('option_id', type=int)
        kind = request.form.get('kind', '')
        name = request.form.get('name', '').strip()
        try:
            price = float(request.form.get('price', ''))
        except ValueError:
            price = None
        if option_id:   # editing an existing option
            option = find_by_id(MenuOption, option_id) or abort(404)
            kind = option.kind
        elif kind not in OPTION_KINDS:
            abort(400)
        if not name or len(name) > 50:
            flash('The name must be 1 to 50 characters.', 'danger')
        elif price is None or not math.isfinite(price) or price < 0 or price > MAX_PRICE:
            flash(f'The extra price must be a number from 0 to ₱{MAX_PRICE:,}.', 'danger')
        elif (MenuOption.query.filter(MenuOption.kind == kind, func.lower(MenuOption.name) == name.lower(),
                                      MenuOption.id != (option_id or 0)).first()):
            flash(f'There is already a {OPTION_KINDS[kind]} called "{name}".', 'danger')
        else:
            if not option_id:
                last = db.session.query(func.max(MenuOption.sort_order)).filter_by(kind=kind).scalar() or 0
                option = MenuOption(kind=kind, sort_order=last + 1)
                db.session.add(option)
            option.name = name
            option.price = round(price, 2)
            option.active = bool(request.form.get('active')) if option_id else True
            db.session.commit()
            flash(f'Saved {OPTION_KINDS[kind]} "{name}".', 'success')
        return redirect(url_for('manage_options'))
    in_order = (MenuOption.sort_order, MenuOption.id)
    return render_template('options.html',
                           sizes=MenuOption.query.filter_by(kind='size').order_by(*in_order).all(),
                           addons=MenuOption.query.filter_by(kind='addon').order_by(*in_order).all())


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

# ---------------- Sale processing (v0.8.0, options since v0.16.0) ----------------
# The basket is kept in the session (a small storage area Flask keeps for each
# logged-in browser) as a dictionary: {"line key": quantity}.
# A line key is the product id, plus the chosen size and add-ons for drinks (v0.16.0):
#   "7"          -> product 7, no options
#   "7:2:1.4"    -> product 7, size option 2, add-on options 1 and 4
# So "Sea Salt 16oz + Oat" and "Sea Salt 12oz" are separate basket lines.
# Nothing is saved to the database until the sale is completed.

def get_basket():
    return session.get('basket', {})

def save_basket(basket):
    session['basket'] = basket


def make_line_key(product_id, size_id=None, addon_ids=()):
    """Build a basket line key (see above). Add-ons are sorted so the same choice
    always gives the same key, whatever order they were ticked in."""
    if size_id is None and not addon_ids:
        return str(product_id)
    return f"{product_id}:{size_id or ''}:{'.'.join(str(i) for i in sorted(set(addon_ids)))}"


def read_line(key, quantity):
    """Turn a basket key into a line: product, size, add-ons, unit price and subtotal.
    Returns (line, problem). problem is a message when the line can no longer be sold
    (product deleted, or an option removed or hidden by the admin)."""
    parts = key.split(':')
    try:
        product_id = int(parts[0])
        size_id = int(parts[1]) if len(parts) > 1 and parts[1] else None
        addon_ids = [int(i) for i in parts[2].split('.')] if len(parts) > 2 and parts[2] else []
    except ValueError:
        return None, 'An item in the basket was not understood, so it was taken out.'
    product = find_by_id(Product, product_id)
    if product is None:
        # The product was deleted after it was added (v0.8.5)
        return None, ('A product in the basket was deleted from the product list, '
                      'so it was taken out of the basket. Please check the total.')
    size = db.session.get(MenuOption, size_id) if size_id else None
    addons = [db.session.get(MenuOption, i) for i in addon_ids]
    if ((size_id and (size is None or not size.active or size.kind != 'size'))
            or any(a is None or not a.active or a.kind != 'addon' for a in addons)):
        return None, (f'A size or add-on chosen for {product.name} is no longer offered, '
                      f'so that line was taken out of the basket.')
    unit_price = round(product.price + (size.price if size else 0) + sum(a.price for a in addons), 2)
    options_text = ', '.join(([size.name] if size else []) + [a.name for a in addons])   # e.g. "16oz, Sub Oat"
    return {'key': key, 'product': product, 'size': size, 'addons': addons, 'quantity': quantity,
            'unit_price': unit_price, 'options': options_text,
            'subtotal': round(unit_price * quantity, 2)}, None


def basket_lines(basket):
    """All readable lines of the basket. Unreadable ones are removed; returns (lines, message)."""
    lines, message = [], None
    for key, quantity in list(basket.items()):   # list(): we may remove items while looping
        line, problem = read_line(key, quantity)
        if problem:
            basket.pop(key)
            message = message or problem
            continue
        lines.append(line)
    return lines, message


def units_in_basket(basket, product_id):
    """How many of one product are in the basket, across all its sizes and add-ons."""
    return sum(q for key, q in basket.items() if key.split(':')[0] == str(product_id))


def show_sale_page(error=None):
    """Build the basket lines and total, then show the New Sale page."""
    basket = get_basket()
    lines, problem = basket_lines(basket)
    error = error or problem
    save_basket(basket)
    total = round(sum(line['subtotal'] for line in lines), 2)
    # Products that can still be added: stock minus what is already in the basket.
    # (The real stock in the database only goes down when the sale is completed.)
    # Menu order (v0.14.2): grouped by category (products without one last), then by name
    in_menu_order = (Product.category.is_(None), Product.category, Product.name)
    choices = []
    for product in Product.query.filter(Product.quantity > 0).order_by(*in_menu_order).all():
        available = product.quantity - units_in_basket(basket, product.id)
        if available > 0:
            choices.append({'product': product, 'available': available})
    sizes = MenuOption.query.filter_by(kind='size', active=True).order_by(MenuOption.sort_order, MenuOption.id).all()
    addons = MenuOption.query.filter_by(kind='addon', active=True).order_by(MenuOption.sort_order, MenuOption.id).all()
    return render_template('new_sale.html', choices=choices, lines=lines, total=total,
                           sizes=sizes, addons=addons, error=error)


@app.route('/sales/new', methods=['GET', 'POST'])
@login_required
def new_sale():
    if request.method == 'POST':
        # A tile, the options window or the "Add to basket" form was submitted
        product = find_by_id(Product, request.form.get('product_id', type=int))
        quantity = request.form.get('quantity', type=int)  # None if not a whole number

        if product is None:
            return show_sale_page('Please choose a product.')
        if quantity is None or quantity < 1:
            return show_sale_page('Quantity must be a whole number of at least 1.')

        # Size and add-ons (v0.16.0), only for products that offer them
        size_id, addon_ids = None, []
        if product.has_options:
            sizes = MenuOption.query.filter_by(kind='size', active=True).order_by(MenuOption.sort_order, MenuOption.id).all()
            size_id = request.form.get('size_id', type=int)
            if sizes:
                if size_id is None:
                    size_id = sizes[0].id          # the smallest size if none was chosen (e.g. the list form)
                if size_id not in [s.id for s in sizes]:
                    return show_sale_page('Please choose one of the sizes offered.')
            else:
                size_id = None
            active_addons = {a.id for a in MenuOption.query.filter_by(kind='addon', active=True)}
            try:
                addon_ids = sorted({int(i) for i in request.form.getlist('addon_ids')})
            except ValueError:
                return show_sale_page('Please choose add-ons from the list.')
            if not set(addon_ids) <= active_addons:
                return show_sale_page('Please choose add-ons from the list.')

        basket = get_basket()
        available = product.quantity - units_in_basket(basket, product.id)   # what can still be added
        if quantity > available:
            return show_sale_page(f'Not enough stock for {product.name}: only {available} more can be added.')

        key = make_line_key(product.id, size_id, addon_ids)
        basket[key] = basket.get(key, 0) + quantity
        save_basket(basket)
        return redirect(url_for('new_sale'))

    return show_sale_page()


@app.route('/sales/remove/<int:product_id>', methods=['POST'])
@login_required
def remove_from_basket(product_id):
    """Take every line of this product out of the basket."""
    basket = get_basket()
    for key in [k for k in basket if k.split(':')[0] == str(product_id)]:
        basket.pop(key)
    save_basket(basket)
    return redirect(url_for('new_sale'))


@app.route('/sales/remove-line', methods=['POST'])
@login_required
def remove_line():
    """Take one basket line (one product with its size and add-ons) out (v0.16.0)."""
    basket = get_basket()
    basket.pop(request.form.get('line', ''), None)   # harmless if it isn't there
    save_basket(basket)
    return redirect(url_for('new_sale'))


@app.route('/sales/complete', methods=['POST'])
@login_required
def complete_sale():
    basket = get_basket()
    if not basket:
        return show_sale_page('The basket is empty.')

    # Step 1: check EVERY line first and work out the total. Stock may have changed
    # since it was added (for example, another cashier sold the last one).
    lines, problem = basket_lines(basket)
    if problem:
        save_basket(basket)
        return show_sale_page(problem)
    units = {}   # product -> units in the whole basket (one product can be on several lines)
    for line in lines:
        units[line['product']] = units.get(line['product'], 0) + line['quantity']
    for product, quantity in units.items():
        if quantity > product.quantity:
            return show_sale_page(f'{product.name} no longer has enough stock. '
                                  f'Please remove it and add it again with a smaller quantity.')
    total = round(sum(line['subtotal'] for line in lines), 2)

    # Step 2: check the payment (v0.15.0: cash or GCash)
    method = request.form.get('payment_method', 'cash')
    reference = None
    if method == 'gcash':
        # The cashier types the reference number shown on the customer's GCash receipt.
        # Spaces are allowed while typing ("1234 567 890123") and removed here.
        reference = ''.join(request.form.get('gcash_reference', '').split())
        if not re.fullmatch(r'[0-9]{%d}' % GCASH_REFERENCE_LENGTH, reference):
            return show_sale_page(f'The GCash reference number must be the {GCASH_REFERENCE_LENGTH} digits '
                                  f'shown on the customer\'s GCash receipt.')
        used = Sale.query.filter_by(payment_reference=reference).first()
        if used:
            return show_sale_page(f'GCash reference {reference} was already used on receipt #{used.id}. '
                                  f'Check the number on the customer\'s screen.')
        cash = total   # GCash pays the exact amount: no change
    elif method == 'cash':
        cash = request.form.get('cash_received', type=float)  # None if not a number
        if cash is None or not math.isfinite(cash) or cash < total or cash > MAX_CASH:
            return show_sale_page(f'Cash received must be a number of at least ₱{total:,.2f} '
                                  f'(and at most ₱{MAX_CASH:,}).')
    else:
        return show_sale_page('Please choose how the customer pays: Cash or GCash.')

    # Step 3: everything is fine, so create the sale and deduct stock
    sale = Sale(user_id=current_user.id, total=total,
                cash_received=round(cash, 2), change_due=round(cash - total, 2),
                payment_method=method, payment_reference=reference)
    for product, quantity in units.items():
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
    for line in lines:
        # One receipt line per basket line. The price includes the size and add-ons,
        # and the options are copied as text, so old receipts stay correct (v0.16.0)
        sale.items.append(SaleItem(product_id=line['product'].id, product_name=line['product'].name,
                                   unit_price=line['unit_price'], quantity=line['quantity'],
                                   options=line['options'] or None))

    db.session.add(sale)
    try:
        db.session.commit()   # saves the sale, its items and the new stock levels together
    except IntegrityError:
        # Two sales with the same GCash reference at the same moment: the unique rule
        # in the database stops the second one; nothing of it is saved (v0.15.0)
        db.session.rollback()
        return show_sale_page(f'GCash reference {reference} was just used by another sale. '
                              f'Check the number on the customer\'s screen.')
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

    # Money in by payment method (v0.15.0): what should be in the drawer vs. in GCash
    by_method = {key: round(sum(s.total for s in sales if s.payment_method == key), 2)
                 for key in PAYMENT_METHODS}

    return render_template('sales_report.html', sales=sales, revenue=revenue,
                           items_sold=items_sold, top_products=top_products,
                           by_method=by_method, start=start, end=end, error=error)


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


def read_uploaded_picture(file):
    """Read an optional picture from a form (v0.14.0).
    Returns (picture, error): picture is (bytes, 'png'/'jpg'/'webp') or None if no file was chosen."""
    if file is None or not file.filename:   # the file box was left empty
        return None, None
    data = file.read()
    kind = detect_image_type(data)
    if kind is None:
        return None, "The picture must be a PNG, JPG or WebP file."
    return (data, kind), None


def save_picture(picture, folder, prefix):
    """Save picture = (bytes, kind) under a random name in folder; return the file name.
    Random names mean nobody can guess or overwrite another file."""
    data, kind = picture
    os.makedirs(folder, exist_ok=True)
    filename = f'{prefix}_{secrets.token_hex(8)}.{kind}'
    with open(os.path.join(folder, filename), 'wb') as f:
        f.write(data)
    return filename


def delete_picture_file(folder, filename):
    """Remove a picture file if it exists. basename() keeps it inside the folder."""
    if filename:
        path = os.path.join(folder, os.path.basename(filename))
        if os.path.exists(path):
            os.remove(path)


def delete_avatar_file(user):
    """Remove the user's current picture file, if any."""
    delete_picture_file(AVATAR_FOLDER, user.avatar)


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


# ---------------- Change password (v0.13.5) ----------------
MIN_PASSWORD_LENGTH = 8


@app.route('/profile/password', methods=['POST'])
@login_required
def change_password():
    """Lets a user replace a default password like admin123 with their own."""
    current = request.form.get('current_password', '')
    new = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')
    if not check_password_hash(current_user.password_hash, current):
        flash('Current password is wrong. Nothing was changed.', 'danger')
    elif new != confirm:
        flash('The new passwords do not match.', 'danger')
    elif new.lower() == current_user.username.lower():
        flash("Your password can't be the same as your username.", 'danger')
    elif len(new) < MIN_PASSWORD_LENGTH:
        flash(f'The new password must be at least {MIN_PASSWORD_LENGTH} characters long.', 'danger')
    elif new == current:
        flash('The new password is the same as the current one.', 'danger')
    else:
        current_user.password_hash = generate_password_hash(new)   # stored scrambled, never as plain text
        db.session.commit()
        flash('Password changed. Use the new one next time you log in.', 'success')
    return redirect(url_for('profile'))


# ---------------- Product pictures (v0.14.0) ----------------
PRODUCT_IMAGE_FOLDER = os.path.join(app.static_folder, 'products')

# Products without a picture get a coloured tile with an icon. The first rule whose
# words appear in the product's name (or else its category) decides the icon and colour.
PRODUCT_ICON_RULES = [
    (('iced', 'cold', 'frappe', 'shake', 'smoothie'), 'bi-cup-straw', 3),
    (('cake', 'cheesecake'), 'bi-cake2', 4),
    (('pastr', 'bread', 'croissant', 'cookie', 'roll', 'ensaymada', 'muffin', 'donut', 'bakery'), 'bi-cookie', 2),
    (('non-coffee', 'tea', 'matcha', 'chocolate', 'milk'), 'bi-cup', 0),
    (('coffee', 'espresso', 'latte', 'americano', 'cappuccino', 'macchiato', 'brewed'), 'bi-cup-hot', 1),
    (('meal', 'sandwich', 'pasta', 'food', 'snack'), 'bi-egg-fried', 1),
]


@app.template_global()
def product_image_url(product):
    """Web address of the product's picture, or None to show the icon tile instead."""
    if product.image and os.path.exists(os.path.join(PRODUCT_IMAGE_FOLDER, os.path.basename(product.image))):
        return url_for('static', filename='products/' + product.image)
    return None


@app.template_global()
def product_icon(product):
    """(icon, colour number 0-4) for a product without a picture."""
    for text in (product.name or '', product.category or ''):
        text = text.lower()
        for words, icon, hue in PRODUCT_ICON_RULES:
            if any(word in text for word in words):
                return icon, hue
    return 'bi-box-seam', 0


@app.errorhandler(413)
def too_large(e):
    flash('That picture is too big. The limit is 2 MB.', 'danger')
    # Send the user back to the form they came from (v0.14.0: product forms too).
    # request.path is our own address, so this can't send anyone to another website.
    if request.path == url_for('add_product') or request.path.startswith('/products/edit/'):
        return redirect(request.path)
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
    # Debug mode shows an in-browser console that can run Python code when something crashes,
    # so it is OFF unless you ask for it (v0.13.4). While coding:  $env:FLASK_DEBUG = "1"
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')

