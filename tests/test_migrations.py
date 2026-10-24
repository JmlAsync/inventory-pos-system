"""Database migrations with Alembic (v0.23.0, DEC-023), test cases TC-28.x.
Every database change is a numbered script in migrations/; an older database is brought up to date at
start-up, after an automatic backup, without losing data (rule I5)."""
import glob
import logging
import os
import sqlite3
from werkzeug.security import generate_password_hash as g
from helpers import check, finish

# ---- An older database (made by v0.21.2: no migration record, no shop_profile, sale without ticket)
os.makedirs('instance', exist_ok=True)
con = sqlite3.connect('instance/inventory.db')
con.executescript("""
CREATE TABLE product (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, sku VARCHAR(50) NOT NULL UNIQUE, price FLOAT NOT NULL, quantity INTEGER, category VARCHAR(50));
CREATE TABLE user (id INTEGER PRIMARY KEY, username VARCHAR(50) NOT NULL UNIQUE, password_hash VARCHAR(200) NOT NULL, role VARCHAR(20) NOT NULL);
CREATE TABLE sale (id INTEGER PRIMARY KEY, created_at DATETIME NOT NULL, user_id INTEGER NOT NULL REFERENCES user(id), total FLOAT NOT NULL);
CREATE TABLE sale_item (id INTEGER PRIMARY KEY, sale_id INTEGER NOT NULL REFERENCES sale(id), product_id INTEGER NOT NULL REFERENCES product(id),
                        product_name VARCHAR(100) NOT NULL, unit_price FLOAT NOT NULL, quantity INTEGER NOT NULL);
INSERT INTO product VALUES (1,'Cafe Latte','CF-002',140,0,'Coffee');
INSERT INTO sale VALUES (1,'2026-10-20 09:15:00',1,280);
INSERT INTO sale_item VALUES (1,1,1,'Cafe Latte',140,2);
""")
con.execute("INSERT INTO user VALUES (1,'admin',?,'admin')", (g('admin123'),))
con.commit(); con.close()

from app import app, upgrade_database, MIGRATIONS_FOLDER
from models import db, Product, Sale, ShopProfile
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory

app.config['CSRF_ENABLED'] = False
app_log = app.logger   # the app's log already exists before the migrations run (needed for TC-28.7)
script = ScriptDirectory(MIGRATIONS_FOLDER)
heads = script.get_heads()


def current_revision():
    with db.engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def backups():
    return sorted(glob.glob('instance/inventory_backup_*_before_*.db'))


# ---- TC-28.1 / 28.2: the older database is upgraded, data kept, a backup taken first
with app.app_context():
    upgrade_database()
    tables = set(db.inspect(db.engine).get_table_names())
    check('TC-28.1 an older database gets every table, and the migration record (alembic_version)',
          {'shop_profile', 'login_session', 'ingredient', 'menu_option', 'recipe_item', 'ingredient_movement', 'alembic_version'} <= tables)
    sale_columns = {c['name'] for c in db.inspect(db.engine).get_columns('sale')}
    check('TC-28.1 missing columns are added (sale.ticket, payment_method, cash_received)',
          {'ticket', 'payment_method', 'cash_received'} <= sale_columns)
    sale = db.session.get(Sale, 1)
    check('TC-28.1 the old sale, its item and the product are kept unchanged',
          sale is not None and sale.total == 280 and sale.items[0].product_name == 'Cafe Latte'
          and sale.payment_method == 'cash' and db.session.get(Product, 1).sku == 'CF-002')
    check('TC-28.1 the database is now at the newest migration', len(heads) == 1 and current_revision() == heads[0])
    found = backups()
    check('TC-28.2 a backup was taken before upgrading (instance/inventory_backup_..._before_...db)', len(found) == 1)
    if found:
        old = sqlite3.connect(found[0])
        check('TC-28.2 the backup is the database as it was: old shape, same data',
              old.execute('SELECT total FROM sale WHERE id = 1').fetchone() == (280.0,)
              and 'ticket' not in [r[1] for r in old.execute('PRAGMA table_info(sale)')])
        old.close()

    # ---- TC-28.3: starting again changes nothing and takes no second backup
    upgrade_database()
    check('TC-28.3 starting again: still at the newest migration, no second backup',
          current_revision() == heads[0] and len(backups()) == 1)

    # ---- TC-28.5: an empty database is built by the migrations alone
    db.drop_all()   # tests do this; the migration record stays behind on purpose
    upgrade_database()
    tables = set(db.inspect(db.engine).get_table_names())
    check('TC-28.5 an emptied database is rebuilt from the migrations, at the newest one',
          {'product', 'sale', 'shop_profile', 'user'} <= tables and current_revision() == heads[0])
    check('TC-28.5 and the empty rebuild takes no backup (nothing to protect)', len(backups()) == 1)

    # ---- TC-28.4: a database built by the migrations is exactly what models.py describes
    # (an older database keeps a few harmless differences, such as a unique index instead of a unique column)
    with db.engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), db.metadata)
    check('TC-28.4 models.py and the migrations agree (a model change without a migration fails here)',
          differences == [])
    if differences:
        print('          differences:', differences[:5])
    db.session.add(ShopProfile(id=1, name='Cafe')); db.session.commit()
    check('TC-28.5 the rebuilt database works', db.session.get(ShopProfile, 1).name == 'Cafe')

# ---- TC-28.6: the first migration can't be undone (it would delete the shop's data)
# (Alembic is called directly: Flask-Migrate's own downgrade() turns the error into a quiet program exit)
from alembic import command
with app.app_context():
    try:
        command.downgrade(app.extensions['migrate'].migrate.get_config(MIGRATIONS_FOLDER), 'base')
        refused = False
    except RuntimeError as error:
        refused = "can't be undone" in str(error)
    db.session.rollback()
    check('TC-28.6 undoing the first migration is refused with a message, data kept',
          refused and db.session.get(ShopProfile, 1) is not None)

# ---- TC-28.7: Alembic's logging set-up doesn't silence the app's own log (the crash log of v0.21.3)
check('TC-28.7 the app log still works after the migrations ran', not app.logger.disabled and not logging.getLogger('app').disabled)

# ---- TC-28.8: one line of history, numbered, each with a description
revisions = list(script.walk_revisions())
check('TC-28.8 one line of migrations (no branches), each with a description',
      len(heads) == 1 and all(r.doc for r in revisions))

finish('MIGRATIONS')
