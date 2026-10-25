"""Voids and refunds (v0.31.0, F28, rules I1, I7, I8, S15, DEC-007, DEC-033, plan §4.1), test cases TC-41.x.
The race cases put "another admin" exactly between reading and writing, as test_race.py and test_undo.py do."""
import io
import re
import sqlite3
import sys
from datetime import timedelta
import sqlalchemy.orm
from werkzeug.security import generate_password_hash as g
from helpers import check, finish, text, make_users, FakeMailbox

from app import app, upgrade_database, MIGRATIONS_FOLDER
from blueprints.reports import money_in_period
from common import shop_day_start_utc, shop_now
app.config['TEST_PLAIN_LOGIN'] = True   # v0.28.0: password-only login; this file isn't about the login code (DEC-030)
from models import (db, User, Product, Ingredient, RecipeItem, IngredientMovement, Sale, SaleItem, SaleAdjustment,
                    AuditEntry, EmailCode, utc_now)
from alembic import command

app.config['CSRF_ENABLED'] = False
app.config['PROPAGATE_EXCEPTIONS'] = False
real_update = sqlalchemy.orm.Query.update
mailbox = FakeMailbox(app)

# ---- TC-41.1 migration 0008: older lines learn whether they used a recipe; undo removes everything again
with app.app_context():
    db.drop_all(); upgrade_database()
    config = app.extensions['migrate'].migrate.get_config(MIGRATIONS_FOLDER)
    command.downgrade(config, '0007'); db.session.remove()
    tables = set(db.inspect(db.engine).get_table_names())
    gone = not {'sale_adjustment', 'adjustment_line', 'sale_item_usage'} & tables
    con = sqlite3.connect(db.engine.url.database)
    con.executescript("""
        INSERT INTO user (id, username, password_hash, role, is_active, must_change_password, can_invite, second_step)
            VALUES (1, 'old', 'x', 'admin', 1, 0, 0, 'email');
        INSERT INTO product (id, name, sku, price, quantity, has_options) VALUES (1, 'Old Latte', 'OL', 15000, 0, 0);
        INSERT INTO product (id, name, sku, price, quantity, has_options) VALUES (2, 'Old Cookie', 'OC', 5000, 9, 0);
        INSERT INTO ingredient (id, name, unit, quantity, low_at, category, full_at) VALUES (1, 'Old Milk', 'ml', 500, 0, 'Other', 0);
        INSERT INTO recipe_item (id, ingredient_id, product_id, amount) VALUES (1, 1, 1, 100);
        INSERT INTO sale (id, created_at, user_id, total, cash_received, change_due, payment_method)
            VALUES (1, '2026-10-20 01:00:00', 1, 20000, 20000, 0, 'cash');
        INSERT INTO sale_item (id, sale_id, product_id, product_name, unit_price, quantity) VALUES (1, 1, 1, 'Old Latte', 15000, 1);
        INSERT INTO sale_item (id, sale_id, product_id, product_name, unit_price, quantity) VALUES (2, 1, 2, 'Old Cookie', 5000, 1);
        INSERT INTO ingredient_movement (ingredient_id, change, reason, sale_id, user_id, created_at)
            VALUES (1, -100, 'sale', 1, 1, '2026-10-20 01:00:00');
    """)
    con.commit(); con.close()
    command.upgrade(config, 'head'); db.session.remove()
    latte, cookie = db.session.get(SaleItem, 1), db.session.get(SaleItem, 2)
    check('TC-41.1 migration 0008 adds the void / refund tables; undoing it removes them',
          gone and {'sale_adjustment', 'adjustment_line', 'sale_item_usage'} <= set(db.inspect(db.engine).get_table_names()))
    check('TC-41.1 older lines: the latte used its recipe, the cookie its own count; nothing refunded, not voided',
          latte.used_recipe is True and cookie.used_recipe is False and latte.refunded_quantity == 0
          and db.session.get(Sale, 1).voided_at is None and db.session.get(Sale, 1).refunded_total == 0)
    db.drop_all(); upgrade_database()

