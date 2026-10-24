"""Saving a sale: the one place where selling changes stock (v0.8.0, v0.8.2, v0.17.0, v0.20.4).
Moved from complete_sale() in app.py in v0.25.0 (DEC-027); the steps are unchanged. Rules I1 and I2:
stock and ingredients go down with conditional updates inside ONE transaction, all or nothing."""
from sqlalchemy.exc import IntegrityError
from models import db, Product, Ingredient, Sale, SaleItem, IngredientMovement


class SaleRefused(Exception):
    """The sale was not saved; the message says why, for the cashier. Nothing was changed."""


class AlreadySold(Exception):
    """This basket's ticket is already on a receipt (a second click or a retry, v0.20.4)."""
    def __init__(self, sale):
        super().__init__(f'already sold as receipt #{sale.id}')
        self.sale = sale


def already_sold(ticket):
    """The receipt that already used this basket's ticket, or None (v0.20.4)."""
    return Sale.query.filter_by(ticket=ticket).first() if ticket else None


def record_sale(user_id, lines, units, needed, total, cash, method, reference, ticket):
    """Save the sale, its lines, the stock changes and the ingredient history together.
    lines: the basket lines; units: {product: units} for products WITHOUT a recipe;
    needed: {ingredient id: amount} for products WITH one. Returns the new Sale, or raises
    SaleRefused / AlreadySold after undoing everything."""
    sale = Sale(user_id=user_id, total=total, cash_received=cash, change_due=cash - total,
                payment_method=method, payment_reference=reference, ticket=ticket)
    for product, quantity in units.items():
        name = product.name
        # Deduct stock in ONE database step that only succeeds if enough is still left
        # (an "atomic update"). This is safe even if another cashier sold some of it
        # a moment ago, after the checks before. It returns how many rows it changed.
        updated = (Product.query
                   .filter(Product.id == product.id, Product.quantity >= quantity)
                   .update({Product.quantity: Product.quantity - quantity},
                           synchronize_session=False))
        if updated == 0:
            db.session.rollback()   # cancel the whole sale: nothing is saved
            raise SaleRefused(f'{name} was just sold by another sale and there is no longer '
                              f'enough stock. Please check the basket again.')
    # The same "atomic update" for every ingredient (v0.17.0): it only succeeds if enough is
    # still on hand at that very moment, so two sales can't use the same milk twice.
    for ingredient_id, amount in needed.items():
        updated = (Ingredient.query
                   .filter(Ingredient.id == ingredient_id, Ingredient.quantity >= amount - 1e-9)
                   .update({Ingredient.quantity: Ingredient.quantity - amount},
                           synchronize_session=False))
        if updated == 0:
            db.session.rollback()   # cancel the whole sale, including stock already deducted
            ingredient = db.session.get(Ingredient, ingredient_id)
            raise SaleRefused(f'{ingredient.name} was just used up by another sale. '
                              f'Please check the basket again.')
        # Write down the change in the ingredient's history ("stock ledger", rule I7)
        sale.movements.append(IngredientMovement(ingredient_id=ingredient_id, change=-amount,
                                                 reason='sale', user_id=user_id))
    for line in lines:
        # One receipt line per basket line. The price includes the size and add-ons,
        # and the options are copied as text, so old receipts stay correct (v0.16.0, rule I3)
        sale.items.append(SaleItem(product_id=line['product'].id, product_name=line['product'].name,
                                   unit_price=line['unit_price'], quantity=line['quantity'],
                                   options=line['options'] or None))
    db.session.add(sale)
    try:
        db.session.commit()   # saves the sale, its items and the new stock levels together
    except IntegrityError:
        # Two sales with the same GCash reference at the same moment: the unique rule
        # in the database stops the second one; nothing of it is saved (v0.15.0)
        db.session.rollback()
        done = already_sold(ticket)   # v0.20.4: the same basket finished a moment ago in another request
        if done:
            raise AlreadySold(done)
        raise SaleRefused(f'GCash reference {reference} was just used by another sale. '
                          f'Check the number on the customer\'s screen.')
    return sale
