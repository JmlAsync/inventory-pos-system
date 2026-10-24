"""Voids and refunds (v0.31.0, F28, rules I8 and S15, DEC-007, DEC-033, plan §4.1): today's receipts, asking for a
void, an admin approving or rejecting it (with their password, or by a code emailed to them), refunds, and the
printable void / refund slip. The checks and the stock changes are in store/adjustments.py."""
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models import Sale, SaleAdjustment, User
from common import (PAYMENT_METHODS, GCASH_REFERENCE_LENGTH, admin_required, find_by_id, shop_now, shop_day_start_utc,
                    peso)
from mail import send_mail
from store import adjustments as adjustment_store
from store import users as user_store
from store.adjustments import AdjustmentRefused
from store.shop import shop_profile
from blueprints.accounts import current_password_ok

bp = Blueprint('adjustments', __name__)

MAX_REASON_LENGTH = 200


@bp.app_template_global()
def waiting_voids_count():
    """For the menu: how many void requests wait for an admin (v0.31.0)."""
    return adjustment_store.waiting_count()


def back_to_receipt(sale_id):
    return redirect(url_for('sales.receipt', sale_id=sale_id))


def read_reason(field='reason', required=True):
    """The typed reason, trimmed. Returns (reason, problem)."""
    reason = ' '.join(request.form.get(field, '').split())
    if required and not reason:
        return None, 'Please write the reason (for example "wrong drink rung up"). It is kept with the receipt.'
    if len(reason) > MAX_REASON_LENGTH:
        return None, f'The reason can be at most {MAX_REASON_LENGTH} characters.'
    return reason, None


def read_money_back():
    """How the money went back: cash from the drawer, or GCash with the 13-digit reference of the transfer made in
    the shop's GCash app. Returns (method, reference, problem)."""
    method = request.form.get('method', '')
    if method not in PAYMENT_METHODS:
        return None, None, 'Please choose how the money goes back: Cash or GCash.'
    if method == 'cash':
        return method, None, None
    reference = ''.join(request.form.get('reference', '').split())   # spaces allowed while typing
    if not re.fullmatch(r'[0-9]{%d}' % GCASH_REFERENCE_LENGTH, reference):
        return None, None, (f'Send the money back in the shop\'s GCash app first, then type the '
                            f'{GCASH_REFERENCE_LENGTH}-digit reference number of that transfer.')
    return method, reference, None


# ---------------- Today's receipts (everyone) ----------------
@bp.route('/sales/today')
@login_required
def todays_receipts():
    """Today's receipts, newest first, with how each one stands: where a cashier finds a receipt to void."""
    start = shop_day_start_utc(shop_now().date())
    sales = Sale.query.filter(Sale.created_at >= start).order_by(Sale.id.desc()).all()
    return render_template('todays_receipts.html', sales=sales, today=shop_now().date())


# ---------------- Asking for a void (everyone) ----------------
@bp.route('/sales/<int:sale_id>/void', methods=['POST'])
@login_required
def request_void(sale_id):
    """Ask for a void of the whole receipt. Nothing changes until an admin approves it (rule S15)."""
    sale = find_by_id(Sale, sale_id) or abort(404)
    reason, problem = read_reason()
    if problem:
        flash(problem, 'danger')
        return back_to_receipt(sale.id)
    try:
        adjustment_store.request_void(sale, reason, current_user.id)
    except AdjustmentRefused as refused:
        flash(str(refused), 'danger')
        return back_to_receipt(sale.id)
    flash('Void requested. An admin must approve it before any money is given back.'
          + (' If no admin is here, ask one for a code by email below.' if adjustment_store.admins_to_ask() else ''),
          'success')
    return back_to_receipt(sale.id)