# ---- The shop for the rest of the file
with app.app_context():
    make_users(db, User)
    admin_user = User.query.filter_by(username='admin').first()
    admin_user.email, admin_user.email_verified_at = 'admin@example.com', utc_now()
    db.session.add(User(username='admin2', password_hash=g('admin2-pass'), role='admin', email='admin2@example.com',
                        email_verified_at=utc_now()))
    db.session.add_all([Product(name='Cookie', sku='CK', price=50, quantity=20),
                        Product(name='Latte', sku='LT', price=150, quantity=0),
                        Ingredient(name='Milk', unit='ml', quantity=2000, low_at=100, category='Milk & cream', full_at=2000),
                        Ingredient(name='Beans', unit='g', quantity=500, low_at=50, category='Coffee', full_at=500)])
    db.session.commit()
    COOKIE = Product.query.filter_by(sku='CK').first().id
    LATTE = Product.query.filter_by(sku='LT').first().id
    MILK = Ingredient.query.filter_by(name='Milk').first().id
    BEANS = Ingredient.query.filter_by(name='Beans').first().id
    db.session.add_all([RecipeItem(product_id=LATTE, ingredient_id=MILK, amount=180),
                        RecipeItem(product_id=LATTE, ingredient_id=BEANS, amount=18)])
    db.session.commit()
    DB_PATH = db.engine.url.database
    ADMIN, CASHIER = admin_user.id, User.query.filter_by(username='cashier').first().id
    ADMIN2 = User.query.filter_by(username='admin2').first().id

admin = app.test_client(); admin.post('/login', data={'username': 'admin', 'password': 'admin123'})
cashier = app.test_client(); cashier.post('/login', data={'username': 'cashier', 'password': 'cashier123'})


def sell(lines, method='cash', reference=None, client=None):
    """Sell [(product id, quantity)] at the till; returns the new receipt's number."""
    client = client or cashier
    for product_id, quantity in lines:
        client.post('/sales/new', data={'product_id': str(product_id), 'quantity': str(quantity)})
    data = {'payment_method': method, 'cash_received': '5000'} if method == 'cash' else \
        {'payment_method': 'gcash', 'gcash_reference': reference}
    response = client.post('/sales/complete', data=data)
    return int(re.search(r'/sales/(\d+)$', response.headers['Location']).group(1))


def state(sale_id):
    """(cookies on the shelf, milk, beans, sale.voided?, refunded total) right now."""
    with app.app_context():
        sale = db.session.get(Sale, sale_id)
        return (db.session.get(Product, COOKIE).quantity, db.session.get(Ingredient, MILK).quantity,
                db.session.get(Ingredient, BEANS).quantity, sale.voided_at is not None, float(sale.refunded_total))


def adjustment_of(sale_id, kind='void'):
    with app.app_context():
        row = SaleAdjustment.query.filter_by(sale_id=sale_id, kind=kind).order_by(SaleAdjustment.id.desc()).first()
        return row.id if row else None


def history(ingredient_id):
    with app.app_context():
        return [(m.reason, m.change) for m in IngredientMovement.query.filter_by(ingredient_id=ingredient_id)
                .order_by(IngredientMovement.id)]


def another_admin_first(sql):
    """The NEXT conditional update waits until another admin has run `sql` (test_race.py's method)."""
    done = {'yes': False}

    def patched(self, *args, **kwargs):
        if not done['yes']:
            done['yes'] = True
            con = sqlite3.connect(DB_PATH); con.execute(sql); con.commit(); con.close()
        return real_update(self, *args, **kwargs)
    sqlalchemy.orm.Query.update = patched


def follow(client, path, data=None):
    return text(client.post(path, data=data or {}, follow_redirects=True))


# ---- TC-41.2 a sale keeps each line's own ingredients (so a refund can return exactly those)
s1 = sell([(COOKIE, 2), (LATTE, 2)])
with app.app_context():
    items = {i.product_id: i for i in db.session.get(Sale, s1).items}
    usage = {u.ingredient_id: u.amount for u in items[LATTE].usage}
    check('TC-41.2 the latte line keeps 360 ml milk and 36 g beans (2 lattes); the cookie line uses its own count',
          items[LATTE].used_recipe is True and usage == {MILK: 360, BEANS: 36}
          and items[COOKIE].used_recipe is False and not items[COOKIE].usage)
check('TC-41.2 after the sale: 18 cookies, 1640 ml milk, 464 g beans', state(s1) == (18, 1640, 464, False, 0))

# ---- TC-41.3 a cashier asks for a void: nothing changes until an admin approves (rule S15)
page = text(cashier.get(f'/sales/{s1}'))
check('TC-41.3 today\'s receipt offers the cashier "Ask for a void" (and no refund)',
      'Ask for a void' in page and 'Refund items' not in page)
