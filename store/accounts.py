"""Logins, passwords and profile pictures (v0.12.0, v0.13.5, v0.20.3). Moved from app.py in v0.25.0 (DEC-027);
the steps are unchanged. Each login is a row in login_session; the cookie only carries its random token."""
import secrets
from models import db, LoginSession, utc_now


def start_login(user, idle_timeout):
    """A new login for this user; tidies up logins idle longer than idle_timeout. Returns the token."""
    now = utc_now()   # v0.23.1: UTC
    LoginSession.query.filter(LoginSession.last_seen < now - idle_timeout).delete()   # tidy up old logins
    token = secrets.token_hex(32)
    db.session.add(LoginSession(token=token, user_id=user.id, created_at=now, last_seen=now))
    db.session.commit()
    return token


def find_login(token):
    return LoginSession.query.filter_by(token=token).first() if token else None


def end_login(row):
    db.session.delete(row)
    db.session.commit()


def end_login_by_token(token):
    """Log-out (v0.20.3): delete this browser's row, so a copy of the cookie stops working too."""
    LoginSession.query.filter_by(token=token or '').delete()
    db.session.commit()


def mark_seen(row, now):
    row.last_seen = now
    db.session.commit()


def change_password(user, new_hash, current_token, idle_timeout):
    """Save the new password hash and end EVERY login of this user, including this browser's token
    (a stolen copy of the cookie carries the same one); then start a new login for this browser.
    Returns (new token, how many OTHER logins were ended)."""
    user.password_hash = new_hash
    ended = LoginSession.query.filter(LoginSession.user_id == user.id, LoginSession.token != (current_token or '')).count()
    LoginSession.query.filter_by(user_id=user.id).delete()
    return start_login(user, idle_timeout), ended   # commits the new password and the new token together


def set_avatar(user, filename):
    """The user's picture file name, or None for the initials circle."""
    user.avatar = filename
    db.session.commit()
