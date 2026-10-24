"""Changing products and the servings / add-ons list (v0.4.0, v0.5.0, v0.10.2, v0.16.0, v0.17.1).
Moved from the product and option pages in app.py in v0.25.0 (DEC-027); the steps are unchanged."""
from sqlalchemy import func
from models import db, Product, MenuOption, RecipeItem, SaleItem, to_money


def create_product(data, image=None):
    """data: the checked values from validate_product_form(); image: a saved picture's file name."""
    product = Product(**data)
    product.image = image
    db.session.add(product)
    db.session.commit()
    return product


def update_product(product, data, image=None, change_image=False):
    """Save the checked form values; with change_image, the picture becomes `image` (None removes it)."""
    product.name = data['name']
    product.sku = data['sku']
    product.price = data['price']
    product.quantity = data['quantity']
    product.category = data['category']
    product.has_options = data['has_options']
    if change_image:
        product.image = image
    db.session.commit()


def has_sales(product):
    """A product that has been sold must stay (v0.10.2, rule I4)."""
    return SaleItem.query.filter_by(product_id=product.id).first() is not None


def delete_product(product):
    """Delete a never-sold product AND its recipe (v0.17.1): SQLite may give this id to the next new
    product, which would otherwise "inherit" the recipe. The caller checks has_sales() first."""
    RecipeItem.query.filter_by(product_id=product.id).delete()
    db.session.delete(product)
    db.session.commit()


def save_option(option, kind, name, price, scale=None, active=True):
    """Add (option=None) or change a serving / add-on. Options are hidden, never deleted (v0.16.0)."""
    if option is None:
        last = db.session.query(func.max(MenuOption.sort_order)).filter_by(kind=kind).scalar() or 0
        option = MenuOption(kind=kind, sort_order=last + 1)
        db.session.add(option)
    option.name = name
    option.price = to_money(price)   # exact centavos, rounded half up (v0.23.2)
    if scale is not None:
        option.scale = scale
    option.active = active
    db.session.commit()
    return option
