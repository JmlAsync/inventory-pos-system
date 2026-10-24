from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from flask_login import UserMixin

db = SQLAlchemy()


def utc_now():
    """The current time in UTC, without a time-zone label, as every time is stored (v0.23.1, DEC-024).
    The pages show it in the shop's time (UTC+8) with the shop_time filter in app.py."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


CENT = Decimal('0.01')


def to_money(amount):
    """An amount in pesos as an exact Decimal rounded to the centavo, half up: 0.125 -> 0.13 (v0.23.2).
    Accepts what forms and code give: text, int, float or Decimal."""
    return Decimal(str(amount)).quantize(CENT, rounding=ROUND_HALF_UP)


class Money(db.TypeDecorator):
    """A money column (v0.23.2, DEF-68, DEC-025): stored as whole centavos (INTEGER: P75.50 -> 7550), so sums are
    exact on every database; Python sees exact Decimal pesos (75.50), never a float that could drift."""
    impl = db.Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else int(to_money(value) * 100)

    def process_result_value(self, value, dialect):
        return None if value is None else (Decimal(value) / 100).quantize(CENT)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    price = db.Column(Money, nullable=False)   # whole centavos in the database (v0.23.2)
    quantity = db.Column(db.Integer, default=0)
    category = db.Column(db.String(50))
    # File name of the product's picture in static/products/, or None (v0.14.0)
    image = db.Column(db.String(100))
    # True for drinks: the cashier picks a size and may add add-ons (v0.16.0)
    has_options = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        return f"<Product {self.name}>"

ROLES = ('owner', 'admin', 'cashier')   # v0.27.0: the owner is the one account from the subscription (rule S12)


class User(db.Model, UserMixin):
    # v0.27.0 (DEC-029): the database allows only ONE owner: a unique index on role, only for rows where it is 'owner'
    __table_args__ = (db.Index('uq_user_one_owner', 'role', unique=True,
                               sqlite_where=db.text("role = 'owner'"), postgresql_where=db.text("role = 'owner'")),)
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)   # 'owner', 'admin' or 'cashier' (ROLES)
    # File name of the profile picture inside static/avatars, or None (v0.12.0)
    avatar = db.Column(db.String(100))
    # v0.27.0 (DEC-029): the person's own email, in lower case (empty for accounts made before v0.27.0 until they
    # add one), and when they proved it with a code
    email = db.Column(db.String(254), unique=True)
    email_verified_at = db.Column(db.DateTime)
    # Switched off instead of deleted, because receipts name their cashier. Flask-Login refuses a switched-off account.
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)   # "Require a new password" (audit A5)
    can_invite = db.Column(db.Boolean, nullable=False, default=False)   # an admin the owner allowed to invite cashiers
    created_at = db.Column(db.DateTime, default=utc_now)
    # v0.28.0 (rule S13, DEC-017, DEC-030): the second step at login, 'email' (a code by email) or 'app' (an
    # authenticator app). The app's key is stored ENCRYPTED (it can't be hashed: the server works out codes from it);
    # totp_last_step is the last 30-second step accepted, so a code can't be used twice (S14).
    second_step = db.Column(db.String(10), nullable=False, default='email')
    totp_key_encrypted = db.Column(db.Text)
    totp_pending_encrypted = db.Column(db.Text)   # during set-up, until the first code proves the scan
    totp_last_step = db.Column(db.Integer)
    # v0.29.0 (DEC-031): Google's permanent id for this person, when they linked Google. Never the email: an address
    # can change hands, the id can't.
    google_sub = db.Column(db.String(255), unique=True)

    @property
    def is_owner(self):
        return self.role == 'owner'

    @property
    def is_admin(self):
        """True for admins AND the owner: the owner can do everything an admin can (v0.27.0)."""
        return self.role in ('admin', 'owner')

    @property
    def initials(self):
        """Up to two letters for the round avatar when there's no picture,
        e.g. 'admin' -> 'AD', 'maria.santos' -> 'MS'."""
        parts = self.username.replace('.', ' ').replace('_', ' ').split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return self.username[:2].upper()


class LoginSession(db.Model):
    """One logged-in browser (v0.20.3, DEF-51). The login cookie only carries this row's random token.
    Logging out deletes the row, so a copied cookie stops working; a password change deletes the
    user's other rows; a row that has been idle for 8 hours no longer counts."""
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)   # 64 random characters, nothing secret about the user
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    last_seen = db.Column(db.DateTime, default=utc_now, nullable=False)


