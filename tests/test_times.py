"""Times stored in UTC, shown in the shop's time (v0.23.1, DEF-67, audit R1, DEC-024), test cases TC-29.x.
A cloud server runs on UTC; before v0.23.1 "today", the report's days and receipt times would have been 8 hours off."""
import os
import re
import sqlite3
from datetime import datetime, date, timedelta, timezone
from helpers import check, finish, make_users, text

# ---- A database at migration 0001 (v0.23.0) whose times are in this computer's local time, as v0.23.0 wrote them
os.makedirs('instance', exist_ok=True)
LOCAL_SALE = datetime(2026, 10, 20, 9, 15, 0)          # what v0.23.0 stored: the wall-clock time of the sale
LOCAL_SEEN = datetime(2026, 10, 20, 9, 20, 30)

from app import app, upgrade_database, MIGRATIONS_FOLDER
app.config['TEST_PLAIN_LOGIN'] = True   # v0.28.0: password-only login; this file isn't about the login code (DEC-030)
from models import db, User, Product, Sale, SaleItem, LoginSession, IngredientMovement, Ingredient
from alembic import command

app.config['CSRF_ENABLED'] = False
with app.app_context():
    config = app.extensions['migrate'].migrate.get_config(MIGRATIONS_FOLDER)
    command.upgrade(config, '0001')                     # the database as v0.23.0 left it
    db.session.execute(db.text("INSERT INTO user (id, username, password_hash, role) VALUES (1, 'u', 'x', 'admin')"))
    db.session.execute(db.text("INSERT INTO sale (id, created_at, user_id, total, cash_received, change_due, payment_method) "
                               "VALUES (1, :t, 1, 100, 100, 0, 'cash')"), {'t': LOCAL_SALE})
    db.session.execute(db.text("INSERT INTO login_session (token, user_id, created_at, last_seen) VALUES ('t', 1, :t, :s)"),
                       {'t': LOCAL_SALE, 's': LOCAL_SEEN})
    db.session.commit()
    upgrade_database()                                  # what v0.23.1 does at start-up: migration 0002

    def as_utc(local):
        """What a local wall-clock time on this computer is in UTC (the conversion 0002 must make)."""
        return local.astimezone(timezone.utc).replace(tzinfo=None)

    stored = db.session.get(Sale, 1).created_at
    check('TC-29.1 migration 0002 turns an old sale time into UTC (this computer\'s local time -> UTC, DEF-67)',
          stored == as_utc(LOCAL_SALE))
    row = LoginSession.query.first()
    check('TC-29.1 ... and login times too', row.created_at == as_utc(LOCAL_SALE) and row.last_seen == as_utc(LOCAL_SEEN))
    command.downgrade(config, '0001')
    check('TC-29.2 undoing 0002 gives back exactly the old local times',
          db.session.execute(db.text('SELECT created_at FROM sale WHERE id = 1')).scalar().startswith('2026-10-20 09:15:00'))
    command.upgrade(config, 'head')

from app import utc_now, shop_now, to_shop_time, shop_day_start_utc, SHOP_TIMEZONE

# ---- The conversions themselves (fixed inputs, so the result is the same on every computer, T3)
check('TC-29.3 the shop is in the Philippines: UTC+8', SHOP_TIMEZONE.utcoffset(None) == timedelta(hours=8))
check('TC-29.3 16:30 UTC on Oct 24 is 00:30 on Oct 25 in the shop', to_shop_time(datetime(2026, 10, 24, 16, 30)) == datetime(2026, 10, 25, 0, 30))
check('TC-29.3 the shop\'s Oct 25 starts at 16:00 UTC on Oct 24', shop_day_start_utc(date(2026, 10, 25)) == datetime(2026, 10, 24, 16, 0))
real_utc = datetime.now(timezone.utc).replace(tzinfo=None)
check('TC-29.3 utc_now() is the real UTC time (within a minute)', abs(utc_now() - real_utc) < timedelta(minutes=1))
check('TC-29.3 shop_now() is UTC + 8 hours', abs(shop_now() - (real_utc + timedelta(hours=8))) < timedelta(minutes=1))
defaults = [t.c.created_at.default for t in (Sale.__table__, LoginSession.__table__, IngredientMovement.__table__)]
defaults.append(LoginSession.__table__.c.last_seen.default)
check('TC-29.4 new sales, logins and ingredient changes are stamped in UTC (their default gives the UTC time)',
      all(abs(d.arg(None) - real_utc) < timedelta(minutes=1) for d in defaults))

# ---- Days in the report and on Home follow the shop's clock
with app.app_context():
    db.drop_all(); upgrade_database(); make_users(db, User)
    db.session.add(Product(name='Latte', sku='L1', price=100, quantity=50)); db.session.commit()
    uid = User.query.filter_by(username='admin').first().id

    def sale(when_utc, total):
        s = Sale(user_id=uid, created_at=when_utc, total=total, cash_received=total, change_due=0)
        s.items.append(SaleItem(product_id=1, product_name='Latte', unit_price=total, quantity=1))
        db.session.add(s); db.session.commit()

    sale(datetime(2025, 3, 9, 15, 59), 111)     # 23:59 on Mar 9 in the shop
    sale(datetime(2025, 3, 9, 16, 1), 222)      # 00:01 on Mar 10 in the shop
    today_start = shop_day_start_utc(shop_now().date())
    sale(today_start + timedelta(minutes=5), 333)    # 00:05 today in the shop (still "yesterday" in UTC)
    sale(today_start - timedelta(minutes=5), 444)    # 23:55 yesterday in the shop

admin = app.test_client(); admin.post('/login', data={'username': 'admin', 'password': 'admin123'})
report = text(admin.get('/reports/sales?start=2025-03-09&end=2025-03-09'))
check('TC-29.5 the report for Mar 9 counts the 23:59 sale and not the 00:01 one', '₱111.00' in report and '₱222.00' not in report)
report = text(admin.get('/reports/sales?start=2025-03-10&end=2025-03-10'))
check('TC-29.5 the report for Mar 10 counts the 00:01 sale', '₱222.00' in report and '₱111.00' not in report)
check('TC-29.6 the report lists the sale at the shop\'s time (2025-03-10 12:01 AM)', '2025-03-10 12:01 AM' in report)
home = text(admin.get('/'))
check('TC-29.7 Home "today" counts a sale at 00:05 shop time, not one at 23:55 the day before', '₱333.00' in home and '₱777.00' not in home)
check('TC-29.7 Home shows today\'s date in the shop', shop_now().strftime('%B %d, %Y') in home)
receipt = text(admin.get('/sales/2'))
check('TC-29.8 the receipt shows the shop\'s time (2025-03-10 12:01 AM)', '2025-03-10 12:01 AM' in receipt)

# ---- No code writes the computer's local time any more (only backup file names, which people read on that computer)
for name in ('app.py', 'models.py', 'seed_demo_data.py'):
    lines = [l for l in open(name, encoding='utf-8').read().split('\n')
             if re.search(r'datetime\.now\(\)|date\.today\(\)|default=datetime\.now\b', l) and 'file name' not in l]
    check(f'TC-29.9 {name}: no local-time stamps left', not lines)
    if lines:
        print('          ', lines[:3])

finish('TIMES')
