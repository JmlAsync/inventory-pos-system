"""Two or more tills selling at the same moment (DEF-13 and v0.17.x).

The risk: two cashiers both pass the "enough stock?" check before either has saved, and the
shop sells more than it has. The app prevents it by subtracting stock only "WHERE quantity >= n"
and undoing (rolling back) the whole sale if any line fails. These tests force that moment."""
import sqlite3
import threading
import sqlalchemy.orm
from werkzeug.security import generate_password_hash as g
from helpers import check, finish, text, Browser, start_server
from app import app
from models import db, Product, User, Sale, SaleItem, Ingredient, RecipeItem, IngredientMovement

app.config['CSRF_ENABLED'] = False
app.config['PROPAGATE_EXCEPTIONS'] = False
real_update = sqlalchemy.orm.Query.update


def other_till_sells_first(sql, params=()):
    """Make the NEXT stock update wait until another till has run `sql` directly in the database.
    This puts the other till's sale exactly between our stock check and our stock update."""
    state = {'done': False}
    with app.app_context():
        path = db.engine.url.database
    def patched(self, *args, **kwargs):
        if not state['done']:
            state['done'] = True
            con = sqlite3.connect(path); con.execute(sql, params); con.commit(); con.close()
        return real_update(self, *args, **kwargs)
    sqlalchemy.orm.Query.update = patched


def scenario(stock, b_buys, a_sells):
    with app.app_context():
        db.drop_all(); db.create_all()
        db.session.add_all([User(username='b', password_hash=g('p'), role='cashier'),
                            Product(name='Last Item', sku='L1', price=10, quantity=stock)]); db.session.commit()
    b = app.test_client(); b.post('/login', data={'username': 'b', 'password': 'p'})
    b.post('/sales/new', data={'product_id': '1', 'quantity': str(b_buys)})
    other_till_sells_first('UPDATE product SET quantity = quantity - ? WHERE id = 1', (a_sells,))
    r = b.post('/sales/complete', data={'cash_received': '1000'})
    sqlalchemy.orm.Query.update = real_update
    with app.app_context():
        left = db.session.get(Product, 1).quantity
        sold = sum(i.quantity for i in SaleItem.query.all())
    return r, left, sold


r, left, sold = scenario(stock=1, b_buys=1, a_sells=1)
check('last item: A sells it mid-sale, B is refused with a message, stock 0', r.status_code == 200 and 'sold' in text(r) and (left, sold) == (0, 0))
r, left, sold = scenario(stock=10, b_buys=8, a_sells=3)
check('10 left, A takes 3, B wants 8: B refused, stock 7 (never negative)', r.status_code == 200 and (left, sold) == (7, 0))
r, left, sold = scenario(stock=10, b_buys=5, a_sells=3)
check('10 left, A takes 3, B wants 5: both fine, stock 2', r.status_code == 302 and (left, sold) == (2, 5))

# A sale with two products where the SECOND runs out mid-sale: nothing at all may be saved
with app.app_context():
    db.drop_all(); db.create_all()
    db.session.add_all([User(username='b', password_hash=g('p'), role='cashier'),
                        Product(name='Bread', sku='B', price=10, quantity=5), Product(name='Milk', sku='M', price=20, quantity=1)])
    db.session.commit()
b = app.test_client(); b.post('/login', data={'username': 'b', 'password': 'p'})
b.post('/sales/new', data={'product_id': '1', 'quantity': '2'}); b.post('/sales/new', data={'product_id': '2', 'quantity': '1'})
other_till_sells_first('UPDATE product SET quantity = 0 WHERE id = 2')
r = b.post('/sales/complete', data={'cash_received': '100'})
sqlalchemy.orm.Query.update = real_update
with app.app_context():
    check('two-item sale, Milk sold out mid-sale: message, Bread stock still 5, no sale saved, basket kept',
          'Milk was just sold by another sale' in text(r) and db.session.get(Product, 1).quantity == 5
          and Sale.query.count() == 0 and 'product-name">Bread</span>' in text(r))


def rush(setup, cash):
    """20 cashiers on a real server press Complete Sale at the same moment. Returns status codes."""
    with app.app_context():
        db.drop_all(); db.create_all(); setup()
        for i in range(20):
            db.session.add(User(username=f'c{i}', password_hash=g('p'), role='cashier'))
        db.session.commit()
    base, server = start_server(app)
    tills = []
    for i in range(20):
        t = Browser(base); t.post('/login', {'username': f'c{i}', 'password': 'p'})
        t.post('/sales/new', {'product_id': '1', 'quantity': '1'}); tills.append(t)
    barrier, results = threading.Barrier(20), []
    def press(t):
        barrier.wait(); results.append(t.post('/sales/complete', {'cash_received': str(cash)}))
    threads = [threading.Thread(target=press, args=(t,)) for t in tills]
    [t.start() for t in threads]; [t.join() for t in threads]
    server.shutdown()
    return results


results = rush(lambda: db.session.add(Product(name='Hot Item', sku='H', price=10, quantity=5)), 10)
with app.app_context():
    left = db.session.get(Product, 1).quantity; sold = sum(i.quantity for i in SaleItem.query.all())
check(f'20 cashiers at once, 5 in stock: exactly 5 sold, 15 refused, no errors ({results.count(302)}/{results.count(200)})',
      results.count(302) == 5 and results.count(200) == 15 and (sold, left) == (5, 0))


def latte_shop():
    db.session.add_all([Product(name='Latte', sku='L', price=150, quantity=0),
                        Ingredient(name='Milk', unit='ml', quantity=1000, low_at=0), Ingredient(name='Beans', unit='g', quantity=10000, low_at=0)])
    db.session.commit()
    db.session.add_all([RecipeItem(product_id=1, ingredient_id=1, amount=200), RecipeItem(product_id=1, ingredient_id=2, amount=18)])


results = rush(latte_shop, 200)
with app.app_context():
    milk = db.session.get(Ingredient, 1).quantity; beans = db.session.get(Ingredient, 2).quantity
    used = -sum(m.change for m in IngredientMovement.query.filter_by(ingredient_id=1))
check(f'20 lattes at once, milk for 5: exactly 5 sold, milk 0, beans 10000 - 5 × 18, history agrees ({results.count(302)} sold)',
      results.count(302) == 5 and milk == 0 and beans == 10000 - 5 * 18 and used == 1000)
finish('RACE')
