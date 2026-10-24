"""The New Sale screen, the basket, completing a sale and the receipt (v0.8.0, v0.15.0, v0.16.0, v0.20.0, v0.20.4).
Moved from app.py in v0.25.0 (DEC-027): the same rules; saving the sale is store/sales.py's record_sale()."""
import math
import re
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, abort
from flask_login import login_required, current_user
from models import db, Product, MenuOption, Ingredient, Sale, to_money
from common import (MAX_QUANTITY, MAX_CASH, GCASH_REFERENCE_LENGTH, LOW_STOCK_THRESHOLD, find_by_id, fmt_amount)
from store.stock import Recipes, add_usage, shortages, can_make, limiting_ingredient, running_low
from store.sales import record_sale, already_sold, SaleRefused, AlreadySold
from store.shop import shop_profile

bp = Blueprint('sales', __name__)

# ---------------- Sale processing (v0.8.0, options since v0.16.0) ----------------
# The basket is kept in the session (a small storage area Flask keeps for each
# logged-in browser) as a dictionary: {"line key": quantity}.
# A line key is the product id, plus the chosen size and add-ons for drinks (v0.16.0):
#   "7"          -> product 7, no options
#   "7:2:1.4"    -> product 7, size option 2, add-on options 1 and 4
# So "Honey Latte 16oz + Oat" and "Honey Latte 12oz" are separate basket lines.
# Nothing is saved to the database until the sale is completed.

def get_basket():
    return session.get('basket', {})


def save_basket(basket):
    session['basket'] = basket
    # v0.20.4 (DEF-48): a basket gets a one-time "sale ticket" when its first item goes in.
    # The receipt keeps the ticket and the database allows each ticket once, so the same basket
    # sent twice (double-click on a slow network, a retry, an old copy of the cookie) is sold once.
    if basket and 'sale_ticket' not in session:
        session['sale_ticket'] = secrets.token_hex(16)


def show_existing_receipt(sale):
    """This basket was already sold: empty it and open that receipt instead of selling it again."""
    session['basket'] = {}
    session.pop('sale_ticket', None)
    flash(f'This sale was already completed (receipt #{sale.id}); it was not charged twice.', 'info')
    return redirect(url_for('sales.receipt', sale_id=sale.id))


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
        return None, (f'A serving or add-on chosen for {product.name} is no longer offered, '
                      f'so that line was taken out of the basket.')
    if (size or addons) and not product.has_options:
        # The admin unticked "sizes and add-ons" for this product after it was added (v0.16.1)
        return None, (f'{product.name} no longer has servings or add-ons, so that line was taken out '
                      f'of the basket. Please add it again.')
    unit_price = round(product.price + (size.price if size else 0) + sum(a.price for a in addons), 2)
    options_text = ', '.join(([size.name] if size else []) + [a.name for a in addons])   # e.g. "16oz, Oat Milk"
    if len(options_text) > 200:   # the receipt column holds 200 characters (v0.16.1)
        options_text = options_text[:199] + '…'
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


def basket_usage(lines, recipes):
    """All ingredients the basket lines need (recipe products only) (v0.17.0)."""
    total = {}
    for line in lines:
        if recipes.has(line['product']):
            add_usage(total, recipes.usage(line['product'], line['size'], line['addons'], line['quantity']))
    return total


def units_in_basket(basket, product_id):
    """How many of one product are in the basket, across all its sizes and add-ons."""
    return sum(q for key, q in basket.items() if key.split(':')[0] == str(product_id))


# ---------------- New Sale screen (v0.20.0): Rush Hour + Stock Aware ----------------
# The tiles show a stock bar, one button per serving (+ Hot / + Iced), and the reason a
# drink can't be made. The order shows which ingredients it will use. Add-ons are changed
# on the order line (design "6a"), so one tap is enough for most drinks.

STOCK_BAR_FULL = LOW_STOCK_THRESHOLD * 4   # this many left (20) or more = a full bar on the tile (v0.20.0)


def menu_tile(product, recipes, reserved, basket, sizes):
    """Everything one tile on New Sale needs (v0.20.0): a button per serving with how many
    can still be made, the stock bar, and the missing ingredient when it can't be made."""
    servings = sizes if (product.has_options and sizes) else [None]
    buttons = []
    for size in servings:
        if recipes.has(product):
            available = can_make(product, recipes, reserved, size)
            short = None if available else limiting_ingredient(product, recipes, reserved, size)
        else:
            # No recipe: the product's own count, minus what is already in the order
            available = max(0, product.quantity - units_in_basket(basket, product.id))
            short = None
        buttons.append({'size': size, 'available': available, 'short': short})
    available = max(b['available'] for b in buttons)
    level = 'out' if available <= 0 else 'low' if available <= LOW_STOCK_THRESHOLD else 'ok'
    return {'product': product, 'buttons': buttons, 'available': available, 'level': level,
            'percent': min(100, round(available / STOCK_BAR_FULL * 100)),
            'short': buttons[0]['short'] if available <= 0 else None}