class LoginAttempt(db.Model):
    """One try at something with a limit, such as a password (v0.26.0, DEC-028, audit R2 and A7). Kept in the
    database, so the 5-tries limit survives a restart and holds for every server process. The key is a keyed hash
    of what is limited ("login|username|computer" or "password|user id"), never the text someone typed."""
    __tablename__ = 'login_attempt'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), nullable=False, index=True)        # HMAC-SHA256 in hex: always 64 characters
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)


class ShopProfile(db.Model):
    """The shop's own details for receipts (v0.22.0, F21, DEC-022). One row only (id 1); the owner
    edits it on Shop details. Kept in the database so it moves with the shop's data."""
    __tablename__ = 'shop_profile'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False, default='Inventory & POS')
    address = db.Column(db.String(120), nullable=False, default='')
    tin = db.Column(db.String(20), nullable=False, default='')       # Tax Identification Number, optional
    footer = db.Column(db.String(120), nullable=False, default='')   # e.g. "Thank you! See you again."


class Sale(db.Model):
    """One customer purchase (one 'receipt'). A Sale contains one or more SaleItems."""
    id = db.Column(db.Integer, primary_key=True)
    # When the sale happened. default=utc_now fills it in automatically.
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    # Which user (cashier or admin) made the sale. ForeignKey links to the user table.
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total = db.Column(Money, nullable=False, default=0)   # Money: whole centavos (v0.23.2)
    cash_received = db.Column(Money, nullable=False, default=0)  # money the customer handed over
    change_due = db.Column(Money, nullable=False, default=0)     # cash_received - total
    # How the customer paid (v0.15.0): 'cash' or 'gcash'. For GCash, the 13-digit reference
    # number from the customer's GCash receipt; unique, so one payment can't be used twice.
    payment_method = db.Column(db.String(10), nullable=False, default='cash')
    payment_reference = db.Column(db.String(20), unique=True)
    # The basket's one-time sale ticket (v0.20.4, DEF-48): unique, so one basket makes one receipt
    ticket = db.Column(db.String(32), unique=True)
    # v0.31.0 (rule I8, DEC-007, DEC-033): the receipt itself never changes. A void or refund is a SaleAdjustment;
    # these two columns only say where the sale stands, so two admins at the same moment can't void it twice or
    # refund more than was paid (each is changed with a conditional update, like stock, rule I1).
    voided_at = db.Column(db.DateTime)                                     # empty = not voided
    refunded_total = db.Column(Money, nullable=False, default=0)          # refunds so far, in whole centavos

    # Relationships: let us write sale.items and sale.user in Python
    items = db.relationship('SaleItem', backref='sale', lazy=True)
    movements = db.relationship('IngredientMovement', backref='sale', lazy=True)   # v0.17.0
    user = db.relationship('User')
    adjustments = db.relationship('SaleAdjustment', backref='sale', lazy=True,
                                  order_by='SaleAdjustment.id')                 # v0.31.0

    @property
    def net_total(self):
        """What the shop kept from this sale: nothing if voided, otherwise the total minus refunds (v0.31.0)."""
        return to_money(0) if self.voided_at else self.total - (self.refunded_total or 0)


class SaleItem(db.Model):
    """One line on a receipt: a product, how many were sold, and the price at that moment."""
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    # Copies of the name and price AT THE TIME OF SALE, so old receipts stay correct
    # even if the product is later renamed, repriced or deleted.
    product_name = db.Column(db.String(100), nullable=False)
    unit_price = db.Column(Money, nullable=False)   # whole centavos (v0.23.2)
    quantity = db.Column(db.Integer, nullable=False)
    # Size and add-ons chosen, copied as text, e.g. "16oz, Oat Milk" (v0.16.0).
    # unit_price already includes their extra cost.
    options = db.Column(db.String(200))
    # v0.31.0 (DEC-033): how many of this line were refunded so far (never more than quantity: a conditional update),
    # and whether its stock came from a recipe (True: ingredients, listed in SaleItemUsage) or from the product's own
    # count (False). Empty for lines sold before v0.31.0.
    refunded_quantity = db.Column(db.Integer, nullable=False, default=0)
    used_recipe = db.Column(db.Boolean)
    usage = db.relationship('SaleItemUsage', lazy=True)

    @property
    def subtotal(self):
        return round(self.unit_price * self.quantity, 2)

    @property
    def refundable_quantity(self):
        return self.quantity - (self.refunded_quantity or 0)


