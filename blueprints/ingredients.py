"""Ingredient and recipe pages, admin only (v0.17.0, v0.18.0, v0.18.1).
Moved from app.py in v0.25.0 (DEC-027): the same rules; stock and recipe changes go through store/ingredients.py."""
import math
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from models import Product, MenuOption, Ingredient, RecipeItem, IngredientMovement
from common import MAX_QUANTITY, find_by_id, admin_required, fmt_amount
from store.stock import (INGREDIENT_UNITS, INGREDIENT_CATEGORIES, guess_ingredient_category,
                         stock_percent, stock_status)
from store import ingredients as ingredient_store

bp = Blueprint('ingredients', __name__)


def read_amount(field, allow_negative=False):
    """A number typed in a form, or None if it isn't a sensible amount."""
    try:
        value = float(request.form.get(field, ''))
    except ValueError:
        return None
    if not math.isfinite(value) or abs(value) > MAX_QUANTITY or (value < 0 and not allow_negative):
        return None
    return round(value, 3)


@bp.route('/ingredients', methods=['GET', 'POST'])
@login_required
@admin_required
def ingredients():
    # Ingredients page: stock bars, groups, restock and count forms (v0.17.0, v0.18.0)
    if request.method == 'POST':
        action = request.form.get('action')
        ingredient = find_by_id(Ingredient, request.form.get('ingredient_id', type=int))
        if action in ('restock', 'count', 'edit') and ingredient is None:
            abort(404)
        if action == 'restock':
            # A delivery: ADD to what is on hand, in one database step (never overwrites a sale)
            amount = read_amount('amount')
            if not amount:
                flash('Type how much was received (more than 0).', 'danger')
            else:
                ingredient_store.restock(ingredient, amount, current_user.id)
                flash(f'Added {fmt_amount(amount)} {ingredient.unit} of {ingredient.name}.', 'success')
        elif action == 'count':
            # A stock count: set what is really on the shelf; the difference is recorded
            counted = read_amount('counted')
            if counted is None:
                flash('Type the amount you counted (0 or more).', 'danger')
            else:
                change = ingredient_store.count(ingredient, counted, current_user.id)
                flash(f'{ingredient.name} set to {fmt_amount(counted)} {ingredient.unit} '
                      f'({"+" if change >= 0 else ""}{fmt_amount(change)}).', 'success')
        elif action in ('add', 'edit'):
            name = request.form.get('name', '').strip()
            unit = request.form.get('unit', '')
            low_at = read_amount('low_at')
            # v0.18.0: group and full level. Missing fields keep what the ingredient has
            # (or a guess / 0 for a new one), so older forms and tests still work.
            category = request.form.get('category') or (ingredient.category if ingredient else guess_ingredient_category(name))
            full_at = read_amount('full_at') if request.form.get('full_at', '') != '' else (ingredient.full_at if ingredient else 0)
            same_name = Ingredient.query.filter(func.lower(Ingredient.name) == name.lower(),
                                                Ingredient.id != (ingredient.id if ingredient else 0)).first()
            if not name or len(name) > 50:
                flash('The name must be 1 to 50 characters.', 'danger')
            elif unit not in INGREDIENT_UNITS:
                flash('Choose a unit: g, ml or pcs.', 'danger')
            elif low_at is None:
                flash('"Warn at" must be a number, 0 or more.', 'danger')
            elif category not in INGREDIENT_CATEGORIES:
                flash('Choose one of the groups in the list.', 'danger')
            elif full_at is None or (full_at and full_at <= low_at):
                flash('"Full" must be more than "Warn at" (or 0 if you don\'t want a stock bar).', 'danger')
            elif same_name:
                flash(f'There is already an ingredient called "{same_name.name}".', 'danger')
            else:
                ingredient = ingredient_store.save_ingredient(ingredient, name, unit, low_at, category, full_at,
                                                              by=current_user.id)
                flash(f'Saved {name}.' + (' Use Restock to add what you have.' if action == 'add' else ''), 'success')
        else:
            abort(400)
        # Forms on an ingredient's own page go back there; the rest go back to the list.
        # Only an id is accepted, never a web address, so nobody can be sent to another site.
        if request.form.get('return_to') == 'detail' and ingredient is not None and ingredient.id:
            return redirect(url_for('ingredients.ingredient_detail', ingredient_id=ingredient.id))
        if ingredient is not None and ingredient.id:
            # Come back to the same row (v0.18.1): "#ing-7" makes the browser scroll to it
            return redirect(url_for('ingredients.ingredients', _anchor=f'ing-{ingredient.id}'))
        return redirect(url_for('ingredients.ingredients'))

    all_ingredients = Ingredient.query.order_by(Ingredient.name).all()
    # Groups in the fixed order; unknown groups (shouldn't happen) go under "Other"
    groups = {category: [] for category in INGREDIENT_CATEGORIES}
    for ingredient in all_ingredients:
        groups.get(ingredient.category, groups['Other']).append(ingredient)
    attention = sorted((i for i in all_ingredients if stock_status(i) != 'ok'),
                       key=lambda i: (stock_status(i) != 'out', i.name))
    return render_template('ingredients.html', ingredients=all_ingredients,
                           groups=[(c, items) for c, items in groups.items() if items],
                           attention=attention, units=INGREDIENT_UNITS, categories=INGREDIENT_CATEGORIES,
                           percent=stock_percent, status=stock_status)


