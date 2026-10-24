"""Inventory & POS: the web app (v0.1.0). Since v0.25.0 (DEC-027) this file only STARTS the app: the shop's
settings, the database and migrations, the login manager, the security checks on every request, the error pages,
and the pages from blueprints/. The rules themselves live in common.py, blueprints/ and store/.

    python app.py     the development server (for a shop: start_shop.bat, see serve.py)
"""
import os
import secrets
import sys
import tomllib
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from flask_login import LoginManager
from flask_migrate import Migrate, upgrade as run_migrations
from werkzeug.security import check_password_hash   # kept here for older scripts and tests that look for it
from models import db, utc_now, to_money

app = Flask(__name__)

# ---------------- The shop's settings (v0.24.0, F22, DEC-026) ----------------
# instance/config.toml is written by setup_shop.py: which database to use and how the server listens.
# It is in instance/, so it never goes to GitHub (rule P1). Without it, the defaults below are used.
CONFIG_FILE = os.path.join(app.instance_path, 'config.toml')


def load_config():
    """The settings in instance/config.toml as a dictionary, or {} if there is no such file."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'rb') as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as error:
        # A plain message instead of a traceback: the owner may have edited the file by hand
        print(f'instance/config.toml has a mistake: {error}.', file=sys.stderr)
        print('Fix it in a text editor, or run "python setup_shop.py" again to write a new one.', file=sys.stderr)
        raise SystemExit(1)


CONFIG = load_config()
# DATABASE_URL (an environment variable, as hosting services use) wins over the file; the default is the local file
app.config['SQLALCHEMY_DATABASE_URI'] = (os.environ.get('DATABASE_URL')
                                         or CONFIG.get('database', {}).get('url', 'sqlite:///inventory.db'))
# Email sending (v0.26.0, DEC-028): the [mail] settings, used by mail.py. The MAIL_PASSWORD environment variable
# wins over the file, like DATABASE_URL. Without a [mail] part, email simply isn't set up yet.
app.config['MAIL'] = dict(CONFIG.get('mail', {}))
if os.environ.get('MAIL_PASSWORD'):
    app.config['MAIL']['password'] = os.environ['MAIL_PASSWORD']


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
# Database changes are numbered scripts in migrations/, run by Alembic through Flask-Migrate (v0.23.0, DEC-023).
# render_as_batch: SQLite can't change most columns in place, so Alembic copies the table instead.
MIGRATIONS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'migrations')
migrate = Migrate(app, db, directory=MIGRATIONS_FOLDER, render_as_batch=True)

# ---------------- Database upgrades (v0.12.0; migrations since v0.23.0) ----------------
# Until v0.22.0 this was a list of columns (NEW_COLUMNS) added with ALTER TABLE. Since v0.23.0 every
# change is a numbered script in migrations/versions/ (DEC-023, rule I5). Migration 0001 took over the
# old list, so a database made by any earlier version is brought up to date without losing data.


def pending_migrations():
    """True if this database hasn't had the newest migration yet (v0.23.0)."""
    from alembic.migration import MigrationContext
    from alembic.script import ScriptDirectory
    with db.engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    return current != ScriptDirectory(MIGRATIONS_FOLDER).get_current_head()


def backup_database(before):
    """Copy the SQLite database to instance/inventory_backup_<date-time>_before_<migration>.db (v0.23.0).
    SQLite's own backup feature makes a consistent copy even if the file is in use."""
    import sqlite3
    path = db.engine.url.database
    if db.engine.url.get_backend_name() != 'sqlite' or not path or not os.path.exists(path):
        return None   # a server database (PostgreSQL) is backed up by its provider
    stamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')   # file name in this computer's time: people read it here
    target = os.path.join(os.path.dirname(path), f'inventory_backup_{stamp}_before_{before}.db')
    source, copy = sqlite3.connect(path), sqlite3.connect(target)
    with copy:
        source.backup(copy)
    source.close(); copy.close()
    return target


def upgrade_database():
    """Bring the database up to the newest migration (v0.23.0, DEC-023). Called by "python app.py",
    seed_demo_data.py and the tests. A database that has data gets a backup first."""
    from alembic.script import ScriptDirectory
    tables = set(db.inspect(db.engine).get_table_names())
    if 'alembic_version' in tables and 'user' not in tables:
        # The tables were dropped (tests do this with db.drop_all()) but the migration record stayed:
        # forget the record, so the migrations build everything again from the start
        with db.engine.begin() as connection:
            connection.execute(db.text('DROP TABLE alembic_version'))
        tables.discard('alembic_version')
    if tables - {'alembic_version'} and pending_migrations():
        backup_database(ScriptDirectory(MIGRATIONS_FOLDER).get_current_head())   # nothing is changed without a copy
    run_migrations(directory=MIGRATIONS_FOLDER)
    # Housekeeping on every start, as before v0.23.0: recipe lines of products that no longer exist (v0.17.1, DEF-40)
    with db.engine.begin() as connection:
        connection.execute(db.text('DELETE FROM recipe_item WHERE product_id IS NOT NULL '
                                   'AND product_id NOT IN (SELECT id FROM product)'))


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
login_manager.login_view = 'accounts.login'