class SaleItemUsage(db.Model):
    """How much of one ingredient ONE receipt line used (v0.31.0, DEC-033). The sale's history lines add these up
    per ingredient; keeping each line's share means a refund of one latte returns exactly that latte's milk, even if
    the recipe has changed since."""
    __tablename__ = 'sale_item_usage'
    id = db.Column(db.Integer, primary_key=True)
    sale_item_id = db.Column(db.Integer, db.ForeignKey('sale_item.id'), nullable=False, index=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)   # for the line's whole quantity


ADJUSTMENT_KINDS = ('void', 'refund')
ADJUSTMENT_STATUSES = ('requested', 'approved', 'rejected')


class SaleAdjustment(db.Model):
    """A void or a refund of a sale (v0.31.0, rules I8 and S15, DEC-007, DEC-033, plan §4.1). A new record that points
    to the receipt, which itself never changes. A void is requested (by anyone) and approved or rejected by an admin;
    a refund is made by an admin and is approved at once. Never edited after the decision, never deleted."""
    __tablename__ = 'sale_adjustment'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False, index=True)
    kind = db.Column(db.String(10), nullable=False)                           # ADJUSTMENT_KINDS
    status = db.Column(db.String(10), nullable=False, default='requested')    # ADJUSTMENT_STATUSES
    total = db.Column(Money, nullable=False, default=0)                       # money given back
    # How the money went back: 'cash' from the drawer, or 'gcash' sent in the shop's GCash app, with that transfer's
    # 13-digit reference (unique, so one transfer can't be claimed twice). Set when approved.
    method = db.Column(db.String(10))
    reference = db.Column(db.String(20), unique=True)
    reason = db.Column(db.String(200), nullable=False)
    requested_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    requested_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    decided_by = db.Column(db.Integer, db.ForeignKey('user.id'))              # the admin who approved or rejected
    decided_at = db.Column(db.DateTime)
    decided_how = db.Column(db.String(10))           # 'password' (on the admin's own screen) or 'code' (by email)
    note = db.Column(db.String(200))                 # why it was rejected
    lines = db.relationship('AdjustmentLine', backref='adjustment', lazy=True, order_by='AdjustmentLine.id')
    requester = db.relationship('User', foreign_keys=[requested_by])
    decider = db.relationship('User', foreign_keys=[decided_by])