page = follow(cashier, f'/sales/{s1}/void', {'reason': '   '})
check('TC-41.3 a reason is required', 'Please write the reason' in page and adjustment_of(s1) is None)
page = follow(cashier, f'/sales/{s1}/void', {'reason': 'x' * 201})
check('TC-41.3 a reason over 200 characters is refused', 'at most 200' in page and adjustment_of(s1) is None)
page = follow(cashier, f'/sales/{s1}/void', {'reason': 'Wrong drink rung up'})
check('TC-41.3 asked: the receipt says "Void requested", stock and money unchanged',
      'Void requested' in page and state(s1) == (18, 1640, 464, False, 0))
check('TC-41.3 the cashier may email an admin (both admins with a confirmed email are listed) or type a code',
      'admin2' in page and 'The code the admin gave you' in page)
page = follow(cashier, f'/sales/{s1}/void', {'reason': 'again'})
with app.app_context():
    waiting = SaleAdjustment.query.filter_by(sale_id=s1, status='requested').count()
check('TC-41.3 a second request for the same receipt is refused', 'already waiting' in page and waiting == 1)
check('TC-41.3 Today\'s receipts lists it as "Void requested"', 'Void requested' in text(cashier.get('/sales/today')))
check('TC-41.3 the admin menu shows 1 waiting request next to Sales Report',
      re.search(r'Sales Report</span>\s*<span class="badge[^"]*"[^>]*>1<', text(admin.get('/sales/today'))) is not None)
VOID1 = adjustment_of(s1)

# ---- TC-41.4 a cashier gets 403 on every approval and refund address (rules S2, S15)
for path in ['/reports/sales', f'/sales/{s1}/refund']:
    check(f'TC-41.4 cashier GET {path} -> 403', cashier.get(path).status_code == 403)
for path in [f'/voids/{VOID1}/approve', f'/voids/{VOID1}/reject', f'/sales/{s1}/void-now', f'/sales/{s1}/refund']:
    check(f'TC-41.4 cashier POST {path} -> 403', cashier.post(path, data={'password': 'cashier123', 'method': 'cash',
                                                                         'reason': 'x'}).status_code == 403)
check('TC-41.4 ... and the request is still waiting, nothing changed',
      state(s1) == (18, 1640, 464, False, 0) and 'Void requested' in text(cashier.get(f'/sales/{s1}')))

# ---- TC-41.5 the admin approves with their password: the whole receipt goes back on the shelf
page = text(admin.get('/reports/sales'))
check('TC-41.5 the Sales Report shows the waiting request at the top: receipt, items, who asked and why',
      f'Receipt #{s1}' in page and 'Wrong drink rung up' in page and 'cashier' in page and '2 × Latte' in page)
page = follow(admin, f'/voids/{VOID1}/approve', {'method': 'cash', 'password': 'wrong-password'})
check('TC-41.5 a wrong password: refused, nothing changed', 'Current password is wrong' in page
      and state(s1) == (18, 1640, 464, False, 0))
page = follow(admin, f'/voids/{VOID1}/approve', {'method': 'card', 'password': 'admin123'})
check('TC-41.5 an unknown way of giving money back is refused', 'Cash or GCash' in page and not state(s1)[3])
page = follow(admin, f'/voids/{VOID1}/approve', {'method': 'cash', 'password': 'admin123'})
check('TC-41.5 approved: 20 cookies, 2000 ml milk and 500 g beans again; the sale is voided',
      state(s1) == (20, 2000, 500, True, 0))
check('TC-41.5 the void slip names who asked and who approved, and the money given back',
      'VOID SLIP' in page and 'Asked by:</strong> cashier' in page and 'Approved by:</strong> admin' in page
      and '₱400.00' in page and 'This is not an official receipt.' in page)
check('TC-41.5 ingredient history: a "void" line puts back exactly what the sale took (rule I7)',
      history(MILK)[-2:] == [('sale', -360), ('void', 360)] and history(BEANS)[-1] == ('void', 36))
page = text(cashier.get(f'/sales/{s1}'))
with app.app_context():
    sale = db.session.get(Sale, s1)
    unchanged = (sale.total == 400 and [(i.product_name, i.quantity, float(i.unit_price)) for i in sale.items]
                 == [('Cookie', 2, 50.0), ('Latte', 2, 150.0)])
    audit = AuditEntry.query.filter_by(action='sale.void').first()
