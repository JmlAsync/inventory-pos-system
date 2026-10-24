"""The pages, grouped by part of the system (v0.25.0, DEC-027), as in the report's high-level architecture:

    accounts.py     log in / out, login limit, profile picture, password
    catalog.py      products, servings and add-ons, product pictures
    ingredients.py  ingredients, history, recipes
    sales.py        New Sale, the basket, completing a sale, receipts
    reports.py      Home and the Sales Report
    shop.py         the shop's details for receipts

Each file is a Flask "blueprint": a group of pages that app.py registers. Page names in templates
start with the group, e.g. url_for('sales.new_sale'). The pages never write to the database
themselves; they call store/ (rule I1, checked by tests/check_contract.py).
"""