def usage_rows(lines, recipes):
    """One row per ingredient the order will use (v0.20.0): how much, before -> after,
    which items use it, and whether it will be OK, low or used up. Worst first."""
    rows = {}
    for line in lines:
        if not recipes.has(line['product']):
            continue
        for ingredient_id, amount in recipes.usage(line['product'], line['size'], line['addons'], line['quantity']).items():
            row = rows.setdefault(ingredient_id, {'used': 0, 'by': []})
            row['used'] = round(row['used'] + amount, 3)
            if line['product'].name not in row['by']:
                row['by'].append(line['product'].name)
    result = []
    for ingredient_id, row in rows.items():
        ingredient = db.session.get(Ingredient, ingredient_id)
        if ingredient is None:
            continue
        after = round(ingredient.quantity - row['used'], 3)
        status = 'out' if after <= 0 else 'low' if after <= ingredient.low_at else 'ok'
        result.append({'ingredient': ingredient, 'used': row['used'], 'before': ingredient.quantity,
                       'after': after, 'by': ', '.join(row['by']), 'status': status})
    order = {'out': 0, 'low': 1, 'ok': 2}
    return sorted(result, key=lambda r: (order[r['status']], r['ingredient'].name.lower()))


def quick_cash(total):
    """Round amounts a customer is likely to hand over: the next ₱100, ₱500 and ₱1,000 above
    the total, e.g. 310 -> [400, 500, 1000], 600 -> [700, 1000] (v0.20.0)."""
    if total <= 0:
        return []
    amounts = {math.floor(total / step) * step + step for step in (100, 500, 1000)}
    return sorted(a for a in amounts if a <= MAX_CASH)


def show_sale_page(error=None):
    """Build the order lines, total and menu tiles, then show the New Sale page."""
    basket = get_basket()
    lines, problem = basket_lines(basket)
    error = error or problem
    save_basket(basket)
    total = round(sum(line['subtotal'] for line in lines), 2)
    # What can still be added: stock minus what is already in the order.
    # (The real stock in the database only goes down when the sale is completed.)
    # Menu order (v0.14.2): grouped by category (products without one last), then by name
    in_menu_order = (Product.category.is_(None), Product.category, Product.name)
    recipes = Recipes()
    reserved = basket_usage(lines, recipes)   # ingredients the order already needs (v0.17.0)
    sizes = MenuOption.query.filter_by(kind='size', active=True).order_by(MenuOption.sort_order, MenuOption.id).all()
    addons = MenuOption.query.filter_by(kind='addon', active=True).order_by(MenuOption.sort_order, MenuOption.id).all()
    # v0.20.0: products that can't be made are shown too (greyed, with the missing ingredient)
    tiles = [menu_tile(p, recipes, reserved, basket, sizes) for p in Product.query.order_by(*in_menu_order).all()]
    choices = [t for t in tiles if t['available'] > 0]   # for the "type a quantity" form
    low, out = running_low()
    return render_template('new_sale.html', tiles=tiles, choices=choices, lines=lines, total=total,
                           sizes=sizes, addons=addons, error=error, low=low, out=out,
                           uses=usage_rows(lines, recipes), quick_cash=quick_cash(total))


def read_chosen_options(product):
    """The serving and add-ons sent with a form, checked against what is offered now.
    Returns (size_id, addon_ids, error). Shared by "add" and "change line" (v0.20.0;
    the checks themselves are from v0.16.0)."""
    if not product.has_options:
        return None, [], None
    sizes = MenuOption.query.filter_by(kind='size', active=True).order_by(MenuOption.sort_order, MenuOption.id).all()
    size_id = request.form.get('size_id', type=int)
    if sizes:
        if size_id is None:
            size_id = sizes[0].id          # the first serving if none was chosen (e.g. the list form)
        if size_id not in [s.id for s in sizes]:
            return None, [], 'Please choose one of the servings offered (e.g. Hot or Iced).'
    else:
        size_id = None
    active_addons = {a.id for a in MenuOption.query.filter_by(kind='addon', active=True)}
    try:
        addon_ids = sorted({int(i) for i in request.form.getlist('addon_ids')})
    except ValueError:
        return None, [], 'Please choose add-ons from the list.'
    if not set(addon_ids) <= active_addons:
        return None, [], 'Please choose add-ons from the list.'
    return size_id, addon_ids, None