check('TC-41.5 the receipt itself is unchanged (rule I8) and says VOIDED, with a link to the slip',
      unchanged and 'VOIDED on' in page and f'slip #{VOID1}' in page and 'Void this receipt' not in page)
check('TC-41.5 the audit log has the void, by the admin', audit is not None and audit.user_id == ADMIN)

# ---- TC-41.6 two admins approve at the same moment: the stock goes back once
page = follow(admin, f'/voids/{VOID1}/approve', {'method': 'cash', 'password': 'admin123'})
check('TC-41.6 approving an already approved void: "already decided", stock not returned twice',
      'already decided' in page and state(s1) == (20, 2000, 500, True, 0))
s2 = sell([(COOKIE, 1)])
follow(cashier, f'/sales/{s2}/void', {'reason': 'Customer left'})
VOID2 = adjustment_of(s2)
another_admin_first(f"UPDATE sale_adjustment SET status = 'approved' WHERE id = {VOID2}")
page = follow(admin, f'/voids/{VOID2}/approve', {'method': 'cash', 'password': 'admin123'})
sqlalchemy.orm.Query.update = real_update
check('TC-41.6 another admin approves exactly between reading and writing: refused, the cookie is not returned (I1)',
      'already decided' in page and state(s2)[0] == 19 and not state(s2)[3])
with app.app_context():
    db.session.get(SaleAdjustment, VOID2).status = 'requested'; db.session.commit()   # back as it was, for TC-41.7

# ---- TC-41.7 rejecting: nothing changes; the cashier may ask again
page = follow(admin, f'/voids/{VOID2}/reject', {'note': 'Customer took it after all'})
with app.app_context():
    rejected = db.session.get(SaleAdjustment, VOID2)
check('TC-41.7 rejected with the note; the cookie stays sold', rejected.status == 'rejected'
      and rejected.note == 'Customer took it after all' and rejected.decided_by == ADMIN and state(s2)[0] == 19)
check('TC-41.7 rejecting again: "already decided"', 'already decided' in follow(admin, f'/voids/{VOID2}/reject'))
check('TC-41.7 the receipt can be asked for again after a rejection',
      'Void requested' in follow(cashier, f'/sales/{s2}/void', {'reason': 'Second try'}))

# ---- TC-41.8 only today's receipts can be voided (plan §4.1)
VOID2B = adjustment_of(s2)
with app.app_context():
    db.session.get(Sale, s2).created_at = utc_now() - timedelta(days=1); db.session.commit()
page = follow(admin, f'/voids/{VOID2B}/approve', {'method': 'cash', 'password': 'admin123'})
check('TC-41.8 a request left waiting until the next day can no longer be approved (reject + refund instead)',
      'earlier day' in page and state(s2)[0] == 19 and not state(s2)[3])
check('TC-41.8 the Sales Report says so instead of offering Approve',
      'can no longer be voided' in text(admin.get('/reports/sales')))
follow(admin, f'/voids/{VOID2B}/reject')
page = follow(cashier, f'/sales/{s2}/void', {'reason': 'late'})
check('TC-41.8 an older receipt: asking is refused with "an admin gives a refund instead"',
      'Only today' in page and adjustment_of(s2) == VOID2B)
check('TC-41.8 ... and the receipt page offers no void button', 'Void this receipt' not in text(cashier.get(f'/sales/{s2}')))

# ---- TC-41.9 GCash: the reference of the transfer back is required, and can't be used twice
s3 = sell([(COOKIE, 1)], method='gcash', reference='1234567890123')
page = follow(admin, f'/sales/{s3}/void-now', {'reason': 'Double charged', 'method': 'gcash', 'password': 'admin123'})
check('TC-41.9 GCash without the transfer\'s reference: refused', '13-digit reference' in page and not state(s3)[3])
page = follow(admin, f'/sales/{s3}/void-now', {'reason': 'Double charged', 'method': 'gcash',
                                              'reference': '9999 888 777666', 'password': 'admin123'})
with app.app_context():
    done = db.session.get(SaleAdjustment, adjustment_of(s3))
check('TC-41.9 an admin voids at once with their password: asked and approved by the same admin, reference kept',
      state(s3)[3] and done.requested_by == ADMIN and done.decided_by == ADMIN and done.reference == '9999888777666')
s4 = sell([(COOKIE, 1)], method='gcash', reference='1234567890124')
cookies = state(s4)[0]
page = follow(admin, f'/sales/{s4}/void-now', {'reason': 'Again', 'method': 'gcash', 'reference': '9999888777666',
                                              'password': 'admin123'})
