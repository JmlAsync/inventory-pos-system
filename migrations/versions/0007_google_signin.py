"""Sign in with Google (v0.29.0): Google's permanent id on the account, and on an invitation while joining

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-25

A Google account is linked by Google's permanent id ("sub"), never by the email (DEC-031). user.google_sub is unique,
so one Google account can open only one account here. invitation.pending_google_sub holds it while someone joins with
Google, until the emailed code is entered. Undoing removes both.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user') as batch:
        batch.add_column(sa.Column('google_sub', sa.String(length=255), nullable=True))
        batch.create_unique_constraint('uq_user_google_sub', ['google_sub'])
    with op.batch_alter_table('invitation') as batch:
        batch.add_column(sa.Column('pending_google_sub', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('invitation') as batch:
        batch.drop_column('pending_google_sub')
    with op.batch_alter_table('user') as batch:
        batch.drop_constraint('uq_user_google_sub', type_='unique')
        batch.drop_column('google_sub')
