"""Changing ingredient stock and recipes (v0.17.0, v0.18.0). Moved from the Ingredients and Recipe pages in
app.py in v0.25.0 (DEC-027); the steps are unchanged. Every stock change writes a history line (rule I7)."""
from models import db, Ingredient, IngredientMovement, RecipeItem
from store.audit import note, differences
# v0.27.0 (DEC-029): changes to ingredients and recipes write an audit line naming who did it (`by`). Restock and
# count are not repeated there: their history lines (I7) already say who, when and how much.


def restock(ingredient, amount, user_id):
    """A delivery: ADD to what is on hand, in one database step, so a sale at the same moment is never
    overwritten (rule I1)."""
    Ingredient.query.filter_by(id=ingredient.id).update(
        {Ingredient.quantity: Ingredient.quantity + amount}, synchronize_session=False)
    db.session.add(IngredientMovement(ingredient_id=ingredient.id, change=amount,
                                      reason='restock', user_id=user_id))
    db.session.commit()


def count(ingredient, counted, user_id):
    """A stock count: set what is really on the shelf; the difference is recorded. Returns the difference.
    (Known limitation, report §10.4: a sale at the very same moment would be overwritten.)"""
    db.session.refresh(ingredient)
    change = round(counted - ingredient.quantity, 3)
    ingredient.quantity = counted
    db.session.add(IngredientMovement(ingredient_id=ingredient.id, change=change,
                                      reason='count', user_id=user_id))
    db.session.commit()
    return change


def save_ingredient(ingredient, name, unit, low_at, category, full_at, by=None):
    """Add a new ingredient (ingredient=None, starting at 0 on hand) or change one. Returns it."""
    action = 'ingredient.update' if ingredient is not None else 'ingredient.add'
    if ingredient is None:
        ingredient = Ingredient(quantity=0)
        db.session.add(ingredient)
    changes = differences(ingredient, {'name': name, 'unit': unit, 'low_at': low_at, 'category': category,
                                       'full_at': full_at})
    if changes:
        note(by, action, name, changes)
    ingredient.name, ingredient.unit, ingredient.low_at = name, unit, low_at
    ingredient.category, ingredient.full_at = category, full_at
    db.session.commit()
    return ingredient


def recipe_label(line):
    """e.g. "Latte: Milk" or "Oat Milk: Milk", for the audit log."""
    owner = line.product or line.option
    return f'{owner.name if owner else "?"}: {line.ingredient.name if line.ingredient else "?"}'


def remove_recipe_line(line, by=None):
    note(by, 'recipe.remove', recipe_label(line), {'amount': [f'{line.amount:g}', '']})
    db.session.delete(line)
    db.session.commit()


def change_recipe_line(line, amount, by=None):
    note(by, 'recipe.update', recipe_label(line), {'amount': [f'{line.amount:g}', f'{amount:g}']})
    line.amount = amount
    db.session.commit()


def add_recipe_line(ingredient_id, amount, product_id=None, option_id=None, by=None):
    """Exactly one of product_id / option_id is given (see RecipeItem in models.py)."""
    line = RecipeItem(ingredient_id=ingredient_id, amount=amount, product_id=product_id, option_id=option_id)
    db.session.add(line)
    db.session.flush()   # loads the product / option and ingredient names for the log line
    note(by, 'recipe.add', recipe_label(line), {'amount': ['', f'{amount:g}']})
    db.session.commit()