check('TC-41.9 the same GCash reference on a second void: refused, and nothing of it is saved',
      'already on another void or refund' in page and not state(s4)[3] and state(s4)[0] == cookies
      and adjustment_of(s4) is None)

# ---- TC-41.10 no admin at the till: approved by a code emailed to the chosen admin (DEC-033)
follow(cashier, f'/sales/{s4}/void', {'reason': 'Wrong flavour'})
VOID4 = adjustment_of(s4)
page = follow(cashier, f'/voids/{VOID4}/ask', {'admin_id': str(CASHIER)})
check('TC-41.10 only an admin from the list can be asked', 'choose an admin' in page and len(mailbox) == 0)
page = follow(cashier, f'/voids/{VOID4}/ask', {'admin_id': str(ADMIN2)})
mail = mailbox.last_to('admin2@example.com')
body = mail.get_content() if mail else ''
check('TC-41.10 the admin gets the receipt, the items, who asks and why, and a code',
      'Code sent to admin2' in page and f'receipt #{s4}' in body and 'Wrong flavour' in body and '1 x Cookie' in body
      and re.search(r'\d{3} \d{3}', body) is not None)
code = re.search(r'(\d{3}) (\d{3})', body).group(0).replace(' ', '')
wrong = '000000' if code != '000000' else '111111'
page = follow(cashier, f'/voids/{VOID4}/code', {'code': wrong, 'method': 'gcash', 'reference': '5555555555555'})
check('TC-41.10 a wrong code: refused, "4 tries left"', '4 tries left' in page and not state(s4)[3])
page = follow(cashier, f'/voids/{VOID4}/code', {'code': code, 'method': 'gcash', 'reference': '5555555555555'})
with app.app_context():
    done = db.session.get(SaleAdjustment, VOID4)
check('TC-41.10 the right code: voided in admin2\'s name, "by emailed code", stock back',
      state(s4)[3] and state(s4)[0] == cookies + 1 and done.decided_by == ADMIN2 and done.decided_how == 'code'
      and 'by emailed code' in page)
s5 = sell([(COOKIE, 1)])
follow(cashier, f'/sales/{s5}/void', {'reason': 'Test'})
VOID5 = adjustment_of(s5)
page = follow(cashier, f'/voids/{VOID5}/code', {'code': code, 'method': 'cash'})
check('TC-41.10 a code works for its own void only', 'no usable code' in page and not state(s5)[3])
follow(cashier, f'/voids/{VOID5}/ask', {'admin_id': str(ADMIN)})
code5 = re.search(r'(\d{3}) (\d{3})', mailbox.last_to('admin@example.com').get_content()).group(0).replace(' ', '')
wrong = '000000' if code5 != '000000' else '111111'
for _ in range(5):
    page = follow(cashier, f'/voids/{VOID5}/code', {'code': wrong, 'method': 'cash'})
page = follow(cashier, f'/voids/{VOID5}/code', {'code': code5, 'method': 'cash'})
check('TC-41.10 after 5 wrong tries the code stops working, even the right one', 'no usable code' in page and not state(s5)[3])
page = follow(cashier, f'/voids/{VOID5}/ask', {'admin_id': str(ADMIN)})
check('TC-41.10 a new code can\'t be sent within a minute (the emailed-code limit)', 'Wait a minute' in page)
mailbox.down = True
with app.app_context():   # as if the minute had passed
    EmailCode.query.filter_by(adjustment_id=VOID5).update({EmailCode.created_at: utc_now() - timedelta(minutes=2)})
    db.session.commit()
page = follow(cashier, f'/voids/{VOID5}/ask', {'admin_id': str(ADMIN)})
check('TC-41.10 no internet: the screen says the email was not sent (nothing silent, rule D2)',
      'Code sent' not in page and 'alert-danger' in page)
mailbox.down = False
follow(admin, f'/voids/{VOID5}/reject')

# ---- TC-41.11 refunds: chosen items, any day, back on the shelf or waste (admins only)
s6 = sell([(COOKIE, 3), (LATTE, 2)])
before = state(s6)
with app.app_context():
    item_ids = {i.product_id: i.id for i in db.session.get(Sale, s6).items}