@bp.route('/voids/<int:adjustment_id>/ask', methods=['POST'])
@login_required
def ask_by_email(adjustment_id):
    """Email the chosen admin this void's details and a code (DEC-033). They give the code to the cashier only if
    they agree."""
    adjustment = find_by_id(SaleAdjustment, adjustment_id) or abort(404)
    if adjustment.kind != 'void' or adjustment.status != 'requested':
        flash('This void was already decided.', 'info')
        return back_to_receipt(adjustment.sale_id)
    admin = find_by_id(User, request.form.get('admin_id', type=int))
    if admin is None or admin not in adjustment_store.admins_to_ask():
        flash('Please choose an admin from the list.', 'danger')
        return back_to_receipt(adjustment.sale_id)
    problem = user_store.may_send_code(adjustment_store.VOID_CODE_PURPOSE, admin.email)
    if problem is None:
        code = adjustment_store.new_void_code(adjustment, admin)
        sale, shop = adjustment.sale, shop_profile().name
        items = '\n'.join(f'  {item.quantity} x {item.product_name}{" (" + item.options + ")" if item.options else ""}'
                          f'  {peso(item.subtotal)}' for item in sale.items)
        body = (f'{adjustment.requester.username} asks to VOID receipt #{sale.id} '
                f'({peso(sale.total)}, paid by {PAYMENT_METHODS.get(sale.payment_method, sale.payment_method)}).\n\n'
                f'Reason: {adjustment.reason}\n\nItems:\n{items}\n\n'
                f'If you agree, give {adjustment.requester.username} this code: {code[:3]} {code[3:]}\n'
                f'It approves this void only, works for {user_store.CODE_MINUTES} minutes, once, and the void will '
                f'name you as the one who approved it.\n\n'
                f'If you don\'t agree, do nothing: the void stays waiting, and you can reject it on Voids & refunds.\n')
        problem = send_mail(admin.email, f'Void request: receipt #{sale.id} ({peso(sale.total)})', body,
                            sender_name=shop)
    if problem:
        flash(problem, 'danger')
    else:
        flash(f'Code sent to {admin.username}. If they agree, they will tell you the code: type it below.', 'success')
    return back_to_receipt(adjustment.sale_id)


@bp.route('/voids/<int:adjustment_id>/code', methods=['POST'])
@login_required
def approve_by_code(adjustment_id):
    """The cashier types the code the admin gave them: the void is approved in that admin's name."""
    adjustment = find_by_id(SaleAdjustment, adjustment_id) or abort(404)
    if adjustment.kind != 'void' or adjustment.status != 'requested':
        flash('This void was already decided.', 'info')
        return back_to_receipt(adjustment.sale_id)
    method, reference, problem = read_money_back()
    if problem:
        flash(problem, 'danger')
        return back_to_receipt(adjustment.sale_id)
    admin, left = adjustment_store.check_void_code(adjustment, request.form.get('code', ''))
    if admin is None:
        flash(f'That code is not right. {left} {"try" if left == 1 else "tries"} left.' if left else
              'There is no usable code for this void (it expired, was used, or had 5 wrong tries). Ask for a new one.',
              'danger')
        return back_to_receipt(adjustment.sale_id)
    try:
        adjustment_store.approve_void(adjustment, admin.id, 'code', method, reference)
    except AdjustmentRefused as refused:
        flash(str(refused), 'danger')
        return back_to_receipt(adjustment.sale_id)
    flash(f'Receipt #{adjustment.sale_id} is voided (approved by {admin.username}). Give back '
          f'{peso(adjustment.total)}{" in cash" if method == "cash" else " (GCash, done)"}; the stock is back.', 'success')
    return redirect(url_for('adjustments.slip', adjustment_id=adjustment.id))


# ---------------- Admins: the waiting voids, approving and rejecting ----------------
@bp.route('/voids')
@login_required
@admin_required
def voids():
    """Voids & refunds: requests waiting for an admin, and the latest decisions."""
    return render_template('voids.html', waiting=adjustment_store.waiting_voids(), done=adjustment_store.decided(),
                           sold_today=adjustment_store.sold_today)


def back_from_decision():
    """Back to where the admin clicked: the receipt, or the Voids & refunds page."""
    if request.form.get('back') == 'receipt':
        return None
    return redirect(url_for('adjustments.voids'))


