"""The data layer (v0.25.0, DEC-027): every change to the database goes through a function in this package.

    store/sales.py        saving a sale: stock and ingredients down in one all-or-nothing transaction (I1, I2)
    store/adjustments.py  voids and refunds: stock back, the sale's state changed conditionally (I1, I8; v0.31.0)
    store/ingredients.py  restock, count, ingredients and recipe lines (I1, I7)
    store/catalog.py      products and the servings / add-ons list (I4)
    store/accounts.py     logins, passwords, profile pictures
    store/users.py        the owner, invitations, emailed codes, switching accounts off (v0.27.0)
    store/audit.py        the audit log: who changed what (v0.27.0)
    store/signin.py       the login's second step: trusted devices, backup codes, the authenticator app (v0.28.0)
    store/shop.py         the shop's details for receipts
    store/stock.py        reading what can still be made and sold (recipes, levels)

The rule (AGENTS.md section 2, decided 2026-10-24): every database change goes through store/; reads move
here when a second kind of store is built (DEC-014: Firestore, only for a client already on Firebase).
The pages in blueprints/ never write; tests/check_contract.py fails if one does. Today SQLite and
PostgreSQL share this code.
"""
