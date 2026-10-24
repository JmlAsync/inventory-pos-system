"""Voids and refunds (v0.31.0, F28, rules I1, I7, I8, S15, DEC-007, DEC-033, plan §4.1).

A receipt is never changed or deleted. A void or a refund is a new SaleAdjustment that points to it, names who asked
and who approved, and writes its own stock and ingredient history lines (reason 'void', 'refund' or 'waste').

    Void    the whole receipt, on the day of the sale. Anyone may REQUEST it; only an admin approves it, with their
            password on their own screen or with a code emailed to them that they pass to the cashier. Everything
            goes back on the shelf.
    Refund  chosen lines and quantities, any day. Admins only. Each line goes back on the shelf (an unopened pastry)
            or is recorded as waste (a made drink).

Two admins at the same moment can't void a receipt twice or refund more than was paid: the sale's state is changed
with conditional updates inside the same transaction as the stock, like a sale (rules I1 and I2).
"""
import secrets
from datetime import timedelta
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from models import (db, Product, Ingredient, IngredientMovement, Sale, SaleItem, SaleAdjustment, AdjustmentLine,
                    EmailCode, User, utc_now, to_money)
from common import keyed_hash, same_secret, shop_now, to_shop_time
from store.audit import note
from store.users import CODE_MINUTES, MAX_CODE_TRIES

VOID_CODE_PURPOSE = 'void'


class AdjustmentRefused(Exception):
    """The void or refund was not saved; the message says why, for the screen. Nothing was changed."""


# ---------------- Reading ----------------
def sold_today(sale):
    """True when the sale was made today on the shop's clock: only then can it be voided (plan §4.1). From v0.32.0
    the day ends at the Z reading instead of at midnight."""
    return to_shop_time(sale.created_at).date() == shop_now().date()


def open_void(sale):
    """The void request of this sale that is still waiting for an admin, or None."""
    return SaleAdjustment.query.filter_by(sale_id=sale.id, kind='void', status='requested').first()


def waiting_voids():
    """Every void request still waiting for an admin, oldest first (the Voids & refunds page)."""
    return SaleAdjustment.query.filter_by(kind='void', status='requested').order_by(SaleAdjustment.id).all()


def waiting_count():
    """How many void requests are waiting (the number next to "Voids & refunds" in the menu)."""
    return SaleAdjustment.query.filter_by(kind='void', status='requested').count()


def decided(limit=50):
    """The newest approved or rejected voids and refunds, newest first."""
    return (SaleAdjustment.query.filter(SaleAdjustment.status != 'requested')
            .order_by(SaleAdjustment.decided_at.desc(), SaleAdjustment.id.desc()).limit(limit).all())


def why_not_void(sale):
    """Why this receipt can't be voided now, or None if it can."""
    if sale.voided_at:
        return 'This receipt is already voided.'
    if sale.refunded_total:
        return 'Part of this receipt was already refunded, so it can\'t be voided. Refund the rest instead.'
    if not sold_today(sale):
        return 'Only today\'s receipts can be voided. For an older receipt, an admin gives a refund instead.'
    return None


def why_not_refund(sale):
    """Why this receipt can't be refunded now, or None if it can."""
    if sale.voided_at:
        return 'This receipt is voided: its money was already given back.'
    if open_void(sale):
        return 'A void is waiting for this receipt. Approve or reject it first.'
    if sale.refunded_total >= sale.total or all(item.refundable_quantity <= 0 for item in sale.items):
        return 'Everything on this receipt was already refunded.'
    return None


def line_usage_known(item):
    """False for a recipe line sold before v0.31.0: its own ingredients weren't kept, so they can't be returned
    exactly (it can still be refunded as waste)."""
    return not item.used_recipe or bool(item.usage)


# ---------------- Stock going back (rule I7) ----------------
def _part(amount, quantity, of):
    """The share of `amount` for `quantity` out of `of` items, to 3 decimals like every ingredient amount."""
    return round(amount * quantity / of, 3)