class AdjustmentLine(db.Model):
    """One receipt line in a void or refund (v0.31.0): how many, the money, and whether the stock went back on the
    shelf (restock) or was thrown away (waste: a made drink can't be sold again)."""
    __tablename__ = 'adjustment_line'
    id = db.Column(db.Integer, primary_key=True)
    adjustment_id = db.Column(db.Integer, db.ForeignKey('sale_adjustment.id'), nullable=False, index=True)
    sale_item_id = db.Column(db.Integer, db.ForeignKey('sale_item.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    amount = db.Column(Money, nullable=False)
    restock = db.Column(db.Boolean, nullable=False, default=True)
    item = db.relationship('SaleItem')


class MenuOption(db.Model):
    """A size (e.g. 16oz) or an add-on (e.g. Oat Milk) that drinks can have (v0.16.0).
    price is the EXTRA cost on top of the product's own price (0 for the base size)."""
    __tablename__ = 'menu_option'
    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(10), nullable=False)       # 'size' or 'addon'
    name = db.Column(db.String(50), nullable=False)
    price = db.Column(Money, nullable=False, default=0)   # whole centavos (v0.23.2)
    active = db.Column(db.Boolean, nullable=False, default=True)   # hidden options aren't offered
    sort_order = db.Column(db.Integer, nullable=False, default=0)  # smaller numbers first
    # Sizes only (v0.17.0): how much of every ingredient this size uses compared with the
    # recipe, e.g. 1.33 for a 16oz when recipes are written for a 12oz
    scale = db.Column(db.Float, nullable=False, default=1.0)


class Ingredient(db.Model):
    """Something the café uses up to make products: beans, milk, croissant dough... (v0.17.0)"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    unit = db.Column(db.String(10), nullable=False, default='g')    # g, ml or pcs
    quantity = db.Column(db.Float, nullable=False, default=0)       # how much is on hand
    low_at = db.Column(db.Float, nullable=False, default=0)         # warn at or below this
    # v0.18.0: a group for the Ingredients page, and the amount when the shelf is full
    # (0 = not set). The stock bar shows quantity / full_at.
    category = db.Column(db.String(30), nullable=False, default='Other')
    full_at = db.Column(db.Float, nullable=False, default=0)


class RecipeItem(db.Model):
    """How much of one ingredient ONE product (at the default size) or ONE option uses (v0.17.0).
    Exactly one of product_id / option_id is set. Option amounts may be negative to
    replace an ingredient, e.g. Oat Milk: fresh milk -180 ml, oat milk +180 ml."""
    id = db.Column(db.Integer, primary_key=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    option_id = db.Column(db.Integer, db.ForeignKey('menu_option.id'))
    amount = db.Column(db.Float, nullable=False)
    ingredient = db.relationship('Ingredient')
    product = db.relationship('Product')        # v0.18.0: for "Used in" on an ingredient's page
    option = db.relationship('MenuOption')


class IngredientMovement(db.Model):
    """One change to an ingredient's stock, so every change can be traced (v0.17.0):
    'sale' (used up by a sale), 'restock' (delivery received) or 'count' (stock count).
    v0.30.0 added 'count-undo'; v0.31.0 'void' and 'refund' (back on the shelf) and 'waste' (came back, thrown away)."""
    id = db.Column(db.Integer, primary_key=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    change = db.Column(db.Float, nullable=False)               # + added, - used
    reason = db.Column(db.String(10), nullable=False)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    # v0.31.0: the void or refund that wrote this line (reason 'void', 'refund' or 'waste')
    adjustment_id = db.Column(db.Integer, db.ForeignKey('sale_adjustment.id'))
    ingredient = db.relationship('Ingredient')
    user = db.relationship('User')


class Invitation(db.Model):
    """An invitation to join the shop (v0.27.0, rule S12, DEC-003, DEC-029). The link in the email carries a random
    token; only its keyed hash is kept here (S14). It works for 48 hours, once. The role is the inviter's choice:
    nothing the new person types can change it."""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    invited_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)          # when the account was made
    cancelled_at = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))   # the account it made
    # Between the two signup steps: the chosen username and the password's hash, until the code is entered
    pending_username = db.Column(db.String(50))
    pending_password_hash = db.Column(db.String(200))
    pending_google_sub = db.Column(db.String(255))   # v0.29.0: joining with Google, until the code is entered
    inviter = db.relationship('User', foreign_keys=[invited_by])


class EmailCode(db.Model):
    """A 6-digit code sent by email (v0.27.0, rule S14, DEC-029): stored only as a keyed hash, valid for 10 minutes,
    one use, one purpose ('signup', 'reset' or 'email'; v0.31.0 'void': approving one void), at most 5 wrong tries."""
    __tablename__ = 'email_code'
    id = db.Column(db.Integer, primary_key=True)
    purpose = db.Column(db.String(10), nullable=False)
    email = db.Column(db.String(254), nullable=False, index=True)   # where it was sent
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    invitation_id = db.Column(db.Integer, db.ForeignKey('invitation.id'))
    adjustment_id = db.Column(db.Integer, db.ForeignKey('sale_adjustment.id'))   # v0.31.0: purpose 'void'
    code_hash = db.Column(db.String(64), nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)   # used, cancelled by a newer code, or 5 wrong tries


class AuditEntry(db.Model):
    """One line of the audit log (v0.27.0, audit R9, DEC-029): who changed what, when, with the old and new values.
    Written by the store/ function that makes the change, in the same commit. Never edited or deleted."""
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))   # who; empty for setup_shop.py on the computer
    action = db.Column(db.String(40), nullable=False, index=True)   # e.g. 'product.update', 'user.role'
    target = db.Column(db.String(120), nullable=False)              # e.g. 'Latte (L1)', 'maria'
    details = db.Column(db.Text, nullable=False, default='{}')      # JSON: {"price": ["150.00", "160.00"]}
    user = db.relationship('User')


class TrustedDevice(db.Model):
    """A browser where this user skips the login code (v0.28.0, rule S13, DEC-005, DEC-030): 30 days, 7 for admins and
    the owner. The browser's cookie holds a random token; only its keyed hash is here (S14). Ends on Remove, Log out
    everywhere, a password change, switching the account off or a role change."""
    __tablename__ = 'trusted_device'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    label = db.Column(db.String(60), nullable=False, default='')   # e.g. "Edge on Windows"
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    last_used_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)


class BackupCode(db.Model):
    """One of 10 one-time codes for when no emailed or app code can be had (v0.28.0, plan §2.6, DEC-030), stored only
    as a keyed hash (S14). Making new ones cancels the old ones."""
    __tablename__ = 'backup_code'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    code_hash = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    used_at = db.Column(db.DateTime)
