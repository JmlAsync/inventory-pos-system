"""Rules and helpers that every part of the system uses (v0.25.0, DEC-027): number limits, looking rows up by id,
the admin check, money and amount formatting, the shop's clock, and picture files.
Moved here unchanged from app.py; the version in each comment is when the rule was first added."""
import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import abort
from flask_login import current_user
from models import db

HERE = os.path.dirname(os.path.abspath(__file__))

# Upper limits for numbers typed into forms (v0.8.3). Generous for a mini-store,
# café or market, but they stop "nan", "inf" and absurdly large values.
MAX_PRICE = 1_000_000      # pesos
MAX_QUANTITY = 1_000_000   # units
MAX_CASH = 1_000_000       # pesos

# Ways to pay (v0.15.0). GCash is only recorded here (the customer pays in their GCash
# app and shows the receipt); connecting to GCash itself needs a merchant account.
PAYMENT_METHODS = {'cash': 'Cash', 'gcash': 'GCash'}
GCASH_REFERENCE_LENGTH = 13

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
    """Admin pages (v0.7.0): anyone else gets 403, even if they type the address (rule S2)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# ---------------- Showing money and amounts ----------------
def peso(amount):
    """Show money the Philippine way, e.g. 6079.5 -> '₱6,079.50' (v0.11.2).
    Used in templates as {{ sale.total|peso }}."""
    return f'₱{amount:,.2f}'


def fmt_amount(amount):
    """18.0 -> '18', 0.5 -> '0.5' (no long decimals on screen)."""
    return f'{amount:,.3f}'.rstrip('0').rstrip('.')


def plain_amount(amount):
    """For number boxes (v0.17.4): no thousands separator, because a type="number" box
    can't read "2,000" and would show up empty."""
    return fmt_amount(amount).replace(',', '')


# ---------------- Times: stored in UTC, shown in the shop's time (v0.23.1, DEF-67, DEC-024) ----------------
# Every time in the database is UTC (models.utc_now). Pages show it, and the report and Home count days, in the
# shop's own time. A cloud server runs on UTC, so the computer's local time can't be trusted for this.
# The Philippines is UTC+8 all year (no daylight saving), so a fixed offset is exact and needs no extra package.
SHOP_TIMEZONE = timezone(timedelta(hours=8), 'PHT')


def shop_now():
    """The current time in the shop (UTC+8), without a time-zone label."""
    return datetime.now(SHOP_TIMEZONE).replace(tzinfo=None)


def to_shop_time(moment):
    """A stored UTC time as the shop's clock showed it."""
    return moment.replace(tzinfo=timezone.utc).astimezone(SHOP_TIMEZONE).replace(tzinfo=None)


def to_utc(shop_moment):
    """A time on the shop's clock as UTC, the way it is stored."""
    return shop_moment.replace(tzinfo=SHOP_TIMEZONE).astimezone(timezone.utc).replace(tzinfo=None)


def shop_day_start_utc(day):
    """When the shop's day (midnight on the shop's clock) begins, in UTC."""
    return to_utc(datetime.combine(day, datetime.min.time()))


# ---------------- Picture files (v0.12.0 profile pictures, v0.14.0 product pictures) ----------------
AVATAR_FOLDER = os.path.join(HERE, 'static', 'avatars')
PRODUCT_IMAGE_FOLDER = os.path.join(HERE, 'static', 'products')


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
