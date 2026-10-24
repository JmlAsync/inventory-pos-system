"""The audit log (v0.27.0, audit R9, DEC-029): who changed what, when, with the old and new values.

Every store/ function that changes a product, a serving or add-on, an ingredient, a recipe line, the shop's details
or an account calls note() BEFORE its own commit, so the change and its line are saved together or not at all.
Lines are never edited or deleted, like receipts (rule I8).
"""
import json
from decimal import Decimal
from models import db, AuditEntry, User


def shown(value):
    """A value as text for the log: money as 150.00, True/False as yes/no, nothing as an empty string."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    if isinstance(value, Decimal):
        return f'{value:.2f}'
    return str(value)


def differences(thing, new_values):
    """{field: [old, new]} for each field in new_values whose value really changes on `thing` (as text)."""
    changes = {}
    for field, new in new_values.items():
        old = getattr(thing, field, None)
        if shown(old) != shown(new):
            changes[field] = [shown(old), shown(new)]
    return changes


def note(by, action, target, details=None):
    """Add one line to the log (the caller commits). by: the user id who did it, or None for setup_shop.py.
    action: e.g. 'product.update'; target: a short name such as 'Latte (L1)'; details: {field: [old, new]}."""
    db.session.add(AuditEntry(user_id=by, action=action, target=str(target)[:120],
                              details=json.dumps(details or {}, ensure_ascii=False)))


def entries(page=1, per_page=50, user_id=None, area=None):
    """One page of the log, newest first, optionally only one person's or one area's lines ('product', 'user'...).
    Returns (lines, there_are_older_ones)."""
    query = AuditEntry.query
    if user_id:
        query = query.filter(AuditEntry.user_id == user_id)
    if area:
        query = query.filter(AuditEntry.action.like(area + '.%'))
    rows = query.order_by(AuditEntry.id.desc()).offset((page - 1) * per_page).limit(per_page + 1).all()
    return rows[:per_page], len(rows) > per_page


def people():
    """Everyone who appears in the log, for the "who" filter."""
    return User.query.filter(User.id.in_(db.session.query(AuditEntry.user_id).distinct())).order_by(User.username).all()


def details_of(entry):
    """The {field: [old, new]} of a line, read back from its JSON text."""
    try:
        return json.loads(entry.details or '{}')
    except ValueError:
        return {}
