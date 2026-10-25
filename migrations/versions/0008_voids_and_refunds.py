"""Voids and refunds (v0.31.0): the adjustment tables, each line's ingredients, and where each sale stands

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-25

A receipt is never edited (rules I3, I8). A void or refund is a new sale_adjustment row with its adjustment_line rows
(DEC-007, DEC-033). sale.voided_at and sale.refunded_total, and sale_item.refunded_quantity, are changed only with
conditional updates, so two admins can't void twice or refund more than was paid. sale_item_usage keeps the
ingredients of each receipt line from now on, so a refund returns exactly what that line used.

Lines sold before this version have no sale_item_usage rows. Their used_recipe is filled in as well as it can be:
yes when the sale used ingredients and the product has a recipe today. Undoing removes all of it again.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('sale_adjustment',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('sale_id', sa.Integer(), nullable=False),
                    sa.Column('kind', sa.String(length=10), nullable=False),
                    sa.Column('status', sa.String(length=10), nullable=False),
                    sa.Column('total', sa.Integer(), nullable=False),
                    sa.Column('method', sa.String(length=10), nullable=True),
                    sa.Column('reference', sa.String(length=20), nullable=True),
                    sa.Column('reason', sa.String(length=200), nullable=False),
                    sa.Column('requested_by', sa.Integer(), nullable=False),
                    sa.Column('requested_at', sa.DateTime(), nullable=False),
                    sa.Column('decided_by', sa.Integer(), nullable=True),
                    sa.Column('decided_at', sa.DateTime(), nullable=True),
                    sa.Column('decided_how', sa.String(length=10), nullable=True),
                    sa.Column('note', sa.String(length=200), nullable=True),
                    sa.ForeignKeyConstraint(['sale_id'], ['sale.id']),
                    sa.ForeignKeyConstraint(['requested_by'], ['user.id']),
                    sa.ForeignKeyConstraint(['decided_by'], ['user.id']),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('reference'))
    op.create_index('ix_sale_adjustment_sale_id', 'sale_adjustment', ['sale_id'])

    op.create_table('adjustment_line',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('adjustment_id', sa.Integer(), nullable=False),
                    sa.Column('sale_item_id', sa.Integer(), nullable=False),
                    sa.Column('quantity', sa.Integer(), nullable=False),
                    sa.Column('amount', sa.Integer(), nullable=False),
                    sa.Column('restock', sa.Boolean(), nullable=False),
                    sa.ForeignKeyConstraint(['adjustment_id'], ['sale_adjustment.id']),
                    sa.ForeignKeyConstraint(['sale_item_id'], ['sale_item.id']),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_adjustment_line_adjustment_id', 'adjustment_line', ['adjustment_id'])

    op.create_table('sale_item_usage',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('sale_item_id', sa.Integer(), nullable=False),
                    sa.Column('ingredient_id', sa.Integer(), nullable=False),
                    sa.Column('amount', sa.Float(), nullable=False),
                    sa.ForeignKeyConstraint(['sale_item_id'], ['sale_item.id']),
                    sa.ForeignKeyConstraint(['ingredient_id'], ['ingredient.id']),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_sale_item_usage_sale_item_id', 'sale_item_usage', ['sale_item_id'])

    # server_default: sales that already exist are not voided and have no refunds
    with op.batch_alter_table('sale') as batch:
        batch.add_column(sa.Column('voided_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('refunded_total', sa.Integer(), nullable=False, server_default='0'))
    with op.batch_alter_table('sale_item') as batch:
        batch.add_column(sa.Column('refunded_quantity', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('used_recipe', sa.Boolean(), nullable=True))
    with op.batch_alter_table('ingredient_movement') as batch:
        batch.add_column(sa.Column('adjustment_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_ingredient_movement_adjustment_id', 'sale_adjustment', ['adjustment_id'], ['id'])
    with op.batch_alter_table('email_code') as batch:
        batch.add_column(sa.Column('adjustment_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_email_code_adjustment_id', 'sale_adjustment', ['adjustment_id'], ['id'])

    # Older lines: did their stock come from a recipe? Yes when the sale used ingredients and the product has one now.
    op.execute(sa.text(
        "UPDATE sale_item SET used_recipe = CASE WHEN "
        "EXISTS (SELECT 1 FROM ingredient_movement m WHERE m.sale_id = sale_item.sale_id AND m.reason = 'sale') "
        "AND EXISTS (SELECT 1 FROM recipe_item r WHERE r.product_id = sale_item.product_id) "
        "THEN :yes ELSE :no END").bindparams(yes=True, no=False))


def downgrade():
    with op.batch_alter_table('email_code') as batch:
        batch.drop_constraint('fk_email_code_adjustment_id', type_='foreignkey')
        batch.drop_column('adjustment_id')
    with op.batch_alter_table('ingredient_movement') as batch:
        batch.drop_constraint('fk_ingredient_movement_adjustment_id', type_='foreignkey')
        batch.drop_column('adjustment_id')
    with op.batch_alter_table('sale_item') as batch:
        batch.drop_column('used_recipe')
        batch.drop_column('refunded_quantity')
    with op.batch_alter_table('sale') as batch:
        batch.drop_column('refunded_total')
        batch.drop_column('voided_at')
    op.drop_index('ix_sale_item_usage_sale_item_id', table_name='sale_item_usage')
    op.drop_table('sale_item_usage')
    op.drop_index('ix_adjustment_line_adjustment_id', table_name='adjustment_line')
    op.drop_table('adjustment_line')
    op.drop_index('ix_sale_adjustment_sale_id', table_name='sale_adjustment')
    op.drop_table('sale_adjustment')