def _return_stock(adjustment, sale, picks, by):
    """Put stock back for picks = [(sale item, quantity, restock)], with a history line for each ingredient.
    restock=False (waste) changes nothing on the shelf: it writes 'refund' +amount and 'waste' -amount, so the
    history shows what came back and was thrown away. The caller commits."""
    back, wasted = {}, {}   # ingredient id -> amount
    old_sale_lines = []     # recipe lines sold before v0.31.0 (their ingredients weren't kept per line)
    for item, quantity, restock in picks:
        if not item.used_recipe:
            if restock:
                # A product with its own count: add the units back, in one database step (I1)
                Product.query.filter_by(id=item.product_id).update(
                    {Product.quantity: Product.quantity + quantity}, synchronize_session=False)
            continue
        if not item.usage:
            old_sale_lines.append(item)
            continue
        for row in item.usage:
            target = back if restock else wasted
            target[row.ingredient_id] = round(target.get(row.ingredient_id, 0) + _part(row.amount, quantity, item.quantity), 3)
    if old_sale_lines and adjustment.kind == 'void':
        # A void of an older sale returns everything that sale used, read from its own history lines
        back = {}
        for line in sale.movements:
            if line.reason == 'sale':
                back[line.ingredient_id] = round(back.get(line.ingredient_id, 0) - line.change, 3)
    reason = adjustment.kind   # 'void' or 'refund'
    for ingredient_id, amount in back.items():
        if amount <= 0:
            continue
        Ingredient.query.filter_by(id=ingredient_id).update(
            {Ingredient.quantity: Ingredient.quantity + amount}, synchronize_session=False)
        db.session.add(IngredientMovement(ingredient_id=ingredient_id, change=amount, reason=reason, sale_id=sale.id,
                                          adjustment_id=adjustment.id, user_id=by))
    for ingredient_id, amount in wasted.items():
        if amount <= 0:
            continue
        db.session.add(IngredientMovement(ingredient_id=ingredient_id, change=amount, reason=reason, sale_id=sale.id,
                                          adjustment_id=adjustment.id, user_id=by))
        db.session.add(IngredientMovement(ingredient_id=ingredient_id, change=-amount, reason='waste', sale_id=sale.id,
                                          adjustment_id=adjustment.id, user_id=by))


def _save(problem_if_reference_used):
    """Commit; a GCash reference already used by another void or refund (the unique rule) undoes everything."""
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise AdjustmentRefused(problem_if_reference_used)


def _reference_used(reference):
    return f'GCash reference {reference} is already on another void or refund. Check the number in the GCash app.'


# ---------------- Voids ----------------
def request_void(sale, reason, by, commit=True):
    """Ask for this whole receipt to be voided. Returns the request (status 'requested')."""
    problem = why_not_void(sale) or ('A void is already waiting for this receipt.' if open_void(sale) else None)
    if problem:
        raise AdjustmentRefused(problem)
    adjustment = SaleAdjustment(sale_id=sale.id, kind='void', status='requested', total=sale.total, reason=reason,
                                requested_by=by)
    adjustment.lines.extend(AdjustmentLine(sale_item_id=item.id, quantity=item.quantity, amount=item.subtotal,
                                           restock=True) for item in sale.items)
    db.session.add(adjustment)
    db.session.flush()   # gives the request its number for the audit line
    note(by, 'sale.void-request', f'Receipt #{sale.id}', {'total': ['', f'{sale.total:.2f}'], 'reason': ['', reason]})
    if commit:
        db.session.commit()
    return adjustment


def approve_void(adjustment, by, how, method, reference):
    """Approve a waiting void: the sale becomes voided and all its stock goes back, in one transaction.
    how: 'password' or 'code'. Raises AdjustmentRefused (nothing changed) if another admin decided first, the day is
    over, or the receipt was refunded meanwhile."""
    sale = adjustment.sale
    if not sold_today(sale):
        raise AdjustmentRefused('This void can no longer be approved: the receipt is from an earlier day. Reject it, '
                                'and give a refund instead if the customer is owed money.')
    now = utc_now()
    # Both steps change a row only if it is still as expected; the second admin's click finds 0 rows (I1)
    try:
        decided_now = (SaleAdjustment.query.filter_by(id=adjustment.id, status='requested')
                       .update({SaleAdjustment.status: 'approved', SaleAdjustment.decided_by: by,
                                SaleAdjustment.decided_at: now, SaleAdjustment.decided_how: how,
                                SaleAdjustment.method: method, SaleAdjustment.reference: reference},
                               synchronize_session=False))
    except IntegrityError:   # the GCash reference is already on another void or refund (the unique rule)
        db.session.rollback()
        raise AdjustmentRefused(_reference_used(reference))
    voided_now = (Sale.query.filter(Sale.id == sale.id, Sale.voided_at.is_(None), Sale.refunded_total == 0)
                  .update({Sale.voided_at: now}, synchronize_session=False))
    if decided_now == 0 or voided_now == 0:
        db.session.rollback()
        raise AdjustmentRefused('This void was already decided by someone else, or the receipt changed. '
                                'Nothing was changed; the page now shows how it stands.')
    _return_stock(adjustment, sale, [(line.item, line.quantity, True) for line in adjustment.lines], by)
    note(by, 'sale.void', f'Receipt #{sale.id}', {'total': [f'{sale.total:.2f}', '0.00'],
                                                   'method': ['', method], 'approved': ['', how]})
    _save(_reference_used(reference))
    db.session.refresh(adjustment)
    return adjustment


