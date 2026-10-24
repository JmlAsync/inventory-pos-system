"""Products and the servings / add-ons list (v0.3.0 to v0.5.0, v0.9.0, v0.14.0, v0.16.0).
Moved from app.py in v0.25.0 (DEC-027): the same rules; database changes now go through store/catalog.py."""
import math
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from models import db, Product, MenuOption, RecipeItem, to_money
from common import (MAX_PRICE, MAX_QUANTITY, LOW_STOCK_THRESHOLD, PRODUCT_IMAGE_FOLDER, find_by_id, admin_required,
                    read_uploaded_picture, save_picture, delete_picture_file)
from store.stock import Recipes, can_make
from store import catalog as catalog_store

bp = Blueprint('catalog', __name__)


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
    #    (when editing, the product being edited is allowed to keep its own SKU).
    #    v0.20.2 (DEF-52): compared without regard to capitals, so "hc-001" counts as "HC-001".
    current = db.session.get(Product, current_product_id) if current_product_id else None
    if current is None or current.sku != sku:   # an unchanged SKU is fine (old look-alike pairs stay editable)
        existing = (Product.query.filter(db.func.lower(Product.sku) == sku.lower())
                    .filter(Product.id != current_product_id).first())
        if existing:
            return None, f'SKU "{sku}" is already used by "{existing.name}" ({existing.sku}).'

    return {'name': name, 'sku': sku, 'price': to_money(price),   # exact centavos (v0.23.2)
            'quantity': quantity, 'category': category,
            'has_options': bool(form.get('has_options'))}, None   # tick box (v0.16.0)


@bp.route('/products')
@login_required
def products():
    # Product list for everyone logged in, with the low-stock warning box (v0.3.0, v0.9.0)
    all_products = Product.query.all()
    # How many of each can be sold: own quantity, or what the ingredients allow (v0.17.0)
    recipes = Recipes()
    stock = {p.id: (can_make(p, recipes) if recipes.has(p) else p.quantity) for p in all_products}
    made_to_order = {p.id for p in all_products if recipes.has(p)}
    # Products at or below the threshold, lowest stock first, for the warning box
    low_stock = sorted([p for p in all_products if stock[p.id] <= LOW_STOCK_THRESHOLD],
                       key=lambda p: stock[p.id])
    return render_template('products.html', products=all_products, stock=stock,
                           made_to_order=made_to_order,
                           low_stock=low_stock, threshold=LOW_STOCK_THRESHOLD)


@bp.route('/products/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_product():
    # Admin: show the Add Product form, and save a new product if every field passes the checks (v0.4.0)
    if request.method == 'POST':
        data, error = validate_product_form(request.form)
        picture, picture_error = read_uploaded_picture(request.files.get('picture'))
        if error or picture_error:
            # Show the form again with the error message; nothing is saved
            return render_template('add_product.html', error=error or picture_error)
        image = save_picture(picture, PRODUCT_IMAGE_FOLDER, 'product') if picture else None
        catalog_store.create_product(data, image, by=current_user.id)
        return redirect(url_for('catalog.products'))
    return render_template('add_product.html')


@bp.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(product_id):
    # Admin: show the Edit form for one product, and save the changes if they pass the checks (v0.5.0)
    product = find_by_id(Product, product_id) or abort(404)
    if request.method == 'POST':
        data, error = validate_product_form(request.form, current_product_id=product.id)
        picture, picture_error = read_uploaded_picture(request.files.get('picture'))
        if error or picture_error:
            return render_template('edit_product.html', product=product, error=error or picture_error,
                                   has_recipe=RecipeItem.query.filter_by(product_id=product.id).first() is not None)
        # Picture (v0.14.0): a new upload replaces the old one; the tick box removes it
        change_image = bool(picture or request.form.get('remove_picture'))
        image = None
        if change_image:
            delete_picture_file(PRODUCT_IMAGE_FOLDER, product.image)
            image = save_picture(picture, PRODUCT_IMAGE_FOLDER, 'product') if picture else None
        catalog_store.update_product(product, data, image, change_image, by=current_user.id)
        return redirect(url_for('catalog.products'))
    return render_template('edit_product.html', product=product,
                           has_recipe=RecipeItem.query.filter_by(product_id=product.id).first() is not None)


@bp.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
@admin_required
def delete_product(product_id):
    # Admin: delete one product, but only if it has never been sold (v0.5.0, v0.10.2)
    product = find_by_id(Product, product_id) or abort(404)
    # A product that has been sold must stay (v0.10.2): reports group sales by product,
    # and SQLite can give a deleted product's id to the next new product, which would
    # then "inherit" the old sales. Setting its quantity to 0 stops it being sold.
    if catalog_store.has_sales(product):
        flash(f'"{product.name}" has sales history, so it can\'t be deleted. '
              f'Set its quantity to 0 instead to stop selling it.', 'danger')
        return redirect(url_for('catalog.products'))
    delete_picture_file(PRODUCT_IMAGE_FOLDER, product.image)   # its picture goes too (v0.14.0)
    catalog_store.delete_product(product, by=current_user.id)   # ...and its recipe (v0.17.1)
    return redirect(url_for('catalog.products'))


# ---------------- Sizes and add-ons (v0.16.0) ----------------
OPTION_KINDS = {'size': 'serving', 'addon': 'add-on'}   # 'size' = a serving: Hot / Iced or 12oz / 16oz (v0.17.2)


@bp.route('/options', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_options():
    """Admin page to add, rename, reprice and hide sizes and add-ons.
    Options are hidden rather than deleted, because old receipts and recipes refer to them."""
    if request.method == 'POST':
        option_id = request.form.get('option_id', type=int)
        kind = request.form.get('kind', '')
        name = request.form.get('name', '').strip()
        option = None
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
            scale = None
            if kind == 'size':
                # How much of every ingredient this size uses compared with the recipe (v0.17.0)
                typed = request.form.get('scale', type=float)
                scale = round(typed, 3) if typed and math.isfinite(typed) and 0 < typed <= 10 else 1.0
            active = bool(request.form.get('active')) if option_id else True
            catalog_store.save_option(option, kind, name, price, scale, active, by=current_user.id)
            flash(f'Saved {OPTION_KINDS[kind]} "{name}".', 'success')
        return redirect(url_for('catalog.manage_options'))
    in_order = (MenuOption.sort_order, MenuOption.id)
    return render_template('options.html',
                           sizes=MenuOption.query.filter_by(kind='size').order_by(*in_order).all(),
                           addons=MenuOption.query.filter_by(kind='addon').order_by(*in_order).all())


# ---------------- Product pictures (v0.14.0) ----------------
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


@bp.app_template_global()
def product_image_url(product):
    """Web address of the product's picture, or None to show the icon tile instead."""
    if product.image and os.path.exists(os.path.join(PRODUCT_IMAGE_FOLDER, os.path.basename(product.image))):
        return url_for('static', filename='products/' + product.image)
    return None


@bp.app_template_global()
def product_icon(product):
    """(icon, colour number 0-4) for a product without a picture."""
    for text in (product.name or '', product.category or ''):
        text = text.lower()
        for words, icon, hue in PRODUCT_ICON_RULES:
            if any(word in text for word in words):
                return icon, hue
    return 'bi-box-seam', 0
