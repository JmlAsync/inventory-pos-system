"""The data layer (v0.25.0, DEC-027): every change to the database goes through a function in this package.

    store/sales.py        saving a sale: stock and ingredients down in one all-or-nothing transaction (I1, I2)
    store/ingredients.py  restock, count, ingredients and recipe lines (I1, I7)
    store/catalog.py      products and the servings / add-ons list (I4)
    store/accounts.py     logins, passwords, profile pictures
    store/shop.py         the shop's details for receipts
    store/stock.py        reading what can still be made and sold (recipes, levels)

The pages in blueprints/ never write to the database themselves; tests/check_contract.py fails if one does.
They may still read with simple queries; those move here when a second kind of database is built
(DEC-014: Firestore, only for a client already on Firebase). Today SQLite and PostgreSQL share this code.
"""
