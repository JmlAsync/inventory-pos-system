"""Shop details on receipts (v0.22.0, F21, DEC-022). Moved from app.py in v0.25.0 (DEC-027); saving goes
through store/shop.py. The receipt shows the shop's name, address, TIN and a footer that the admin sets here,
and ALWAYS "This is not an official receipt." (SR6): the system is not a BIR-registered POS, so its receipts
must never look like official sales invoices. That line is in the template, not a setting."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from common import admin_required, shop_now
from store.shop import shop_profile, save_shop_profile
from mail import mail_settings, send_mail, check_email_address

bp = Blueprint('shop', __name__)

SHOP_LIMITS = {'name': 60, 'address': 120, 'footer': 120}


def validate_shop_form(form):
    """Clean values from the Shop details form, or an error message (v0.22.0)."""
    values = {key: form.get(key, '').strip() for key in ('name', 'address', 'tin', 'footer')}
    if not values['name']:
        return None, 'Shop name is required.'
    labels = {'name': 'Shop name', 'address': 'Address', 'footer': 'Footer'}
    for key, limit in SHOP_LIMITS.items():
        if len(values[key]) > limit:
            return None, f'{labels[key]} can be at most {limit} characters.'
    # A Philippine TIN is 9 digits, plus a 3- or 5-digit branch code; dashes and spaces are allowed
    digits = values['tin'].replace('-', '').replace(' ', '')
    if values['tin'] and (not digits.isdigit() or not digits.isascii() or not 9 <= len(digits) <= 14):
        return None, 'TIN must have 9 to 14 digits (dashes and spaces are fine), or be left empty.'
    return values, None


@bp.route('/settings/shop', methods=['GET', 'POST'])
@login_required
@admin_required
def shop_settings():
    # Admin page for the shop's name, address, TIN and receipt footer (v0.22.0)
    if request.method == 'POST':
        values, error = validate_shop_form(request.form)
        if error:
            return render_template('shop_settings.html', shop=request.form, error=error)
        save_shop_profile(values)
        flash('Shop details saved. They now appear on every receipt.', 'success')
        return redirect(url_for('shop.shop_settings'))
    return render_template('shop_settings.html', shop=shop_profile())


# ---------------- Email settings and a test message (v0.26.0, F23, DEC-028) ----------------
# The settings themselves are written by setup_shop.py on the shop's computer (the password never travels
# through a web page). This page shows them, without the password, and sends a test message, so the owner
# knows email works before invitations and sign-in codes rely on it.

@bp.route('/settings/email', methods=['GET', 'POST'])
@login_required
@admin_required
def email_settings():
    settings, problem = mail_settings()
    if request.method == 'POST':
        to = request.form.get('to', '')
        if check_email_address(to) is None:
            flash('Type the email address to send the test to, like name@example.com.', 'danger')
            return redirect(url_for('shop.email_settings'))
        shop = shop_profile()
        error = send_mail(to, f'Test message from {shop.name}',
                          f'This is a test message from {shop.name} (Inventory & POS).\n\n'
                          f'If you can read this, the shop\'s email sending works.\n\n'
                          f'Sent by {current_user.username} on {shop_now():%d %b %Y, %I:%M %p}.\n',
                          sender_name=shop.name)
        if error:
            flash(error, 'danger')
        else:
            flash(f'Test message sent to {to.strip()}. If it hasn\'t arrived in a few minutes, look in the spam folder.',
                  'success')
        return redirect(url_for('shop.email_settings'))
    return render_template('email_settings.html', settings=settings, problem=problem)
