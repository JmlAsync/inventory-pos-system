"""What can still be made and sold: recipes, ingredient levels and product stock (v0.17.0, v0.18.0, v0.20.0).
Moved unchanged from app.py in v0.25.0 (DEC-027). These only READ the database; the changes are in sales.py
and ingredients.py next to this file."""
import math
from models import db, Ingredient, MenuOption, RecipeItem

# ---------------- Ingredients and recipes (v0.17.0) ----------------
# A product WITH a recipe takes its stock from its ingredients: one Honey Latte uses 18 g of
# beans, 180 ml of milk... so "how many can we still make" is worked out from what is on
# hand. A product WITHOUT a recipe keeps its own quantity, as before.
INGREDIENT_UNITS = ['g', 'ml', 'pcs']

# Groups on the Ingredients page (v0.18.0), in the order they are shown
INGREDIENT_CATEGORIES = ['Coffee', 'Milk & cream', 'Syrups & sauces', 'Toppings', 'Bakery',
                         'Cups & packaging', 'Other']
# Words that suggest a group; the first rule that matches wins (cups before milk, etc.)
INGREDIENT_CATEGORY_RULES = [
    (('cup', 'lid', 'straw', 'sleeve', 'bag', 'napkin'), 'Cups & packaging'),
    (('espresso', 'coffee', 'bean'), 'Coffee'),
    (('dough', 'croissant', 'bread', 'broas', 'waffle'), 'Bakery'),
    (('syrup', 'sauce', 'spread', 'sweetener', 'sugar', 'paste', 'honey'), 'Syrups & sauces'),
    (('milk', 'cream', 'foam', 'butter'), 'Milk & cream'),
    (('powder', 'crumb', 'flakes', 'marshmallow', 'salt', 'biscuit', 'sesame', 'cinnamon', 'cocoa', 'sprinkle', 'nut'), 'Toppings'),
]


def guess_ingredient_category(name):
    """A likely group for an ingredient name, e.g. 'Oat milk' -> 'Milk & cream' (v0.18.0)."""
    text = (name or '').lower()
    for words, category in INGREDIENT_CATEGORY_RULES:
        if any(word in text for word in words):
            return category
    return 'Other'


def stock_percent(ingredient):
    """How full the shelf is, 0-100, or None when no full level is set (v0.18.0)."""
    if ingredient.full_at and ingredient.full_at > 0:
        return max(0, min(100, round(ingredient.quantity / ingredient.full_at * 100)))
    return None


def stock_status(ingredient):
    """'out', 'low' or 'ok' (v0.18.0)."""
    if ingredient.quantity <= 0:
        return 'out'
    if ingredient.quantity <= ingredient.low_at:
        return 'low'
    return 'ok'


class Recipes:
    """All recipe lines, read from the database once per request:
    product id -> {ingredient id: amount}, and the same for options."""
    def __init__(self):
        self.of_product, self.of_option = {}, {}
        for item in RecipeItem.query.all():
            if item.product_id:
                target = self.of_product.setdefault(item.product_id, {})
            else:
                target = self.of_option.setdefault(item.option_id, {})
            target[item.ingredient_id] = target.get(item.ingredient_id, 0) + item.amount

    def has(self, product):
        return product.id in self.of_product

    def usage(self, product, size=None, addons=(), quantity=1):
        """Ingredients used by `quantity` of a product with this size and add-ons.
        The size's scale multiplies everything (a 16oz uses 1.33 times a 12oz).
        Negative option amounts replace an ingredient; nothing goes below 0."""
        per_one = dict(self.of_product.get(product.id, {}))
        for option in ([size] if size else []) + list(addons):
            for ingredient_id, amount in self.of_option.get(option.id, {}).items():
                per_one[ingredient_id] = per_one.get(ingredient_id, 0) + amount
        scale = size.scale if size else 1
        return {ingredient_id: round(amount * scale * quantity, 3)
                for ingredient_id, amount in per_one.items() if amount > 0}


def add_usage(total, usage):
    for ingredient_id, amount in usage.items():
        total[ingredient_id] = round(total.get(ingredient_id, 0) + amount, 3)
    return total


def shortages(usage):
    """Ingredients in `usage` that there isn't enough of: [(ingredient, needed, on hand)]."""
    short = []
    for ingredient_id, needed in usage.items():
        ingredient = db.session.get(Ingredient, ingredient_id)
        if ingredient is not None and needed > ingredient.quantity + 1e-9:
            short.append((ingredient, needed, ingredient.quantity))
    return short


def default_size():
    return (MenuOption.query.filter_by(kind='size', active=True)
            .order_by(MenuOption.sort_order, MenuOption.id).first())


def can_make(product, recipes, reserved=None, size=None):
    """How many more of a recipe product (default size, no add-ons) can be made with what
    is on hand, minus what `reserved` (e.g. the basket) already needs."""
    reserved = reserved or {}
    if product.has_options and size is None:
        size = default_size()
    per_one = recipes.usage(product, size if product.has_options else None)
    if not per_one:
        return 0
    counts = []
    for ingredient_id, amount in per_one.items():
        ingredient = db.session.get(Ingredient, ingredient_id)
        left = (ingredient.quantity if ingredient else 0) - reserved.get(ingredient_id, 0)
        counts.append(max(0, math.floor((left + 1e-9) / amount)))
    return min(counts)


def stock_levels(products):
    """product id -> how many can be sold now: can_make() for recipe products, quantity otherwise.
    Used by the product list, the low-stock box and the home page."""
    recipes = Recipes()
    return {p.id: (can_make(p, recipes) if recipes.has(p) else p.quantity) for p in products}


def limiting_ingredient(product, recipes, reserved=None, size=None):
    """The ingredient that runs out first for this recipe product and serving: the reason
    can_make() is small. None for products without a recipe (v0.20.0)."""
    reserved = reserved or {}
    worst, worst_count = None, None
    for ingredient_id, amount in recipes.usage(product, size if product.has_options else None).items():
        ingredient = db.session.get(Ingredient, ingredient_id)
        left = (ingredient.quantity if ingredient else 0) - reserved.get(ingredient_id, 0)
        count = max(0, math.floor((left + 1e-9) / amount))
        if worst_count is None or count < worst_count:
            worst, worst_count = ingredient, count
    return worst


def running_low():
    """Ingredients at or below their warning level, for the banner (v0.20.0): (low, out)."""
    items = Ingredient.query.filter(Ingredient.quantity <= Ingredient.low_at).order_by(Ingredient.name).all()
    return [i for i in items if i.quantity > 0], [i for i in items if i.quantity <= 0]