def basket_stock_problem(basket):
    """Why this order can't be made with what is on hand, or None (v0.20.0). Used before
    saving a + tap or a changed line: units for products without a recipe, ingredients
    for the rest (the same rules as adding a product)."""
    lines, problem = basket_lines(dict(basket))
    if problem:
        return problem
    recipes = Recipes()
    units = {}
    for line in lines:
        if not recipes.has(line['product']):
            units[line['product']] = units.get(line['product'], 0) + line['quantity']
    for product, quantity in units.items():
        if quantity > product.quantity:
            return f'Not enough stock for {product.name}: only {product.quantity} on hand.'
    short = shortages(basket_usage(lines, recipes))
    if short:
        ingredient, need, have = short[0]
        return (f'Not enough {ingredient.name}: the order would need {fmt_amount(need)} {ingredient.unit}, '
                f'only {fmt_amount(have)} {ingredient.unit} on hand.')
    return None


@bp.route('/sales/new', methods=['GET', 'POST'])
@login_required
def new_sale():
    # New Sale screen: the menu tiles and the basket held in the session (v0.8.0, v0.20.0)
    if request.method == 'POST':
        # A serving button on a tile, "+ Add", or the "type a quantity" form was submitted
        product = find_by_id(Product, request.form.get('product_id', type=int))
        quantity = request.form.get('quantity', type=int)  # None if not a whole number

        if product is None:
            return show_sale_page('Please choose a product.')
        if quantity is None or quantity < 1:
            return show_sale_page('Quantity must be a whole number of at least 1.')
        if quantity > MAX_QUANTITY:
            # v0.19.3 (DEF-47): a 309-digit quantity crashed the recipe calculation, because a
            # number that big can't be turned into a decimal. Stop it before any calculation.
            return show_sale_page(f'Quantity can be at most {MAX_QUANTITY:,}.')

        # Size and add-ons (v0.16.0), only for products that offer them
        size_id, addon_ids, problem = read_chosen_options(product)
        if problem:
            return show_sale_page(problem)

        basket = get_basket()
        recipes = Recipes()
        if recipes.has(product):
            # Recipe product (v0.17.0): enough ingredients for the basket AND this line?
            lines, _ = basket_lines(dict(basket))
            size = db.session.get(MenuOption, size_id) if size_id else None
            addons = [db.session.get(MenuOption, i) for i in addon_ids]
            needed = add_usage(basket_usage(lines, recipes), recipes.usage(product, size, addons, quantity))
            short = shortages(needed)
            if short:
                ingredient, need, have = short[0]
                return show_sale_page(f'Not enough {ingredient.name} for {quantity} × {product.name}: '
                                      f'the basket would need {fmt_amount(need)} {ingredient.unit}, '
                                      f'only {fmt_amount(have)} {ingredient.unit} on hand.')
        else:
            available = product.quantity - units_in_basket(basket, product.id)   # what can still be added
            if quantity > available:
                return show_sale_page(f'Not enough stock for {product.name}: only {available} more can be added.')

        key = make_line_key(product.id, size_id, addon_ids)
        basket[key] = basket.get(key, 0) + quantity
        save_basket(basket)
        return redirect(url_for('sales.new_sale'))

    return show_sale_page()


@bp.route('/sales/line-quantity', methods=['POST'])
@login_required
def change_line_quantity():
    """The − and + buttons on an order line (v0.20.0): one less or one more of exactly that
    line. Only -1 and +1 are accepted; at 0 the line is taken out. "+" is checked against
    the stock first, like adding a product."""
    basket = get_basket()
    key = request.form.get('line', '')
    change = request.form.get('change', type=int)
    if key not in basket or change not in (-1, 1):
        return redirect(url_for('sales.new_sale'))   # nothing to change (e.g. a tap on an old page)
    quantity = basket[key] + change
    if quantity <= 0:
        basket.pop(key)
        save_basket(basket)
        return redirect(url_for('sales.new_sale'))
    if quantity > MAX_QUANTITY:
        return show_sale_page(f'Quantity can be at most {MAX_QUANTITY:,}.')
    trial = dict(basket)
    trial[key] = quantity
    if change > 0:
        problem = basket_stock_problem(trial)
        if problem:
            return show_sale_page(problem)
    save_basket(trial)
    return redirect(url_for('sales.new_sale'))