# ---------------- The pages (v0.25.0, DEC-027): one blueprint per part of the system ----------------
from common import (MAX_PRICE, MAX_QUANTITY, MAX_CASH, PAYMENT_METHODS, GCASH_REFERENCE_LENGTH, LOW_STOCK_THRESHOLD,
                    MAX_DB_ID, find_by_id, admin_required, peso, fmt_amount, plain_amount, SHOP_TIMEZONE, shop_now,
                    to_shop_time, to_utc, shop_day_start_utc, AVATAR_FOLDER, PRODUCT_IMAGE_FOLDER, detect_image_type,
                    read_uploaded_picture, save_picture, delete_picture_file)
from store.stock import (INGREDIENT_UNITS, INGREDIENT_CATEGORIES, guess_ingredient_category, stock_percent,
                         stock_status, Recipes, add_usage, shortages, default_size, can_make, stock_levels,
                         limiting_ingredient, running_low)
from store.shop import shop_profile
from blueprints import accounts, catalog, ingredients, sales, reports, shop

for blueprint in (accounts.bp, catalog.bp, ingredients.bp, sales.bp, reports.bp, shop.bp):
    app.register_blueprint(blueprint)
login_manager.user_loader(accounts.load_user)   # who is logged in, checked on every request (v0.20.3)

# Filters and values every template can use: {{ sale.total|peso }}, {{ amount|plain_amount }} ...
app.jinja_env.globals['PAYMENT_METHODS'] = PAYMENT_METHODS   # labels for templates (v0.15.0)
app.add_template_filter(peso, 'peso')                       # ₱6,079.50 (v0.11.2)
app.add_template_filter(fmt_amount, 'amount')               # 2,000 / 0.5 (v0.17.0)
app.add_template_filter(plain_amount, 'plain_amount')       # 2000, for number boxes (v0.17.4)
app.add_template_filter(to_shop_time, 'shop_time')          # a stored UTC time on the shop's clock (v0.23.1)


# ---------------- Error pages ----------------
@app.errorhandler(403)
def forbidden(e):
    return render_template('403.html'), 403


@app.errorhandler(413)
def too_large(e):
    flash('That picture is too big. The limit is 2 MB.', 'danger')
    # Send the user back to the form they came from (v0.14.0: product forms too).
    # request.path is our own address, so this can't send anyone to another website.
    if request.path == url_for('catalog.add_product') or request.path.startswith('/products/edit/'):
        return redirect(request.path)
    return redirect(url_for('accounts.profile'))


@app.errorhandler(500)
def server_error(e):
    """A crash shows a friendly page instead of the plain "Internal Server Error" (v0.21.3, DEF-61, audit A11).
    The details go to the server log only; the browser never sees them."""
    db.session.rollback()   # undo anything half-done, so the next request starts clean
    app.logger.error('Unexpected error on %s', request.path, exc_info=getattr(e, 'original_exception', e))
    try:
        return render_template('500.html'), 500
    except Exception:
        # If even the friendly page fails (for example the database is down), send a plain one
        return ('<h1>Something went wrong</h1><p>Nothing was saved. Please go back and try again.</p>'), 500


# ---------------- Names other files and the tests import from app (unchanged since before v0.25.0) ----------------
from blueprints.accounts import (MAX_LOGIN_FAILURES, LOCKOUT_MINUTES, LOCKOUT_WINDOW, MAX_USERNAME_LENGTH,
                                 DUMMY_PASSWORD_HASH, MIN_PASSWORD_LENGTH, IDLE_TIMEOUT, start_login_session,
                                 load_user, avatar_url, attempt_key)   # v0.26.0: failed_logins is now a table
from blueprints.catalog import validate_product_form, product_image_url, product_icon, OPTION_KINDS
from blueprints.sales import (get_basket, save_basket, make_line_key, read_line, basket_lines, quick_cash,
                              menu_tile, usage_rows, STOCK_BAR_FULL)
from blueprints.shop import validate_shop_form, SHOP_LIMITS
from blueprints.reports import EARLIEST_DATE, LATEST_DATE

if __name__ == '__main__':
    with app.app_context():
        upgrade_database()   # backs up, then runs any missing migrations (v0.12.0; v0.23.0)
    # Debug mode shows an in-browser console that can run Python code when something crashes,
    # so it is OFF unless you ask for it (v0.13.4). While coding:  $env:FLASK_DEBUG = "1"
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
