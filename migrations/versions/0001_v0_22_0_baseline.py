"""v0.22.0 baseline: the whole database as it was in v0.22.0

Revision ID: 0001
Revises:
Create Date: 2026-10-24

The first migration (v0.23.0, DEC-023). It brings ANY database to the v0.22.0 shape:
- an empty database: every table is created;
- a database made before v0.23.0 (by db.create_all() and the old NEW_COLUMNS list in app.py):
  only the missing tables and columns are added, so all its data stays.
It can't be undone: undoing it would delete the shop's data.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def tables():
    """The ten tables of v0.22.0, in an order where every table comes after the ones it points to.
    Written out here (not imported from models.py) so this script never changes when the models do."""
    return [
        ('ingredient', [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=50), nullable=False),
            sa.Column('unit', sa.String(length=10), nullable=False),
            sa.Column('quantity', sa.Float(), nullable=False),
            sa.Column('low_at', sa.Float(), nullable=False),
            sa.Column('category', sa.String(length=30), nullable=False),
            sa.Column('full_at', sa.Float(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')]),
        ('menu_option', [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('kind', sa.String(length=10), nullable=False),
            sa.Column('name', sa.String(length=50), nullable=False),
            sa.Column('price', sa.Float(), nullable=False),
            sa.Column('active', sa.Boolean(), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('scale', sa.Float(), nullable=False),
            sa.PrimaryKeyConstraint('id')]),
        ('product', [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('sku', sa.String(length=50), nullable=False),
            sa.Column('price', sa.Float(), nullable=False),
            sa.Column('quantity', sa.Integer(), nullable=True),
            sa.Column('category', sa.String(length=50), nullable=True),
            sa.Column('image', sa.String(length=100), nullable=True),
            sa.Column('has_options', sa.Boolean(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('sku')]),
        ('shop_profile', [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=60), nullable=False),
            sa.Column('address', sa.String(length=120), nullable=False),
            sa.Column('tin', sa.String(length=20), nullable=False),
            sa.Column('footer', sa.String(length=120), nullable=False),
            sa.PrimaryKeyConstraint('id')]),
        ('user', [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('username', sa.String(length=50), nullable=False),
            sa.Column('password_hash', sa.String(length=200), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.Column('avatar', sa.String(length=100), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('username')]),
        ('login_session', [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('token', sa.String(length=64), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('last_seen', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('token')]),
        ('recipe_item', [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('ingredient_id', sa.Integer(), nullable=False),
            sa.Column('product_id', sa.Integer(), nullable=True),
            sa.Column('option_id', sa.Integer(), nullable=True),
            sa.Column('amount', sa.Float(), nullable=False),
            sa.ForeignKeyConstraint(['ingredient_id'], ['ingredient.id']),
            sa.ForeignKeyConstraint(['option_id'], ['menu_option.id']),
            sa.ForeignKeyConstraint(['product_id'], ['product.id']),
            sa.PrimaryKeyConstraint('id')]),
        ('sale', [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('total', sa.Float(), nullable=False),
            sa.Column('cash_received', sa.Float(), nullable=False),
            sa.Column('change_due', sa.Float(), nullable=False),
            sa.Column('payment_method', sa.String(length=10), nullable=False),
            sa.Column('payment_reference', sa.String(length=20), nullable=True),
            sa.Column('ticket', sa.String(length=32), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('payment_reference'),
            sa.UniqueConstraint('ticket')]),
        ('ingredient_movement', [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('ingredient_id', sa.Integer(), nullable=False),
            sa.Column('change', sa.Float(), nullable=False),
            sa.Column('reason', sa.String(length=10), nullable=False),
            sa.Column('sale_id', sa.Integer(), nullable=True),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['ingredient_id'], ['ingredient.id']),
            sa.ForeignKeyConstraint(['sale_id'], ['sale.id']),
            sa.ForeignKeyConstraint(['user_id'], ['user.id']),
            sa.PrimaryKeyConstraint('id')]),
        ('sale_item', [
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('sale_id', sa.Integer(), nullable=False),
            sa.Column('product_id', sa.Integer(), nullable=False),
            sa.Column('product_name', sa.String(length=100), nullable=False),
            sa.Column('unit_price', sa.Float(), nullable=False),
            sa.Column('quantity', sa.Integer(), nullable=False),
            sa.Column('options', sa.String(length=200), nullable=True),
            sa.ForeignKeyConstraint(['product_id'], ['product.id']),
            sa.ForeignKeyConstraint(['sale_id'], ['sale.id']),
            sa.PrimaryKeyConstraint('id')]),
    ]


def columns_added_after_creation():
    """Columns that versions before v0.23.0 added to existing tables (the old NEW_COLUMNS list in app.py).
    An older database may lack some of them. NOT NULL columns get a default for the rows already there."""
    return [
        ('sale', sa.Column('cash_received', sa.Float(), nullable=False, server_default='0')),          # v0.8.0
        ('sale', sa.Column('change_due', sa.Float(), nullable=False, server_default='0')),             # v0.8.0
        ('user', sa.Column('avatar', sa.String(length=100), nullable=True)),                           # v0.12.0
        ('product', sa.Column('image', sa.String(length=100), nullable=True)),                         # v0.14.0
        ('sale', sa.Column('payment_method', sa.String(length=10), nullable=False, server_default='cash')),   # v0.15.0
        ('sale', sa.Column('payment_reference', sa.String(length=20), nullable=True)),                 # v0.15.0
        ('product', sa.Column('has_options', sa.Boolean(), nullable=False, server_default='0')),       # v0.16.0
        ('sale_item', sa.Column('options', sa.String(length=200), nullable=True)),                     # v0.16.0
        ('menu_option', sa.Column('scale', sa.Float(), nullable=False, server_default='1')),           # v0.17.0
        ('ingredient', sa.Column('category', sa.String(length=30), nullable=False, server_default='Other')),  # v0.18.0
        ('ingredient', sa.Column('full_at', sa.Float(), nullable=False, server_default='0')),          # v0.18.0
        ('sale', sa.Column('ticket', sa.String(length=32), nullable=True)),                            # v0.20.4
    ]


def upgrade():
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    # 1. Create every table the database doesn't have yet (all ten in an empty database)
    created = set()
    for name, parts in tables():
        if name not in existing:
            op.create_table(name, *parts)
            created.add(name)

    # 2. An older database: add the columns its existing tables lack, as NEW_COLUMNS used to
    inspector = sa.inspect(bind)
    for table, column in columns_added_after_creation():
        if table in created:
            continue   # just created complete
        if column.name not in {c['name'] for c in inspector.get_columns(table)}:
            op.add_column(table, column)
            if (table, column.name) == ('ingredient', 'category'):
                # First time: put existing ingredients into a likely group (was v0.18.0's upgrade step)
                from app import guess_ingredient_category
                for ingredient_id, name in bind.execute(sa.text('SELECT id, name FROM ingredient')).fetchall():
                    bind.execute(sa.text('UPDATE ingredient SET category = :c WHERE id = :i'),
                                 {'c': guess_ingredient_category(name), 'i': ingredient_id})
            if (table, column.name) == ('ingredient', 'full_at'):
                # ... and treat what is on hand as "full", so the stock bars start sensible (v0.18.0)
                bind.execute(sa.text('UPDATE ingredient SET full_at = quantity WHERE quantity > low_at'))

    # 3. An older sale table: one GCash reference and one basket ticket per sale (v0.15.0, v0.20.4).
    #    A new table already has these as UNIQUE columns.
    if 'sale' not in created:
        op.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_sale_payment_reference ON sale (payment_reference)')
        op.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_sale_ticket ON sale (ticket)')
    # 4. Recipe lines left behind by products deleted in v0.17.0 (DEF-40)
    if 'recipe_item' not in created:
        op.execute('DELETE FROM recipe_item WHERE product_id IS NOT NULL AND product_id NOT IN (SELECT id FROM product)')


def downgrade():
    raise RuntimeError("Migration 0001 can't be undone: it would delete every table and the shop's data. "
                       "Restore a backup from instance/ instead.")
