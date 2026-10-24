"""Owner, invitations, emailed codes and the audit log (v0.27.0)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-24

The user table gets an email (and when it was confirmed), "switched on", "must choose a new password", "may invite"
and a creation time, plus an index that allows only ONE owner. Three new tables: invitation, email_code and
audit_log (DEC-029). Existing accounts keep working exactly as before: switched on, no email yet, same role.
The owner is chosen afterwards by running setup_shop.py. Undoing removes all of it again.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user') as batch:   # SQLite: the table is copied with the new columns
        batch.add_column(sa.Column('email', sa.String(length=254), nullable=True))
        batch.add_column(sa.Column('email_verified_at', sa.DateTime(), nullable=True))
        # server_default: the accounts that already exist are switched on, with no flags set
        batch.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column('can_invite', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        batch.create_unique_constraint('uq_user_email', ['email'])
    op.create_index('uq_user_one_owner', 'user', ['role'], unique=True,
                    sqlite_where=sa.text("role = 'owner'"), postgresql_where=sa.text("role = 'owner'"))

    op.create_table('invitation',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('email', sa.String(length=254), nullable=False),
                    sa.Column('role', sa.String(length=20), nullable=False),
                    sa.Column('token_hash', sa.String(length=64), nullable=False),
                    sa.Column('invited_by', sa.Integer(), nullable=False),
                    sa.Column('created_at', sa.DateTime(), nullable=False),
                    sa.Column('expires_at', sa.DateTime(), nullable=False),
                    sa.Column('used_at', sa.DateTime(), nullable=True),
                    sa.Column('cancelled_at', sa.DateTime(), nullable=True),
                    sa.Column('user_id', sa.Integer(), nullable=True),
                    sa.Column('pending_username', sa.String(length=50), nullable=True),
                    sa.Column('pending_password_hash', sa.String(length=200), nullable=True),
                    sa.ForeignKeyConstraint(['invited_by'], ['user.id']),
                    sa.ForeignKeyConstraint(['user_id'], ['user.id']),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('token_hash'))

    op.create_table('email_code',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('purpose', sa.String(length=10), nullable=False),
                    sa.Column('email', sa.String(length=254), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=True),
                    sa.Column('invitation_id', sa.Integer(), nullable=True),
                    sa.Column('code_hash', sa.String(length=64), nullable=False),
                    sa.Column('attempts', sa.Integer(), nullable=False),
                    sa.Column('created_at', sa.DateTime(), nullable=False),
                    sa.Column('expires_at', sa.DateTime(), nullable=False),
                    sa.Column('used_at', sa.DateTime(), nullable=True),
                    sa.ForeignKeyConstraint(['invitation_id'], ['invitation.id']),
                    sa.ForeignKeyConstraint(['user_id'], ['user.id']),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_email_code_email', 'email_code', ['email'])

    op.create_table('audit_log',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('created_at', sa.DateTime(), nullable=False),
                    sa.Column('user_id', sa.Integer(), nullable=True),
                    sa.Column('action', sa.String(length=40), nullable=False),
                    sa.Column('target', sa.String(length=120), nullable=False),
                    sa.Column('details', sa.Text(), nullable=False),
                    sa.ForeignKeyConstraint(['user_id'], ['user.id']),
                    sa.PrimaryKeyConstraint('id'))
    op.create_index('ix_audit_log_created_at', 'audit_log', ['created_at'])
    op.create_index('ix_audit_log_action', 'audit_log', ['action'])


def downgrade():
    op.drop_index('ix_audit_log_action', table_name='audit_log')
    op.drop_index('ix_audit_log_created_at', table_name='audit_log')
    op.drop_table('audit_log')
    op.drop_index('ix_email_code_email', table_name='email_code')
    op.drop_table('email_code')
    op.drop_table('invitation')
    op.drop_index('uq_user_one_owner', table_name='user')
    with op.batch_alter_table('user') as batch:
        batch.drop_constraint('uq_user_email', type_='unique')
        for column in ('created_at', 'can_invite', 'must_change_password', 'is_active', 'email_verified_at', 'email'):
            batch.drop_column(column)