def void_now(sale, reason, by, method, reference):
    """An admin voids a receipt themself: the request and the approval in one transaction."""
    adjustment = request_void(sale, reason, by, commit=False)
    return approve_void(adjustment, by, 'password', method, reference)


def reject_void(adjustment, by, why):
    """Reject a waiting void: nothing changes on the receipt or the shelf. False if it was already decided."""
    rejected = (SaleAdjustment.query.filter_by(id=adjustment.id, status='requested')
                .update({SaleAdjustment.status: 'rejected', SaleAdjustment.decided_by: by,
                         SaleAdjustment.decided_at: utc_now(), SaleAdjustment.decided_how: 'password',
                         SaleAdjustment.note: why or None}, synchronize_session=False))
    if rejected == 0:
        db.session.rollback()
        return False
    note(by, 'sale.void-reject', f'Receipt #{adjustment.sale_id}', {'note': ['', why or '']})
    db.session.commit()
    db.session.refresh(adjustment)
    return True


# ---------------- Refunds ----------------
def refund(sale, picks, by, method, reference, reason):
    """Refund picks = [(sale item, quantity, restock)] of this receipt; admins only (the page checks). Returns the
    refund. The money and every line's quantity are checked and changed in one conditional step each, so two
    refunds at the same moment can't give back more than was paid (plan §4.1)."""
    problem = why_not_refund(sale)
    if problem:
        raise AdjustmentRefused(problem)
    picks = [(item, quantity, restock) for item, quantity, restock in picks if quantity > 0]
    if not picks:
        raise AdjustmentRefused('Choose how many of at least one item to refund.')
    for item, quantity, restock in picks:
        if restock and not line_usage_known(item):
            raise AdjustmentRefused(f'{item.product_name} was sold before each line\'s ingredients were kept, so its '
                                    f'ingredients can\'t be put back exactly. Refund it as waste.')
    amount = to_money(sum(item.unit_price * quantity for item, quantity, _ in picks))
    paid_back = (Sale.query.filter(Sale.id == sale.id, Sale.voided_at.is_(None),
                                   Sale.refunded_total + amount <= Sale.total)
                 .update({Sale.refunded_total: Sale.refunded_total + amount}, synchronize_session=False))
    if paid_back == 0:
        db.session.rollback()
        raise AdjustmentRefused('That is more than is left to refund on this receipt (someone may have refunded '
                                'part of it a moment ago). Nothing was changed.')
    for item, quantity, _ in picks:
        counted = (SaleItem.query.filter(SaleItem.id == item.id, SaleItem.refunded_quantity + quantity <= SaleItem.quantity)
                   .update({SaleItem.refunded_quantity: SaleItem.refunded_quantity + quantity},
                           synchronize_session=False))
        if counted == 0:
            db.session.rollback()
            raise AdjustmentRefused(f'Only {item.refundable_quantity} of {item.product_name} can still be refunded. '
                                    f'Nothing was changed.')
    now = utc_now()
    adjustment = SaleAdjustment(sale_id=sale.id, kind='refund', status='approved', total=amount, reason=reason,
                                method=method, reference=reference, requested_by=by, requested_at=now,
                                decided_by=by, decided_at=now, decided_how='password')
    adjustment.lines.extend(AdjustmentLine(sale_item_id=item.id, quantity=quantity,
                                           amount=to_money(item.unit_price * quantity), restock=restock)
                            for item, quantity, restock in picks)
    db.session.add(adjustment)
    try:
        db.session.flush()   # gives the refund its number; the unique rule checks the GCash reference here
    except IntegrityError:
        db.session.rollback()
        raise AdjustmentRefused(_reference_used(reference))
    _return_stock(adjustment, sale, picks, by)
    note(by, 'sale.refund', f'Receipt #{sale.id}', {'total': ['', f'{amount:.2f}'], 'method': ['', method],
                                                     'reason': ['', reason]})
    _save(_reference_used(reference))
    return adjustment