CK6, LT6 = item_ids[COOKIE], item_ids[LATTE]
page = text(admin.get(f'/sales/{s6}/refund'))
check('TC-41.11 the refund page lists the lines; a made drink starts as Waste, a cookie as Back on the shelf',
      f'name="qty_{CK6}"' in page and re.search(rf'id="waste-{LT6}"[^>]*checked', page) is not None
      and re.search(rf'id="restock-{CK6}"[^>]*checked', page) is not None)
form = {f'qty_{CK6}': '1', f'stock_{CK6}': 'restock', f'qty_{LT6}': '1', f'stock_{LT6}': 'waste',
        'reason': 'Customer returned them', 'method': 'cash', 'password': 'admin123'}
page = follow(admin, f'/sales/{s6}/refund', dict(form, password='nope'))
check('TC-41.11 wrong password: refused, nothing changed', 'Current password is wrong' in page and state(s6) == before)
page = follow(admin, f'/sales/{s6}/refund', dict(form, **{f'qty_{CK6}': '4'}))
check('TC-41.11 more than was sold: refused ("At most 3")', 'At most 3 of Cookie' in page and state(s6) == before)
page = follow(admin, f'/sales/{s6}/refund', dict(form, **{f'qty_{CK6}': 'two'}))
check('TC-41.11 not a whole number: refused', 'whole number' in page and state(s6) == before)
page = follow(admin, f'/sales/{s6}/refund', dict(form, **{f'qty_{CK6}': '0', f'qty_{LT6}': '0'}))
check('TC-41.11 nothing chosen: refused', 'at least one item' in page and state(s6) == before)
milk_lines = len(history(MILK))
page = follow(admin, f'/sales/{s6}/refund', form)
after = state(s6)
check('TC-41.11 refunded ₱200: one cookie back on the shelf, the latte\'s milk NOT back (waste)',
      'REFUND SLIP' in page and '₱200.00' in page and after[0] == before[0] + 1 and after[1] == before[1]
      and after[4] == 200)
check('TC-41.11 the waste shows in the history: "refund" +180 then "waste" -180 (the shelf is unchanged)',
      history(MILK)[milk_lines:] == [('refund', 180), ('waste', -180)])
page = text(admin.get(f'/sales/{s6}'))
check('TC-41.11 the receipt shows "Refunded ₱200.00 of ₱450.00" and "1 refunded" on each line',
      'Refunded ₱200.00 of ₱450.00' in page and page.count('1 refunded') == 2)
page = follow(admin, f'/sales/{s6}/refund', {f'qty_{LT6}': '1', f'stock_{LT6}': 'restock', f'qty_{CK6}': '0',
                                             'reason': 'Unopened', 'method': 'cash', 'password': 'admin123'})
check('TC-41.11 a second partial refund, back on the shelf: exactly one latte\'s milk and beans come back',
      state(s6)[1] == before[1] + 180 and state(s6)[2] == before[2] + 18 and state(s6)[4] == 350)
page = follow(admin, f'/sales/{s6}/refund', {f'qty_{LT6}': '1', 'reason': 'More', 'method': 'cash',
                                             'password': 'admin123'})
check('TC-41.11 the latte line is fully refunded now: "At most 0"', 'At most 0 of Latte' in page)
page = follow(cashier, f'/sales/{s6}/void', {'reason': 'try'})
check('TC-41.11 a partly refunded receipt can\'t be voided', 'already refunded' in page and not state(s6)[3])
follow(admin, f'/sales/{s6}/refund', {f'qty_{CK6}': '2', f'stock_{CK6}': 'restock', 'reason': 'Rest',
                                     'method': 'cash', 'password': 'admin123'})
page = follow(admin, f'/sales/{s6}/refund')
check('TC-41.11 everything refunded: the refund page is refused', 'already refunded' in page and state(s6)[4] == 450)
page = follow(admin, f'/sales/{s1}/refund')
check('TC-41.11 a voided receipt can\'t be refunded', 'is voided' in page)

# ---- TC-41.12 two refunds at the same moment can't give back more than was paid (plan §4.1)
s7 = sell([(COOKIE, 2)])
with app.app_context():
    CK7 = db.session.get(Sale, s7).items[0].id
another_admin_first(f'UPDATE sale SET refunded_total = 10000 WHERE id = {s7}')   # another admin refunded ₱100
page = follow(admin, f'/sales/{s7}/refund', {f'qty_{CK7}': '1', f'stock_{CK7}': 'restock', 'reason': 'Race',
                                             'method': 'cash', 'password': 'admin123'})
