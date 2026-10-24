"""The second step at login (v0.28.0, rules S13 and S14, DEC-005, DEC-017, DEC-030): trusted devices, backup codes,
the authenticator app, and Log out everywhere.

Tokens and backup codes are kept only as keyed hashes; the authenticator key only encrypted (totp.py). Steps that must
happen once (a backup code, an app code's 30-second step) are conditional updates, so two requests at the same moment
can't both use them. Changes that matter for safety write an audit line (store/audit.py).
"""
import secrets
from datetime import timedelta
import totp
from common import keyed_hash, same_secret
from models import db, User, TrustedDevice, BackupCode, LoginSession, utc_now
from store.audit import note

TRUST_DAYS = {'cashier': 30, 'admin': 7, 'owner': 7}   # DEC-005: shorter for accounts that can change more
MAX_TRUSTED_IN_COOKIE = 10
BACKUP_CODE_COUNT = 10
BACKUP_LETTERS = 'abcdefghjkmnpqrstuvwxyz23456789'   # no 0/o, 1/l/i: nothing to confuse on paper


# ---------------- Trusted devices (DEC-005) ----------------
def trust_days(user):
    return TRUST_DAYS.get(user.role, 7)


def trust_device(user, label):
    """Remember this browser for this user. Returns the random token for the cookie (only its hash is stored)."""
    token = secrets.token_urlsafe(32)
    now = utc_now()
    db.session.add(TrustedDevice(user_id=user.id, token_hash=keyed_hash('device', token), label=label[:60],
                                 created_at=now, last_used_at=now, expires_at=now + timedelta(days=trust_days(user))))
    note(user.id, 'user.trust-device', user.username, {'device': ['', label[:60]]})
    db.session.commit()
    return token


def trusted_device_for(user, tokens):
    """The unexpired trusted device of THIS user among the cookie's tokens, or None. Marks it used now."""
    now = utc_now()
    for token in tokens[:MAX_TRUSTED_IN_COOKIE]:
        wanted = keyed_hash('device', token)
        row = TrustedDevice.query.filter_by(token_hash=wanted, user_id=user.id).first()
        if row and same_secret(row.token_hash, wanted) and row.expires_at > now:
            row.last_used_at = now
            db.session.commit()
            return row
    return None


def devices(user):
    """This user's trusted devices that haven't expired, newest first."""
    return (TrustedDevice.query.filter(TrustedDevice.user_id == user.id, TrustedDevice.expires_at > utc_now())
            .order_by(TrustedDevice.id.desc()).all())


def remove_device(user, device_id):
    """Profile > Devices > Remove. Only the user's own devices. Returns True if one was removed."""
    row = TrustedDevice.query.filter_by(id=device_id, user_id=user.id).first()
    if row is None:
        return False
    note(user.id, 'user.untrust-device', user.username, {'device': [row.label, '']})
    db.session.delete(row)
    db.session.commit()
    return True


def forget_devices(user):
    """Every trusted device of this user ends (the caller commits): password change, switch off, role change."""
    TrustedDevice.query.filter_by(user_id=user.id).delete()


def logout_everywhere(user):
    """Profile > Log out everywhere: every login of this user ends, and every trusted device too (S13)."""
    LoginSession.query.filter_by(user_id=user.id).delete()
    forget_devices(user)
    note(user.id, 'user.logout-everywhere', user.username)
    db.session.commit()


# ---------------- Backup codes (plan §2.6) ----------------
def tidy_backup_code(typed):
    """'K7MP 29XA', 'k7mp-29xa' and 'k7mp29xa' are the same code."""
    return ''.join(ch for ch in (typed or '').lower() if ch.isalnum())


def new_backup_codes(user):
    """Make 10 new backup codes (the old ones stop working). Returns them, shown once as xxxx-xxxx."""
    BackupCode.query.filter(BackupCode.user_id == user.id, BackupCode.used_at.is_(None)).update(
        {BackupCode.used_at: utc_now()}, synchronize_session=False)
    codes = [''.join(secrets.choice(BACKUP_LETTERS) for _ in range(8)) for _ in range(BACKUP_CODE_COUNT)]
    for code in codes:
        db.session.add(BackupCode(user_id=user.id, code_hash=keyed_hash('backup', user.id, code)))
    note(user.id, 'user.backup-codes', user.username)
    db.session.commit()
    return [f'{code[:4]}-{code[4:]}' for code in codes]


def use_backup_code(user, typed):
    """True if this is one of the user's unused backup codes; it is used up at once (one conditional update)."""
    code = tidy_backup_code(typed)
    if len(code) != 8:
        return False
    wanted = keyed_hash('backup', user.id, code)
    for row in BackupCode.query.filter(BackupCode.user_id == user.id, BackupCode.used_at.is_(None)).all():
        if same_secret(row.code_hash, wanted):
            used = (BackupCode.query.filter(BackupCode.id == row.id, BackupCode.used_at.is_(None))
                    .update({BackupCode.used_at: utc_now()}, synchronize_session=False))
            note(user.id, 'user.backup-code-used', user.username)
            db.session.commit()
            return used == 1
    return False


def backup_codes_left(user):
    return BackupCode.query.filter(BackupCode.user_id == user.id, BackupCode.used_at.is_(None)).count()


# ---------------- The authenticator app (DEC-017) ----------------
def start_app(user):
    """Set-up step 1: a new key, kept encrypted as "pending" until the app's first code proves the scan."""
    key = totp.new_key()
    user.totp_pending_encrypted = totp.lock(key)
    db.session.commit()
    return key


def pending_key(user):
    return totp.unlock(user.totp_pending_encrypted) if user.totp_pending_encrypted else None


def finish_app(user, typed):
    """Set-up step 2: if the code matches the pending key, the app becomes this user's second step. Returns True/False."""
    key = pending_key(user)
    step = totp.matching_step(key, typed) if key else None
    if step is None:
        return False
    note(user.id, 'user.second-step', user.username, {'sign-in method': ['email', 'app']})
    user.second_step, user.totp_key_encrypted, user.totp_pending_encrypted = 'app', user.totp_pending_encrypted, None
    user.totp_last_step = step   # the code just typed can't be used again to log in
    db.session.commit()
    return True


def check_app_code(user, typed):
    """True if the code matches the user's app key for a 30-second step NOT used before. The step is saved in one
    conditional update, so the same code can't log in twice, even at the same moment (S14)."""
    key = totp.unlock(user.totp_key_encrypted) if user.totp_key_encrypted else None
    step = totp.matching_step(key, typed) if key else None
    if step is None:
        return False
    saved = (User.query.filter(User.id == user.id,
                               (User.totp_last_step.is_(None)) | (User.totp_last_step < step))
             .update({User.totp_last_step: step}, synchronize_session=False))
    db.session.commit()
    return saved == 1


def back_to_email(user, by):
    """Turn the app off (by the user, or an admin's reset): the emailed code again. The key is deleted."""
    note(by, 'user.second-step', user.username, {'sign-in method': ['app', 'email']})
    user.second_step, user.totp_key_encrypted, user.totp_pending_encrypted, user.totp_last_step = 'email', None, None, None
    db.session.commit()