@bp.route('/voids/<int:adjustment_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_void(adjustment_id):
    """Approve with the admin's own password (plan §4.1): someone else at an unlocked admin screen can't do it."""
    adjustment = find_by_id(SaleAdjustment, adjustment_id) or abort(404)
    if adjustment.kind != 'void':
        abort(404)
    method, reference, problem = read_money_back()
    problem = problem or current_password_ok(request.form.get('password', ''))
    if problem:
        flash(problem, 'danger')
        return back_from_decision() or back_to_receipt(adjustment.sale_id)
    try:
        adjustment_store.approve_void(adjustment, current_user.id, 'password', method, reference)
    except AdjustmentRefused as refused:
        flash(str(refused), 'danger')
        return back_from_decision() or back_to_receipt(adjustment.sale_id)
    flash(f'Receipt #{adjustment.sale_id} is voided. Give back {peso(adjustment.total)}'
          f'{" in cash" if method == "cash" else " (GCash, done)"}; the stock is back.', 'success')
    return redirect(url_for('adjustments.slip', adjustment_id=adjustment.id))


@bp.route('/voids/<int:adjustment_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_void(adjustment_id):
    """Reject a void request: the receipt and the stock stay as they are."""
    adjustment = find_by_id(SaleAdjustment, adjustment_id) or abort(404)
    if adjustment.kind != 'void':
        abort(404)
    why, problem = read_reason('note', required=False)
    if problem:
        flash(problem, 'danger')
    elif adjustment_store.reject_void(adjustment, current_user.id, why):
        flash(f'The void of receipt #{adjustment.sale_id} was rejected. Nothing changed.', 'success')
    else:
        flash('This void was already decided by someone else.', 'info')
    return back_from_decision() or back_to_receipt(adjustment.sale_id)


@bp.route('/sales/<int:sale_id>/void-now', methods=['POST'])
@login_required
@admin_required
def void_now(sale_id):
    """An admin voids a receipt themself, with their password: asked and approved in one step."""
    sale = find_by_id(Sale, sale_id) or abort(404)
    reason, problem = read_reason()
    method, reference, money_problem = read_money_back() if not problem else (None, None, None)
    problem = problem or money_problem or current_password_ok(request.form.get('password', ''))
    if problem:
        flash(problem, 'danger')
        return back_to_receipt(sale.id)
    try:
        adjustment = adjustment_store.void_now(sale, reason, current_user.id, method, reference)
    except AdjustmentRefused as refused:
        flash(str(refused), 'danger')
        return back_to_receipt(sale.id)
    flash(f'Receipt #{sale.id} is voided. Give back {peso(adjustment.total)}'
          f'{" in cash" if method == "cash" else " (GCash, done)"}; the stock is back.', 'success')
    return redirect(url_for('adjustments.slip', adjustment_id=adjustment.id))


# ---------------- Admins: refunds ----------------
def read_picks(sale):
    """Each receipt line's quantity to refund and Return to stock / Waste. Returns (picks, problem)."""
    picks = []
    for item in sale.items:
        raw = request.form.get(f'qty_{item.id}', '').strip() or '0'
        if not raw.isdigit():
            return None, f'The number to refund for {item.product_name} must be a whole number (0 for none).'
        quantity = int(raw)
        if quantity > item.refundable_quantity:
            return None, (f'At most {item.refundable_quantity} of {item.product_name} can be refunded '
                          f'({item.quantity} sold, {item.refunded_quantity} refunded before).')
        picks.append((item, quantity, request.form.get(f'stock_{item.id}') == 'restock'))
    return picks, None


@bp.route('/sales/<int:sale_id>/refund', methods=['GET', 'POST'])
@login_required
@admin_required
def refund(sale_id):
    """Refund chosen lines of a receipt, any day (plan §4.1). The admin confirms with their password."""
    sale = find_by_id(Sale, sale_id) or abort(404)
    blocked = adjustment_store.why_not_refund(sale)
    if blocked:
        flash(blocked, 'danger')
        return back_to_receipt(sale.id)
    error = None
    if request.method == 'POST':
        picks, error = read_picks(sale)
        reason, problem = read_reason()
        error = error or problem
        if not error:
            method, reference, error = read_money_back()
        error = error or current_password_ok(request.form.get('password', ''))
        if not error:
            try:
                adjustment = adjustment_store.refund(sale, picks, current_user.id, method, reference, reason)
            except AdjustmentRefused as refused:
                error = str(refused)
            else:
                flash(f'Refunded {peso(adjustment.total)} on receipt #{sale.id}'
                      f'{" in cash" if method == "cash" else " (GCash, done)"}.', 'success')
                return redirect(url_for('adjustments.slip', adjustment_id=adjustment.id))
    return render_template('refund.html', sale=sale, error=error, form=request.form,
                           usage_known=adjustment_store.line_usage_known)


# ---------------- The printable slip (everyone) ----------------
@bp.route('/sales/adjustment/<int:adjustment_id>')
@login_required
def slip(adjustment_id):
    """A void or refund slip to print and keep with the drawer's cash, or a waiting / rejected request."""
    adjustment = find_by_id(SaleAdjustment, adjustment_id) or abort(404)
    return render_template('adjustment_slip.html', adjustment=adjustment, sale=adjustment.sale, shop=shop_profile())
