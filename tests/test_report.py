"""Sales report: dates, totals and top products (feature F9, test cases TC-9.x)."""
from datetime import datetime, timedelta, date
from werkzeug.security import generate_password_hash as g
from helpers import check, finish, text
from app import app
from models import db, Product, User, Sale, SaleItem

app.config['CSRF_ENABLED'] = False
app.config['PROPAGATE_EXCEPTIONS'] = False
today = date.today(); now = datetime.now(); midnight = datetime.combine(today, datetime.min.time())
with app.app_context():
    db.drop_all(); db.create_all()
    db.session.add_all([User(username='a', password_hash=g('p'), role='admin'), User(username='c', password_hash=g('p'), role='cashier'),
                        Product(name='Coke', sku='1', price=75.5, quantity=100), Product(name='Bread', sku='2', price=10, quantity=100)])
    db.session.commit()
    def sale(when, items, user_id=2):
        s = Sale(user_id=user_id, created_at=when, total=round(sum(q * p for _, q, p in items), 2), cash_received=1000, change_due=0)
        for name, q, p in items:
            s.items.append(SaleItem(product_id={'Coke': 1, 'Bread': 2}[name], product_name=name, unit_price=p, quantity=q))
        db.session.add(s)
    sale(midnight + timedelta(minutes=1), [('Coke', 2, 75.5), ('Bread', 5, 10)])   # today 00:01
    sale(max(now, midnight + timedelta(minutes=2)), [('Bread', 3, 10)], user_id=1)  # today, later
    sale(midnight - timedelta(minutes=1), [('Coke', 10, 75.5)])                     # yesterday 23:59
    sale(now - timedelta(days=3), [('Coke', 1, 75.5)])
    db.session.commit()

c = app.test_client(); c.post('/login', data={'username': 'c', 'password': 'p'})
check('cashier gets 403 and has no menu link', c.get('/reports/sales').status_code == 403 and 'Sales Report' not in text(c.get('/')))
check('visitor is sent to log in', app.test_client().get('/reports/sales').status_code == 302)
a = app.test_client(); a.post('/login', data={'username': 'a', 'password': 'p'})
h = text(a.get('/reports/sales'))
check('admin: menu link', '<span>Sales Report</span>' in text(a.get('/')) or 'Sales Report</a>' in text(a.get('/')))
check('today: revenue ₱231.00, 2 sales, 10 items (00:01 counts as today)', '₱231.00' in h and '>2</div>' in h and '>10</div>' in h)
top = h[h.find('Top products'):h.find('All sales')]
check('top products: Bread (8) before Coke (2), grouped by product', top.find('Bread') < top.find('Coke') and '<td>8</td>' in top)
y = (today - timedelta(days=1)).isoformat()
h = text(a.get(f'/reports/sales?start={y}&end={y}'))
check('yesterday only: ₱755.00, 1 sale (23:59 counts as yesterday)', '₱755.00' in h and '>1</div>' in h)
s3 = (today - timedelta(days=3)).isoformat()
h = text(a.get(f'/reports/sales?start={s3}&end={today.isoformat()}'))
check('4-day range: ₱1,061.50, 4 sales', '₱1,061.50' in h and '>4</div>' in h)
check('From and To swapped: same result', '₱1,061.50' in text(a.get(f'/reports/sales?start={today.isoformat()}&end={s3}')))
h = text(a.get('/reports/sales?start=2026-13-45&end=x'))
check('impossible dates: message, today shown instead', 'real dates between 2000 and 2100' in h and '₱231.00' in h)
h = text(a.get('/reports/sales?start=2020-01-01&end=2020-01-02'))
check('period without sales: ₱0.00 and "No sales in this period"', '₱0.00' in h and 'No sales in this period' in h)
check('year 1 or 9999 does not crash', all(a.get(f'/reports/sales?start={d}&end={d}').status_code == 200 for d in ['0001-01-01', '9999-12-31']))
finish('REPORT')
