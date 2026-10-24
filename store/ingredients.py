"""Changing ingredient stock and recipes (v0.17.0, v0.18.0). Moved from the Ingredients and Recipe pages in
app.py in v0.25.0 (DEC-027); the steps are unchanged. Every stock change writes a history line (rule I7)."""
from datetime import timedelta
from models import db, Ingredient, IngredientMovement, RecipeItem, utc_now
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


SAME_AMOUNT = 0.0005        # the pages show 3 decimals, so "the amount seen" matches within half a thousandth
COUNT_UNDO_MINUTES = 5


def count(ingredient, counted, seen, user_id):
    """A stock count: set what is really on the shelf; the difference is recorded (I7).
    v0.30.0 (DEC-032, plan §4.8): saved only if the amount on hand is still the amount the admin SAW on the page,
    checked and changed in one conditional step (I1). Returns the history line, or None if a sale or a delivery
    changed it in between (nothing is saved; the admin counts again)."""
    on_hand = db.session.query(Ingredient.quantity).filter(Ingredient.id == ingredient.id).scalar()
    if on_hand is None or seen is None or abs(on_hand - seen) > SAME_AMOUNT:
        return None
    updated = (Ingredient.query.filter(Ingredient.id == ingredient.id, Ingredient.quantity == on_hand)
               .update({Ingredient.quantity: counted}, synchronize_session=False))
    if updated == 0:
        db.session.rollback()   # a sale got in between our reading and our writing: nothing is saved
        return None
    line = IngredientMovement(ingredient_id=ingredient.id, change=round(counted - on_hand, 3),
                              reason='count', user_id=user_id)
    db.session.add(line)
    db.session.commit()
    return line


def on_hand(ingredient):
    """The amount on hand now, read fresh from the database (for messages after a refused count)."""
    return db.session.query(Ingredient.quantity).filter(Ingredient.id == ingredient.id).scalar()


def undoable_count(movement_id):
    """The count line with this id if it can still be undone (DEC-032): a count, less than 5 minutes old, and
    nothing else happened to that ingredient since. Otherwise None."""
    line = db.session.get(IngredientMovement, movement_id) if movement_id else None
    if line is None or line.reason != 'count' or utc_now() - line.created_at > timedelta(minutes=COUNT_UNDO_MINUTES):
        return None
    later = IngredientMovement.query.filter(IngredientMovement.ingredient_id == line.ingredient_id,
                                            IngredientMovement.id > line.id).first()
    return None if later else line


def undo_count(line, user_id):
    """Put the amount back as it was before the count, with an opposite history line (reason 'count-undo'), in one
    conditional step: refused (False) if the amount changed in the meantime."""
    on_hand = db.session.query(Ingredient.quantity).filter(Ingredient.id == line.ingredient_id).scalar()
    updated = (Ingredient.query.filter(Ingredient.id == line.ingredient_id, Ingredient.quantity == on_hand)
               .update({Ingredient.quantity: round(on_hand - line.change, 3)}, synchronize_session=False))
    if updated == 0 or undoable_count(line.id) is None:
        db.session.rollback()
        return False
    db.session.add(IngredientMovement(ingredient_id=line.ingredient_id, change=-line.change,
                                      reason='count-undo', user_id=user_id))
    db.session.commit()
    return True


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
