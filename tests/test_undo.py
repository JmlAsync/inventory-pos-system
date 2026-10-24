"""Undo on the basket, a safe stock count, and undoing a count (v0.30.0, F27, DEC-032, plan §4.2 and §4.8),
test cases TC-40.x. The race cases put "another till" exactly between reading and writing, as test_race.py does."""
import json
import sqlite3
from datetime import timedelta
import sqlalchemy.orm
from helpers import check, finish, text, make_users

from app import app, upgrade_database
app.config['TEST_PLAIN_LOGIN'] = True   # v0.28.0: password-only login; this file isn't about the login code (DEC-030)
from models import db, User, Product, Ingredient, IngredientMovement, utc_now

app.config['CSRF_ENABLED'] = False
real_update = sqlalchemy.orm.Query.update

with app.app_context():
    db.drop_all(); upgrade_database(); make_users(db, User)
    db.session.add_all([Product(name=f'Item {n}', sku=f'I{n}', price=10, quantity=50) for n in range(1, 41)])
    db.session.add_all([Ingredient(name='Milk', unit='ml', quantity=400, low_at=50, category='Milk & cream', full_at=1000),
                        Ingredient(name='Beans', unit='g', quantity=999.6999999999, low_at=50, category='Coffee', full_at=1000)])
    db.session.commit()
    DB_PATH = db.engine.url.database
    MILK = Ingredient.query.filter_by(name='Milk').first().id
    BEANS = Ingredient.query.filter_by(name='Beans').first().id

admin = app.test_client(); admin.post('/login', data={'username': 'admin', 'password': 'admin123'})
cashier = app.test_client(); cashier.post('/login', data={'username': 'cashier', 'password': 'cashier123'})


def on_hand(ingredient_id):
    with app.app_context():
        return db.session.get(Ingredient, ingredient_id).quantity


def lines(ingredient_id):
    with app.app_context():
        return [(m.reason, m.change) for m in IngredientMovement.query.filter_by(ingredient_id=ingredient_id).order_by(IngredientMovement.id)]


def count(ingredient_id, counted, seen=None, client=None):
    data = {'action': 'count', 'ingredient_id': str(ingredient_id), 'counted': str(counted)}
    if seen is not None:
        data['seen'] = str(seen)
    return text((client or admin).post('/ingredients', data=data, follow_redirects=True))


def another_till_first(sql):
    """The NEXT conditional update waits until another till has run `sql` (test_race.py's method)."""
    state = {'done': False}

    def patched(self, *args, **kwargs):
        if not state['done']:
            state['done'] = True
            con = sqlite3.connect(DB_PATH); con.execute(sql); con.commit(); con.close()
        return real_update(self, *args, **kwargs)
    sqlalchemy.orm.Query.update = patched


# ---- TC-40.1 a safe count: saved only if the amount is still what the admin saw (plan §4.8)
page = text(admin.get(f'/ingredients/{MILK}'))
check('TC-40.1 the count form carries the amount the admin sees (seen = 400)', 'name="seen" value="400"' in page)
check('TC-40.1 the Ingredients page fills it in the Update window from the row', '.js-seen' in text(admin.get('/ingredients')))
page = count(MILK, 380, seen=400)
check('TC-40.1 the amount is still 400: saved, with -20 in the history', on_hand(MILK) == 380 and lines(MILK)[-1] == ('count', -20))
before = lines(MILK)
page = count(MILK, 300, seen=400)
check('TC-40.1 the amount changed since the page was opened (a sale): nothing saved, "count again", and the amount now',
      on_hand(MILK) == 380 and lines(MILK) == before and 'changed since you opened the page' in page and 'now says 380' in page)
page = count(MILK, 300)
check('TC-40.1 a count without the amount seen (a page from before v0.30.0) is refused the same way',
      on_hand(MILK) == 380 and 'count again' in page)
page = count(BEANS, 1000, seen='999.7')
check('TC-40.1 the page\'s 3 decimals match a stored 999.6999999999 (amounts are decimals)', on_hand(BEANS) == 1000)
another_till_first(f'UPDATE ingredient SET quantity = quantity - 30 WHERE id = {MILK}')
page = count(MILK, 500, seen=380)
sqlalchemy.orm.Query.update = real_update
check('TC-40.1 a sale exactly between reading and writing: the conditional step refuses, the sale is kept (I1)',
      on_hand(MILK) == 350 and 'count again' in page)
