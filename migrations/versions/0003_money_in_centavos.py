"""Money in centavos (v0.23.2): prices and totals become whole centavos (INTEGER), e.g. 75.50 -> 7550

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-24

Until v0.23.1 money was stored as decimal numbers (REAL), which can drift by a centavo when many are added up
(audit R5). The models now use the Money type (models.py): whole centavos in the database, exact Decimal pesos
in Python (DEC-025). Each amount is multiplied by 100 and rounded FIRST, then the column becomes INTEGER: changing
the type alone would cut 75.50 to 75. Undoing divides by 100 again.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

# (table, column, to centavos, back to pesos) for every money column; each statement is fixed text (rule S5)
MONEY = [
    ('product', 'price', 'UPDATE product SET price = ROUND(price * 100)', 'UPDATE product SET price = price / 100.0'),
    ('sale', 'total', 'UPDATE sale SET total = ROUND(total * 100)', 'UPDATE sale SET total = total / 100.0'),
    ('sale', 'cash_received', 'UPDATE sale SET cash_received = ROUND(cash_received * 100)',
     'UPDATE sale SET cash_received = cash_received / 100.0'),
    ('sale', 'change_due', 'UPDATE sale SET change_due = ROUND(change_due * 100)',
     'UPDATE sale SET change_due = change_due / 100.0'),
    ('sale_item', 'unit_price', 'UPDATE sale_item SET unit_price = ROUND(unit_price * 100)',
     'UPDATE sale_item SET unit_price = unit_price / 100.0'),
    ('menu_option', 'price', 'UPDATE menu_option SET price = ROUND(price * 100)',
     'UPDATE menu_option SET price = price / 100.0'),
]


def upgrade():
    for table, column, to_centavos, _ in MONEY:
        op.execute(to_centavos)                                  # 75.5 -> 7550.0 (still REAL)
        with op.batch_alter_table(table) as batch:               # SQLite: the table is copied with the new type
            batch.alter_column(column, existing_type=sa.Float(), type_=sa.Integer(), existing_nullable=False)


def downgrade():
    for table, column, _, to_pesos in MONEY:
        with op.batch_alter_table(table) as batch:
            batch.alter_column(column, existing_type=sa.Integer(), type_=sa.Float(), existing_nullable=False)
        op.execute(to_pesos)                                     # 7550 -> 75.5