@bp.route('/sales/line-options', methods=['POST'])
@login_required
def change_line_options():
    """Design 6a (v0.20.0): change the serving and add-ons of a drink that is already in the
    order. The line gets a new key (see make_line_key); if the same drink with the same
    choices is already there, the two lines become one. Checked like adding a product."""
    basket = get_basket()
    key = request.form.get('line', '')
    if key not in basket:
        return redirect(url_for('sales.new_sale'))
    line, problem = read_line(key, basket[key])
    if problem:
        return show_sale_page()   # shows the problem and takes the line out
    product = line['product']
    if not product.has_options:
        return show_sale_page(f'{product.name} has no servings or add-ons to change.')
    size_id, addon_ids, problem = read_chosen_options(product)
    if problem:
        return show_sale_page(problem)
    new_key = make_line_key(product.id, size_id, addon_ids)
    if new_key == key:
        return redirect(url_for('sales.new_sale'))   # nothing changed
    trial = dict(basket)
    quantity = trial.pop(key)
    trial[new_key] = trial.get(new_key, 0) + quantity
    if trial[new_key] > MAX_QUANTITY:
        return show_sale_page(f'Quantity can be at most {MAX_QUANTITY:,}.')
    problem = basket_stock_problem(trial)
    if problem:
        return show_sale_page(problem)
    save_basket(trial)
    return redirect(url_for('sales.new_sale'))


@bp.route('/sales/remove/<int:product_id>', methods=['POST'])
@login_required
def remove_from_basket(product_id):
    """Take every line of this product out of the basket."""
    basket = get_basket()
    for key in [k for k in basket if k.split(':')[0] == str(product_id)]:
        basket.pop(key)
    save_basket(basket)
    return redirect(url_for('sales.new_sale'))


@bp.route('/sales/remove-line', methods=['POST'])
@login_required
def remove_line():
    """Take one basket line (one product with its size and add-ons) out (v0.16.0)."""
    basket = get_basket()
    basket.pop(request.form.get('line', ''), None)   # harmless if it isn't there
    save_basket(basket)
    return redirect(url_for('sales.new_sale'))


@bp.route('/sales/complete', methods=['POST'])
@login_required
def complete_sale():
    # Turn the basket into a saved Sale: take stock and ingredients in one transaction, or nothing (v0.8.0, v0.8.2)
    basket = get_basket()
    if not basket:
        return show_sale_page('The basket is empty.')
    # v0.20.4 (DEF-48): was this very basket already sold (a second click, a retry, an old cookie)?
    if 'sale_ticket' not in session:
        session['sale_ticket'] = secrets.token_hex(16)   # a basket from before v0.20.4
    ticket = session['sale_ticket']
    done = already_sold(ticket)
    if done:
        return show_existing_receipt(done)

    # Step 1: check EVERY line first and work out the total. Stock may have changed
    # since it was added (for example, another cashier sold the last one).
    lines, problem = basket_lines(basket)
    if problem:
        save_basket(basket)
        return show_sale_page(problem)
    recipes = Recipes()
    units = {}   # product -> units in the whole basket (products WITHOUT a recipe)
    for line in lines:
        if not recipes.has(line['product']):
            units[line['product']] = units.get(line['product'], 0) + line['quantity']
    for product, quantity in units.items():
        if quantity > product.quantity:
            return show_sale_page(f'{product.name} no longer has enough stock. '
                                  f'Please remove it and add it again with a smaller quantity.')
    needed = basket_usage(lines, recipes)   # ingredients for products WITH a recipe (v0.17.0)
    short = shortages(needed)
    if short:
        ingredient, need, have = short[0]
        return show_sale_page(f'Not enough {ingredient.name} left for this basket: it needs '
                              f'{fmt_amount(need)} {ingredient.unit}, only {fmt_amount(have)} {ingredient.unit} on hand.')
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

    # Step 3: everything is fine, so save the sale and take the stock: all or nothing (store/sales.py)
    try:
        sale = record_sale(current_user.id, lines, units, needed, total,
                           to_money(cash),   # exact pesos, so the change is exact too (v0.23.2, DEF-68)
                           method, reference, ticket)
    except AlreadySold as done:
        return show_existing_receipt(done.sale)
    except SaleRefused as reason:
        return show_sale_page(str(reason))
    save_basket({})       # empty the basket for the next customer
    session.pop('sale_ticket', None)   # the next basket gets a new ticket (v0.20.4)
    return redirect(url_for('sales.receipt', sale_id=sale.id))


@bp.route('/sales/<int:sale_id>')
@login_required
def receipt(sale_id):
    # Show a saved sale as a printable receipt, built from the copies kept in SaleItem (v0.8.0)
    sale = find_by_id(Sale, sale_id) or abort(404)
    return render_template('receipt.html', sale=sale, shop=shop_profile())   # v0.22.0: the shop's own details