check('TC-40.1 the cashier still gets 403 on Ingredients', cashier.post('/ingredients', data={'action': 'count'}).status_code == 403)

# ---- TC-40.2 undo a count within 5 minutes (plan §4.2)
count(MILK, 35, seen=350)   # a typo: 35 instead of 350
page = text(admin.get('/ingredients'))
check('TC-40.2 after a count, Ingredients offers "Undo count" with the change', 'Undo count' in page and '-315 ml' in page)
check('TC-40.2 ... and so does that ingredient\'s page', 'Undo count' in text(admin.get(f'/ingredients/{MILK}')))
check('TC-40.2 ... but not another ingredient\'s page', 'Undo count' not in text(admin.get(f'/ingredients/{BEANS}')))
with app.app_context():
    typo = IngredientMovement.query.filter_by(ingredient_id=MILK, reason='count').order_by(IngredientMovement.id.desc()).first().id
check('TC-40.2 a cashier can\'t undo a count (403)', cashier.post(f'/ingredients/count/{typo}/undo').status_code == 403)
page = text(admin.post(f'/ingredients/count/{typo}/undo', follow_redirects=True))
check('TC-40.2 Undo count: back to 350, with an opposite history line (never deleting the count, I7)',
      on_hand(MILK) == 350 and lines(MILK)[-2:] == [('count', -315), ('count-undo', 315)] and 'Count undone' in page)
check('TC-40.2 the history pages call it "Count undone"', 'Count undone' in text(admin.get('/ingredients/history'))
      and 'Count undone' in text(admin.get(f'/ingredients/{MILK}')))
page = text(admin.post(f'/ingredients/count/{typo}/undo', follow_redirects=True))
check('TC-40.2 it can be undone only once', on_hand(MILK) == 350 and 'can no longer be undone' in page)
check('TC-40.2 the banner is gone', 'Undo count' not in text(admin.get('/ingredients')))

count(MILK, 340, seen=350)
with app.app_context():
    late = IngredientMovement.query.filter_by(ingredient_id=MILK).order_by(IngredientMovement.id.desc()).first()
    late.created_at -= timedelta(minutes=6); late_id = late.id; db.session.commit()
page = text(admin.post(f'/ingredients/count/{late_id}/undo', follow_redirects=True))
check('TC-40.2 after 5 minutes: refused, "count again"', on_hand(MILK) == 340 and 'can no longer be undone' in page)

count(MILK, 330, seen=340)
with app.app_context():
    counted_id = IngredientMovement.query.filter_by(ingredient_id=MILK).order_by(IngredientMovement.id.desc()).first().id
admin.post('/ingredients', data={'action': 'restock', 'ingredient_id': str(MILK), 'amount': '100'})
page = text(admin.post(f'/ingredients/count/{counted_id}/undo', follow_redirects=True))
check('TC-40.2 something happened since (a delivery): refused, the delivery kept', on_hand(MILK) == 430 and 'can no longer be undone' in page)

count(MILK, 420, seen=430)
with app.app_context():
    counted_id = IngredientMovement.query.filter_by(ingredient_id=MILK).order_by(IngredientMovement.id.desc()).first().id
another_till_first(f'UPDATE ingredient SET quantity = quantity - 20 WHERE id = {MILK}')
page = text(admin.post(f'/ingredients/count/{counted_id}/undo', follow_redirects=True))
sqlalchemy.orm.Query.update = real_update
check('TC-40.2 a sale exactly between reading and writing: the undo is refused, the sale kept',
      on_hand(MILK) == 400 and 'can no longer be undone' in page)


# ---------- The basket ----------
def basket(client):
    with client.session_transaction() as s:
        return dict(s.get('basket', {}))


def undo_steps(client):
    with client.session_transaction() as s:
        return list(s.get('basket_undo', []))


def add(client, product_id, quantity=1):
    client.post('/sales/new', data={'product_id': str(product_id), 'quantity': str(quantity)})


