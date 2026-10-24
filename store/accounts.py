"""Logins, passwords and profile pictures (v0.12.0, v0.13.5, v0.20.3). Moved from app.py in v0.25.0 (DEC-027);
the steps are unchanged. Each login is a row in login_session; the cookie only carries its random token.
Since v0.26.0 the tries with a limit (wrong passwords) are rows in login_attempt (DEC-028)."""
import secrets
from models import db, LoginSession, LoginAttempt, utc_now
from store.audit import note


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
    note(user.id, 'user.password', user.username)   # v0.27.0: who changed a password and when, never the password
    ended = LoginSession.query.filter(LoginSession.user_id == user.id, LoginSession.token != (current_token or '')).count()
    LoginSession.query.filter_by(user_id=user.id).delete()
    return start_login(user, idle_timeout), ended   # commits the new password and the new token together


def set_avatar(user, filename):
    """The user's picture file name, or None for the initials circle."""
    user.avatar = filename
    db.session.commit()


# ---------------- Tries with a limit (v0.26.0, DEC-028, audit R2 and A7) ----------------
# Used for wrong passwords on the login page and on Change password. Rows live in the database, so a restart
# doesn't forget them and every server process sees the same count.

def record_try(key, window, limit):
    """Record one try under this key FIRST, then count the tries in the last `window`. Returns True if this try
    is within the limit. If it is over the limit, its row is removed again (so a refused try doesn't make the
    wait longer) and False is returned. Recording before counting means two tries at the same moment can't
    both see "4" and both get through: the one that counts last sees both rows."""
    now = utc_now()
    LoginAttempt.query.filter(LoginAttempt.created_at <= now - window).delete()   # tidy up: old tries no longer count
    row = LoginAttempt(key=key, created_at=now)
    db.session.add(row)
    db.session.commit()
    if LoginAttempt.query.filter(LoginAttempt.key == key, LoginAttempt.created_at > now - window).count() > limit:
        db.session.delete(row)
        db.session.commit()
        return False
    return True


def forget_tries(key):
    """A correct password: every try under this key is forgotten, so the count starts again (as since v0.13.3)."""
    LoginAttempt.query.filter_by(key=key).delete()
    db.session.commit()