# ---------------- Approving a void by an emailed code (DEC-033) ----------------
# For when no admin is at the till: the cashier chooses an admin, the admin gets the receipt's details and a code by
# email, and tells the cashier the code only if they agree. The code works for THIS void only, for 10 minutes, once,
# with 5 tries, and is kept only as a keyed hash (rule S14). The approval names that admin.
def admins_to_ask():
    """Admins (and the owner) who can approve by email: switched on, with a confirmed email address."""
    return (User.query.filter(User.role.in_(('owner', 'admin')), User.is_active.is_(True),
                              User.email.isnot(None), User.email_verified_at.isnot(None))
            .order_by(User.username).all())


def _void_code_hash(adjustment, email, code):
    """Bound to the purpose, this void and the admin's address: the code can't approve anything else."""
    return keyed_hash('code', VOID_CODE_PURPOSE, adjustment.id, email.lower(), code)


def new_void_code(adjustment, admin):
    """Make a code for this admin and this void (an older one for the same pair stops working). Returns it."""
    now = utc_now()
    (EmailCode.query.filter(EmailCode.purpose == VOID_CODE_PURPOSE, EmailCode.adjustment_id == adjustment.id,
                            func.lower(EmailCode.email) == admin.email.lower(), EmailCode.used_at.is_(None))
     .update({EmailCode.used_at: now}, synchronize_session=False))
    code = f'{secrets.randbelow(1_000_000):06d}'
    db.session.add(EmailCode(purpose=VOID_CODE_PURPOSE, email=admin.email.lower(), user_id=admin.id,
                             adjustment_id=adjustment.id, code_hash=_void_code_hash(adjustment, admin.email, code),
                             created_at=now, expires_at=now + timedelta(minutes=CODE_MINUTES)))
    db.session.commit()
    return code


def check_void_code(adjustment, code):
    """Check a code typed at the till. Returns (admin, None) when it is right (the code is used up), or (None, tries
    left): 0 when no code for this void can be used any more. Every open code for this void counts the try first, in
    a conditional update, so guessing can't go faster than 5 tries per code (as the login codes, DEC-028)."""
    now = utc_now()
    rows = (EmailCode.query.filter(EmailCode.purpose == VOID_CODE_PURPOSE, EmailCode.adjustment_id == adjustment.id,
                                   EmailCode.used_at.is_(None), EmailCode.expires_at > now).all())
    typed = ''.join(ch for ch in (code or '') if ch.isdigit())[:6]
    left = 0
    for row in rows:
        counted = (EmailCode.query.filter(EmailCode.id == row.id, EmailCode.used_at.is_(None),
                                          EmailCode.attempts < MAX_CODE_TRIES)
                   .update({EmailCode.attempts: EmailCode.attempts + 1}, synchronize_session=False))
        db.session.commit()
        if counted == 0:
            continue
        if len(typed) == 6 and same_secret(row.code_hash, _void_code_hash(adjustment, row.email, typed)):
            used = (EmailCode.query.filter(EmailCode.id == row.id, EmailCode.used_at.is_(None))
                    .update({EmailCode.used_at: now}, synchronize_session=False))
            db.session.commit()
            admin = db.session.get(User, row.user_id) if used else None
            if admin is not None and admin.is_active and admin.is_admin:
                return admin, None
            continue
        db.session.refresh(row)
        if row.attempts >= MAX_CODE_TRIES:
            row.used_at = now   # the 5th wrong try cancels this code
            db.session.commit()
        else:
            left = max(left, MAX_CODE_TRIES - row.attempts)
    return None, left