# ---- TC-40.3 Undo brings the order back, one change at a time
c = app.test_client(); c.post('/login', data={'username': 'cashier', 'password': 'cashier123'})
check('TC-40.3 an empty order has no Undo button', 'action="/sales/undo"' not in text(c.get('/sales/new')))
add(c, 1); add(c, 2, 2)
c.post('/sales/line-quantity', data={'line': '1', 'change': '1'})
c.post('/sales/remove-line', data={'line': '2'})
check('TC-40.3 (the order: 2 × Item 1)', basket(c) == {'1': 2})
check('TC-40.3 Undo shows once something changed', 'action="/sales/undo"' in text(c.get('/sales/new')))
history = []
for _ in range(4):
    c.post('/sales/undo'); history.append(basket(c))
check('TC-40.3 each Undo steps back: Item 2 again, Item 1 back to 1, Item 2 gone, empty',
      history == [{'1': 2, '2': 2}, {'1': 1, '2': 2}, {'1': 1}, {}])
r = c.post('/sales/undo', follow_redirects=True)
check('TC-40.3 nothing left to undo: a plain message, the order unchanged', 'nothing to undo' in text(r) and basket(c) == {})
add(c, 3); c.post('/sales/remove/3')
c.post('/sales/undo')
check('TC-40.3 "remove product" can be undone too', basket(c) == {'3': 1})
r = c.post('/sales/line-quantity', data={'line': '99', 'change': '1'})
check('TC-40.3 a tap that changes nothing adds no undo step', len(undo_steps(c)) == 1)

# ---- TC-40.4 at most 5 steps, and the session cookie stays small
c = app.test_client(); c.post('/login', data={'username': 'cashier', 'password': 'cashier123'})
for n in range(1, 8):
    add(c, n)
check('TC-40.4 7 changes keep only the last 5', len(undo_steps(c)) == 5)
for _ in range(5):
    c.post('/sales/undo')
check('TC-40.4 5 undos: back to 2 items, then nothing more to undo', basket(c) == {'1': 1, '2': 1}
      and 'nothing to undo' in text(c.post('/sales/undo', follow_redirects=True)))
big = app.test_client(); big.post('/login', data={'username': 'cashier', 'password': 'cashier123'})
for n in range(1, 41):
    add(big, n, 9)
steps = undo_steps(big)
check('TC-40.4 a 40-line order: the kept copies stay under about 1,500 characters (the cookie limit is 4 KB)',
      1 <= len(steps) <= 5 and (len(json.dumps(steps)) <= 1500 or len(steps) == 1) and len(basket(big)) == 40)
check('TC-40.4 ... and the cashier is still logged in (the cookie wasn\'t dropped)', big.get('/sales/new').status_code == 200)

# ---- TC-40.5 a sold order can never come back
c = app.test_client(); c.post('/login', data={'username': 'cashier', 'password': 'cashier123'})
add(c, 5, 2)
r = c.post('/sales/complete', data={'cash_received': '100'})
check('TC-40.5 (the sale is completed)', r.status_code == 302 and '/sales/' in r.headers['Location'])
check('TC-40.5 after the sale the undo list is empty and there is no Undo button',
      undo_steps(c) == [] and 'action="/sales/undo"' not in text(c.get('/sales/new')))
c.post('/sales/undo')
check('TC-40.5 ... and posting Undo anyway brings nothing back', basket(c) == {})

# ---- TC-40.6 an undone order is checked against the stock again
c = app.test_client(); c.post('/login', data={'username': 'cashier', 'password': 'cashier123'})
with app.app_context():
    db.session.get(Product, 10).quantity = 2; db.session.commit()
add(c, 10, 2); c.post('/sales/remove-line', data={'line': '10'})
with app.app_context():
    db.session.get(Product, 10).quantity = 1; db.session.commit()   # another till sold one meanwhile
page = text(c.post('/sales/undo'))
check('TC-40.6 Undo restores the line but says the stock changed', basket(c) == {'10': 2} and 'Undone, but' in page
      and 'Not enough stock for Item 10' in page)
check('TC-40.6 ... and the sale is still refused until fixed', 'no longer has enough stock'
      in text(c.post('/sales/complete', data={'cash_received': '100'})))

# ---- TC-40.7 a new login starts with no undo list
c = app.test_client(); c.post('/login', data={'username': 'cashier', 'password': 'cashier123'})
add(c, 11)
c.post('/logout'); c.post('/login', data={'username': 'cashier', 'password': 'cashier123'})
check('TC-40.7 after logging out and in, nothing to undo (the next person starts clean)', undo_steps(c) == [] and basket(c) == {})

finish('UNDO')
