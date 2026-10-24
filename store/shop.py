"""The shop's details for receipts (v0.22.0, DEC-022). Moved from app.py in v0.25.0 (DEC-027)."""
from models import db, ShopProfile
from store.audit import note, differences


def shop_profile():
    """The shop's details: the saved row, or the defaults if nothing was saved yet (not stored)."""
    return db.session.get(ShopProfile, 1) or ShopProfile(name='Inventory & POS', address='', tin='', footer='')


def save_shop_profile(values, by=None):
    """Save the checked values (name, address, tin, footer) in the one row, creating it the first time.
    v0.27.0: the changes go in the audit log (DEC-029)."""
    shop = db.session.get(ShopProfile, 1) or ShopProfile(id=1, name='Inventory & POS', address='', tin='', footer='')
    changes = differences(shop, values)
    if changes:
        note(by, 'shop.update', 'Shop details', changes)
    for key, value in values.items():
        setattr(shop, key, value)
    db.session.add(shop)
    db.session.commit()
    return shop