sqlalchemy.orm.Query.update = real_update
with app.app_context():
    refunds = SaleAdjustment.query.filter_by(sale_id=s7).count()
check('TC-41.12 another refund lands exactly between reading and writing: refused, nothing saved (I1)',
      'more than is left' in page and refunds == 0 and state(s7)[4] == 100)
with app.app_context():
    db.session.get(Sale, s7).refunded_total = 0; db.session.commit()
another_admin_first(f'UPDATE sale_item SET refunded_quantity = 2 WHERE id = {CK7}')
cookies = state(s7)[0]
page = follow(admin, f'/sales/{s7}/refund', {f'qty_{CK7}': '1', f'stock_{CK7}': 'restock', 'reason': 'Race',
                                             'method': 'cash', 'password': 'admin123'})
sqlalchemy.orm.Query.update = real_update
check('TC-41.12 the line was refunded in between: refused, the money step is undone too (all or nothing, I2)',
      'can still be refunded' in page and state(s7)[4] == 0 and state(s7)[0] == cookies)

# ---- TC-41.13 sales sold before v0.31.0 (no per-line ingredients)
with app.app_context():
    old = Sale(user_id=CASHIER, total=200, cash_received=200, payment_method='cash')
    old.items.extend([SaleItem(product_id=LATTE, product_name='Latte', unit_price=150, quantity=1, used_recipe=True),
                      SaleItem(product_id=COOKIE, product_name='Cookie', unit_price=50, quantity=1, used_recipe=False)])
    old.movements.append(IngredientMovement(ingredient_id=MILK, change=-180, reason='sale', user_id=CASHIER))
    db.session.add(old); db.session.commit()
    S_OLD, OLD_LATTE = old.id, old.items[0].id
page = text(admin.get(f'/sales/{S_OLD}/refund'))
check('TC-41.13 an older latte line can only be refunded as waste (its own ingredients weren\'t kept)',
      re.search(rf'id="restock-{OLD_LATTE}"[^>]*disabled', page) is not None and 'waste only' in page)
page = follow(admin, f'/sales/{S_OLD}/refund', {f'qty_{OLD_LATTE}': '1', f'stock_{OLD_LATTE}': 'restock',
                                                'reason': 'x', 'method': 'cash', 'password': 'admin123'})
check('TC-41.13 a crafted "back on the shelf" for it is refused', 'Refund it as waste' in page and state(S_OLD)[4] == 0)
milk = state(S_OLD)[1]
follow(admin, f'/sales/{S_OLD}/void-now', {'reason': 'Old void', 'method': 'cash', 'password': 'admin123'})
check('TC-41.13 voiding an older sale returns what its own history lines took (180 ml milk)',
      state(S_OLD)[3] and state(S_OLD)[1] == milk + 180)

# ---- TC-41.14 the Sales Report and Home: gross, voids, refunds, net; cash in the drawer
page = text(admin.get('/reports/sales'))
check('TC-41.14 the report shows Net sales with Gross, Voids and Refunds', 'Net sales' in page and 'Voids −' in page
      and 'Refunds −' in page)
with app.app_context():
    start = shop_day_start_utc(shop_now().date()); end = shop_day_start_utc(shop_now().date() + timedelta(days=1))
    sales = Sale.query.filter(Sale.created_at >= start, Sale.created_at < end).all()
    money = money_in_period(sales, start, end)
    voided = sum(s.total for s in sales if s.voided_at)
    refunded = sum(a.total for a in SaleAdjustment.query.filter_by(kind='refund', status='approved'))
    check('TC-41.14 net = gross − voids − refunds, each from the records',
          money['voids'] == voided and money['refunds'] == refunded
          and money['net'] == money['gross'] - voided - refunded)
    cash_in = sum(s.total for s in sales if s.payment_method == 'cash')
    cash_out = sum(a.total for a in SaleAdjustment.query.filter_by(status='approved', method='cash')
                   if a.kind == 'refund' or a.sale in sales)
    gcash_back = sum(a.total for a in SaleAdjustment.query.filter_by(status='approved', method='gcash'))
    check('TC-41.14 cash expected in the drawer subtracts the cash given back; GCash given back comes off GCash',
          money['by_method']['cash'] == cash_in - cash_out
          and money['by_method']['gcash'] == sum(s.total for s in sales if s.payment_method == 'gcash') - gcash_back)
    net_today = money['net']