@bp.route('/ingredients/<int:ingredient_id>')
@login_required
@admin_required
def ingredient_detail(ingredient_id):
    """One ingredient: restock, count, edit and its own history (v0.18.0). The Update
    window on the list does the same without leaving the page; this page is the fallback."""
    ingredient = find_by_id(Ingredient, ingredient_id) or abort(404)
    history = (IngredientMovement.query.filter_by(ingredient_id=ingredient.id)
               .order_by(IngredientMovement.id.desc()).limit(20).all())
    used_in = RecipeItem.query.filter_by(ingredient_id=ingredient.id).all()
    return render_template('ingredient_detail.html', ingredient=ingredient, history=history,
                           used_in=used_in, units=INGREDIENT_UNITS, categories=INGREDIENT_CATEGORIES,
                           percent=stock_percent, status=stock_status)


HISTORY_REASONS = {'sale': 'Sale', 'restock': 'Restock', 'count': 'Stock count'}


@bp.route('/ingredients/history')
@login_required
@admin_required
def ingredients_history():
    """Every change to ingredient stock, newest first, filterable (v0.18.0)."""
    query = IngredientMovement.query
    chosen = find_by_id(Ingredient, request.args.get('ingredient', type=int))
    reason = request.args.get('reason', '')
    if chosen:
        query = query.filter_by(ingredient_id=chosen.id)
    if reason in HISTORY_REASONS:
        query = query.filter_by(reason=reason)
    else:
        reason = ''
    moves = query.order_by(IngredientMovement.id.desc()).limit(200).all()
    return render_template('ingredients_history.html', moves=moves, chosen=chosen, reason=reason,
                           reasons=HISTORY_REASONS,
                           ingredients=Ingredient.query.order_by(Ingredient.name).all())


@bp.route('/recipe/<kind>/<int:item_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_recipe(kind, item_id):
    """Recipe of one product (per 1, default size) or one size/add-on (v0.17.0)."""
    if kind == 'product':
        owner = find_by_id(Product, item_id) or abort(404)
        lines = RecipeItem.query.filter_by(product_id=owner.id)
    elif kind == 'option':
        owner = find_by_id(MenuOption, item_id) or abort(404)
        lines = RecipeItem.query.filter_by(option_id=owner.id)
    else:
        abort(404)
    if request.method == 'POST':
        line = find_by_id(RecipeItem, request.form.get('line_id', type=int))
        if line is not None and line not in lines.all():
            abort(404)   # a line of another recipe
        if request.form.get('action') == 'remove' and line is not None:
            ingredient_store.remove_recipe_line(line, by=current_user.id)
            flash('Ingredient removed from the recipe.', 'success')
        else:
            amount = read_amount('amount', allow_negative=(kind == 'option'))
            ingredient = find_by_id(Ingredient, request.form.get('ingredient_id', type=int))
            if line is None and ingredient is None:
                flash('Choose an ingredient.', 'danger')
            elif amount is None or amount == 0 or (kind == 'product' and amount < 0):
                flash('Type an amount' + (' (more than 0).' if kind == 'product'
                                          else ' (negative to replace an ingredient, e.g. -180 ml milk).'), 'danger')
            elif line is not None:
                ingredient_store.change_recipe_line(line, amount, by=current_user.id)
                flash('Recipe saved.', 'success')
            elif lines.filter_by(ingredient_id=ingredient.id).first():
                flash(f'{ingredient.name} is already in this recipe; change its amount instead.', 'danger')
            else:
                ingredient_store.add_recipe_line(ingredient.id, amount,
                                                 product_id=owner.id if kind == 'product' else None,
                                                 option_id=owner.id if kind == 'option' else None,
                                                 by=current_user.id)
                flash(f'Added {ingredient.name} to the recipe.', 'success')
        return redirect(url_for('ingredients.edit_recipe', kind=kind, item_id=item_id))
    return render_template('recipe.html', kind=kind, owner=owner,
                           lines=lines.join(Ingredient).order_by(Ingredient.name).all(),
                           ingredients=Ingredient.query.order_by(Ingredient.name).all())
