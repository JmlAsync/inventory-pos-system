"""Times in UTC (v0.23.1): every stored time is turned from this computer's local time into UTC

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-24

Until v0.23.0 the app stored datetime.now(), the local time of the computer it ran on. From v0.23.1 it stores
UTC and shows the shop's time (UTC+8). The old times were written on this same computer, so its own time-zone
setting is the right way to convert them (DEC-024). Undoing turns them back exactly.
"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

# The four stored times, each with a fixed SELECT and UPDATE (no SQL built from pieces, rule S5)
COLUMNS = [
    ('SELECT id, created_at FROM sale', 'UPDATE sale SET created_at = :t WHERE id = :i'),
    ('SELECT id, created_at FROM login_session', 'UPDATE login_session SET created_at = :t WHERE id = :i'),
    ('SELECT id, last_seen FROM login_session', 'UPDATE login_session SET last_seen = :t WHERE id = :i'),
    ('SELECT id, created_at FROM ingredient_movement', 'UPDATE ingredient_movement SET created_at = :t WHERE id = :i'),
]


def read_time(value):
    """SQLite gives the time back as text, other databases as a datetime."""
    return datetime.fromisoformat(value) if isinstance(value, str) else value


def local_to_utc(moment):
    # A time without a zone is read by astimezone() as this computer's local time
    return moment.astimezone(timezone.utc).replace(tzinfo=None)


def utc_to_local(moment):
    return moment.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)


def convert(change):
    bind = op.get_bind()
    for select, update in COLUMNS:
        for row_id, value in bind.execute(sa.text(select)).fetchall():
            if value is not None:
                new = change(read_time(value))
                bind.execute(sa.text(update), {'t': new.strftime('%Y-%m-%d %H:%M:%S.%f'), 'i': row_id})


def upgrade():
    convert(local_to_utc)


def downgrade():
    convert(utc_to_local)
