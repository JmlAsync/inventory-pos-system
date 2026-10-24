"""Login codes (v0.28.0): the sign-in method, the authenticator key, trusted devices and backup codes

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-25

Every login now needs a code unless the browser is trusted (rule S13, DEC-030). The user table gets the second step
('email' by default) and the encrypted authenticator key; two new tables hold trusted devices and backup codes, both
as keyed hashes only (S14). Existing accounts start with the emailed code. Undoing removes all of it again.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user') as batch:
        batch.add_column(sa.Column('second_step', sa.String(length=10), nullable=False, server_default='email'))
        batch.add_column(sa.Column('totp_key_encrypted', sa.Text(), nullable=True))
        batch.add_column(sa.Column('totp_pending_encrypted', sa.Text(), nullable=True))
        batch.add_column(sa.Column('totp_last_step', sa.Integer(), nullable=True))

    op.create_table('trusted_device',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.Column('token_hash', sa.String(length=64), nullable=False),
                    sa.Column('label', sa.String(length=60), nullable=False),
                    sa.Column('created_at', sa.DateTime(), nullable=False),
                    sa.Column('last_used_at', sa.DateTime(), nullable=False),
                    sa.Column('expires_at', sa.DateTime(), nullable=False),
                    sa.ForeignKeyConstraint(['user_id'], ['user.id']),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('token_hash'))

    op.create_table('backup_code',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=False),
                    sa.Column('code_hash', sa.String(length=64), nullable=False),
                    sa.Column('created_at', sa.DateTime(), nullable=False),
                    sa.Column('used_at', sa.DateTime(), nullable=True),
                    sa.ForeignKeyConstraint(['user_id'], ['user.id']),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_backup_code_user_id', 'backup_code', ['user_id'])


def downgrade():
    op.drop_index('ix_backup_code_user_id', table_name='backup_code')
    op.drop_table('backup_code')
    op.drop_table('trusted_device')
    with op.batch_alter_table('user') as batch:
        for column in ('totp_last_step', 'totp_pending_encrypted', 'totp_key_encrypted', 'second_step'):
            batch.drop_column(column)
