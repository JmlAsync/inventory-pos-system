"""Login attempts (v0.26.0): a new table login_attempt for the 5-tries limit on passwords

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-24

Until v0.25.0 the wrong passwords were counted in the app's memory, so a restart forgot them and each server
process had its own count (audit R2). From v0.26.0 each try is a row here (DEC-028): a keyed hash of what is
limited and the time. Nothing is copied over: the old counts only lived in memory. Undoing drops the table.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('login_attempt',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('key', sa.String(length=64), nullable=False),
                    sa.Column('created_at', sa.DateTime(), nullable=False),
                    sa.PrimaryKeyConstraint('id'))
    # Indexes: tries are counted by key and tidied up by time, on every login
    op.create_index('ix_login_attempt_key', 'login_attempt', ['key'])
    op.create_index('ix_login_attempt_created_at', 'login_attempt', ['created_at'])


def downgrade():
    op.drop_index('ix_login_attempt_created_at', table_name='login_attempt')
    op.drop_index('ix_login_attempt_key', table_name='login_attempt')
    op.drop_table('login_attempt')