check('TC-41.14 Home shows today\'s net revenue', f'₱{net_today:,.2f}' in text(admin.get('/')))
check('TC-41.14 the report\'s sales list marks voided and refunded receipts',
      'badge text-bg-danger">Voided' in page and 'Refunded ₱' in page)
with app.app_context():
    lone = Sale(user_id=CASHIER, total=100, cash_received=100, payment_method='cash',
                created_at=utc_now() - timedelta(days=3))
    lone.items.append(SaleItem(product_id=COOKIE, product_name='Cookie', unit_price=50, quantity=2, used_recipe=False))
    db.session.add(lone); db.session.commit()
    S_LONE, LONE_ITEM = lone.id, lone.items[0].id
follow(admin, f'/sales/{S_LONE}/refund', {f'qty_{LONE_ITEM}': '1', f'stock_{LONE_ITEM}': 'restock', 'reason': 'Late return',
                                          'method': 'cash', 'password': 'admin123'})
with app.app_context():
    three_days = (shop_now() - timedelta(days=3)).date().isoformat()
page = text(admin.get(f'/reports/sales?start={three_days}&end={three_days}'))
check('TC-41.14 a refund given today for an older receipt counts today, not on the receipt\'s day',
      'Net sales' in page and '₱100.00' in page and 'Refunds −' not in page)
with app.app_context():
    todays = Sale.query.filter(Sale.created_at >= start).all()
    check('TC-41.14 ... and today\'s refunds include it', money_in_period(todays, start, end)['refunds'] == money['refunds'] + 50)

from common import peso
from models import to_money
check('TC-41.14 a day with more refunds than sales shows −₱130.00 (found in the browser check: it showed ₱-130.00)',
      peso(to_money(-130)) == '−₱130.00' and peso(to_money(1234.5)) == '₱1,234.50')

# ---- TC-41.15 the slip, the history and the audit log
page = text(admin.get(f'/sales/adjustment/{VOID1}'))
check('TC-41.15 a cashier can open and print a slip', 'Print slip' in text(cashier.get(f'/sales/adjustment/{VOID1}')))
check('TC-41.15 a slip that doesn\'t exist: 404', cashier.get('/sales/adjustment/99999').status_code == 404)
page = text(admin.get(f'/ingredients/history?ingredient={MILK}'))
check('TC-41.15 ingredient history names Void, Refund and Waste with a link to the slip',
      f'Void <a href="/sales/adjustment/{VOID1}">slip #{VOID1}</a>' in page and 'Waste <a' in page)
page = text(admin.get('/admin/audit?area=sale'))
check('TC-41.15 the audit log has a "Voids & refunds" area with requests, voids, rejections and refunds',
      'void requested' in page and 'voided' in page and 'void rejected' in page and 'refunded' in page)
page = text(admin.get('/reports/sales'))
check('TC-41.15 the Sales Report lists the day\'s voids and refunds with who asked and who decided',
      'Voids &amp; refunds</h2>' in page and '(emailed code)' in page and 'Rejected: Customer took it after all' in page)
check('TC-41.15 there is no separate Voids & refunds page any more (owner\'s decision)',
      admin.get('/voids').status_code == 404 and 'Voids &amp; refunds</span>' not in page)
check('TC-41.15 a rejection from the Sales Report goes back to the Sales Report',
      follow(cashier, f'/sales/{s5}/void', {'reason': 'Back test'}) and
      admin.post(f'/voids/{adjustment_of(s5)}/reject').headers['Location'].endswith('/reports/sales'))

# ---- TC-41.16 (DEF-71) demo mode shows an email with "₱" even in a server window or log that can't show "₱"
# (found in the browser check: Windows writes a redirected window in cp1252, and the void email crashed the page)
from mail import send_mail
real_stdout, window = sys.stdout, io.TextIOWrapper(io.BytesIO(), encoding='cp1252')
sys.stdout, app.config['DEMO_MODE'] = window, True
try:
    with app.app_context():
        result = send_mail('admin@example.com', 'Void request: receipt #1 (₱110.00)', 'Total ₱110.00')
except UnicodeEncodeError:
    result = 'crashed'
finally:
    window.flush()
    sys.stdout, app.config['DEMO_MODE'] = real_stdout, False
printed = window.buffer.getvalue().decode('cp1252')
check('TC-41.16 (DEF-71) demo mode: the email is shown with "?" for "₱" instead of crashing the page',
      result is None and 'Total ?110.00' in printed)

finish('VOIDS')
