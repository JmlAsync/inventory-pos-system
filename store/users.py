"""The owner, invitations, emailed codes and changes to accounts (v0.27.0, rules S12, S14, S15, DEC-029).

Every change here writes its audit line (store/audit.py) in the same commit. Tokens and codes are kept only as keyed
hashes (common.keyed_hash) and compared with same_secret() (hmac.compare_digest). Steps that must happen once, such
as using an invitation or counting a wrong code, are conditional updates: they change 0 rows if another request
got there first, so two requests at the same moment can't both succeed.
"""
import secrets
from datetime import timedelta
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash
from common import keyed_hash, same_secret
from models import db, User, Invitation, EmailCode, LoginSession, utc_now
from store.accounts import record_try
from store.audit import note
from store.signin import forget_devices

INVITATION_HOURS = 48
CODE_MINUTES = 10
MAX_CODE_TRIES = 5
CODE_EVERY_SECONDS = 60     # at most one new code a minute per address and purpose (plan §2.4)
CODES_PER_HOUR = 5


# ---------------- Looking people up ----------------
def username_taken(username):
    """True if an account already uses this username, ignoring capitals ("Maria" and "maria" are the same person)."""
    return User.query.filter(func.lower(User.username) == username.lower()).first() is not None


def email_taken(email):
    return User.query.filter(func.lower(User.email) == email.lower()).first() is not None


def active_user_with_email(email):
    """The switched-on account whose CONFIRMED email this is, or None (for Forgot password)."""
    return User.query.filter(func.lower(User.email) == email.lower(), User.is_active.is_(True),
                             User.email_verified_at.isnot(None)).first()


def owner():
    return User.query.filter_by(role='owner').first()


def all_users():
    """Owner first, then admins, then cashiers; switched-off accounts last in each group."""
    order = {'owner': 0, 'admin': 1, 'cashier': 2}
    return sorted(User.query.all(), key=lambda u: (not u.is_active, order.get(u.role, 3), u.username.lower()))


# ---------------- The owner (setup_shop.py, until the licence in v0.39.0; owner's decision 1 in DEC-029) ----------------
def make_owner(username, email, password_hash):
    """Create the owner, or turn the existing admin with this username into the owner. Returns a sentence saying what
    happened. Called by setup_shop.py on the shop's computer, so the log line names nobody (by=None)."""
    existing_owner = owner()
    if existing_owner:
        return f'The owner account is "{existing_owner.username}"; it was left as it is.'
    user = User.query.filter_by(username=username).first()
    now = utc_now()
    if user:
        if user.role != 'admin':
            return None   # the caller refuses: only an admin can become the owner
        note(None, 'user.owner', user.username, {'role': [user.role, 'owner'], 'email': [user.email or '', email]})
        user.role, user.email = 'owner', email
        user.email_verified_at = None   # a new address must be confirmed again
        db.session.commit()
        return f'The admin account "{username}" is now the owner, with the email {email}.'
    db.session.add(User(username=username, password_hash=password_hash, role='owner', email=email, created_at=now))
    note(None, 'user.owner', username, {'role': ['', 'owner'], 'email': ['', email]})
    db.session.commit()
    return f'The owner account "{username}" was created, with the email {email}.'


# ---------------- Invitations (DEC-003) ----------------
def open_invitation_for(email):
    """An invitation to this address that can still be used, or None."""
    return (Invitation.query.filter(func.lower(Invitation.email) == email.lower(), Invitation.used_at.is_(None),
                                    Invitation.cancelled_at.is_(None), Invitation.expires_at > utc_now()).first())


def invitations():
    """Invitations not yet used or cancelled, newest first (expired ones too, so they can be sent again)."""
    return (Invitation.query.filter(Invitation.used_at.is_(None), Invitation.cancelled_at.is_(None))
            .order_by(Invitation.id.desc()).all())


def _new_token(invitation, now=None):
    """A fresh random token for the link; only its keyed hash is stored. The old link stops working."""
    token = secrets.token_urlsafe(32)
    invitation.token_hash = keyed_hash('invitation', token)
    invitation.expires_at = (now or utc_now()) + timedelta(hours=INVITATION_HOURS)
    invitation.pending_username = invitation.pending_password_hash = None
    return token


def create_invitation(email, role, by):
    """Store a new invitation; returns (invitation, token). The caller emails the link with the token."""
    now = utc_now()   # one reading of the clock, so it works exactly 48 hours from its creation
    invitation = Invitation(email=email, role=role, invited_by=by, created_at=now)
    token = _new_token(invitation, now)
    db.session.add(invitation)
    note(by, 'user.invite', email, {'role': ['', role]})
    db.session.commit()
    return invitation, token


def renew_invitation(invitation, by):
    """Resend: a new token and 48 more hours. Returns the token."""
    token = _new_token(invitation)
    note(by, 'user.invite-again', invitation.email)
    db.session.commit()
    return token


def cancel_invitation(invitation, by):
    invitation.cancelled_at = utc_now()
    note(by, 'user.invite-cancel', invitation.email)
    db.session.commit()


def invitation_by_token(token):
    """The invitation this link's token belongs to, if it can still be used; otherwise None."""
    if not token or len(token) > 100:
        return None
    wanted = keyed_hash('invitation', token)
    invitation = Invitation.query.filter_by(token_hash=wanted).first()
    if (invitation is None or not same_secret(invitation.token_hash, wanted) or invitation.used_at
            or invitation.cancelled_at or invitation.expires_at <= utc_now()):
        return None
    return invitation


def save_pending_signup(invitation, username, password_hash=None, google_sub=None):
    """Signup step 1: remember the chosen username and the password's hash (or, joining with Google since v0.29.0,
    Google's permanent id) until the code is entered."""
    invitation.pending_username, invitation.pending_password_hash = username, password_hash
    invitation.pending_google_sub = google_sub
    db.session.commit()


def google_sub_taken(sub):
    return User.query.filter_by(google_sub=sub).first() is not None


def finish_signup(invitation):
    """Signup step 2, after the right code: make the account with the INVITER's role (S12) and mark the invitation used,
    in one commit. Returns the new user, or None if the invitation was used a moment ago or the username was taken."""
    now = utc_now()
    used = (Invitation.query.filter(Invitation.id == invitation.id, Invitation.used_at.is_(None),
                                    Invitation.cancelled_at.is_(None))
            .update({Invitation.used_at: now}, synchronize_session=False))
    if used == 0:
        db.session.rollback()
        return None
    # Joining with Google (v0.29.0): a random password nobody knows; "Forgot your password?" can set a real one
    password_hash = invitation.pending_password_hash or generate_password_hash(secrets.token_hex(32))
    user = User(username=invitation.pending_username, password_hash=password_hash, role=invitation.role,
                email=invitation.email.lower(), email_verified_at=now, created_at=now,
                google_sub=invitation.pending_google_sub)
    db.session.add(user)
    try:
        db.session.flush()   # gives the new account its id, still inside the same transaction
    except IntegrityError:
        db.session.rollback()   # the username or email was taken in the meantime: nothing is saved
        return None
    invitation.user_id, invitation.pending_password_hash, invitation.pending_google_sub = user.id, None, None
    note(user.id, 'user.join', user.username, {'role': ['', user.role], 'email': ['', user.email]})
    db.session.commit()
    return user


# ---------------- Emailed codes (S14, plan §2.4) ----------------
def code_hash(purpose, email, code):
    """The code is bound to its purpose and address: a signup code can't reset a password (S14)."""
    return keyed_hash('code', purpose, email.lower(), code)


def may_send_code(purpose, email):
    """None if a new code may be sent now, otherwise a sentence saying when. One a minute, 5 an hour per address."""
    last = (EmailCode.query.filter(EmailCode.purpose == purpose, func.lower(EmailCode.email) == email.lower())
            .order_by(EmailCode.id.desc()).first())
    # v0.28.0: a code already used successfully doesn't make the next login wait (log out and in again within a
    # minute); the wait stops repeated resends of an open code, or of one cancelled by 5 wrong tries
    used_successfully = last is not None and last.used_at is not None and last.attempts < MAX_CODE_TRIES
    if last and not used_successfully and utc_now() - last.created_at < timedelta(seconds=CODE_EVERY_SECONDS):
        return 'A code was sent less than a minute ago. Wait a minute before asking for another one.'
    if not record_try(keyed_hash('code-sent', purpose, email.lower()), timedelta(hours=1), CODES_PER_HOUR):
        return f'{CODES_PER_HOUR} codes were sent to this address in the last hour. Please try again later.'
    return None


def new_code(purpose, email, user_id=None, invitation_id=None):
    """Make a 6-digit code (the older ones for this purpose and address stop working). Returns it, to be emailed."""
    now = utc_now()
    (EmailCode.query.filter(EmailCode.purpose == purpose, func.lower(EmailCode.email) == email.lower(),
                            EmailCode.used_at.is_(None))
     .update({EmailCode.used_at: now}, synchronize_session=False))
    code = f'{secrets.randbelow(1_000_000):06d}'   # 000000-999999, from the operating system's secure random source
    db.session.add(EmailCode(purpose=purpose, email=email.lower(), user_id=user_id, invitation_id=invitation_id,
                             code_hash=code_hash(purpose, email, code), created_at=now,
                             expires_at=now + timedelta(minutes=CODE_MINUTES)))
    db.session.commit()
    return code


def check_code(purpose, email, code):
    """Check a typed code. Returns (row, None) when it is right (the code is now used up), or (None, tries_left):
    tries_left is how many tries remain, or 0 when there is no usable code (expired, used, or 5 wrong tries).
    The try is counted BEFORE comparing, in one conditional update, like the login limit (DEC-028)."""
    now = utc_now()
    row = (EmailCode.query.filter(EmailCode.purpose == purpose, func.lower(EmailCode.email) == email.lower(),
                                  EmailCode.used_at.is_(None), EmailCode.expires_at > now)
           .order_by(EmailCode.id.desc()).first())
    if row is None:
        return None, 0
    counted = (EmailCode.query.filter(EmailCode.id == row.id, EmailCode.used_at.is_(None),
                                      EmailCode.attempts < MAX_CODE_TRIES)
               .update({EmailCode.attempts: EmailCode.attempts + 1}, synchronize_session=False))
    db.session.commit()
    if counted == 0:
        return None, 0
    typed = ''.join(ch for ch in (code or '') if ch.isdigit())[:6]   # "123 456" and "123-456" are fine too
    if len(typed) == 6 and same_secret(row.code_hash, code_hash(purpose, email, typed)):
        used = (EmailCode.query.filter(EmailCode.id == row.id, EmailCode.used_at.is_(None))
                .update({EmailCode.used_at: now}, synchronize_session=False))
        db.session.commit()
        return (row, None) if used else (None, 0)
    db.session.refresh(row)
    if row.attempts >= MAX_CODE_TRIES:   # the 5th wrong try cancels the code: a new one must be sent
        row.used_at = now
        db.session.commit()
        return None, 0
    return None, MAX_CODE_TRIES - row.attempts


# ---------------- Changing accounts (S15: who may do what is checked by the page) ----------------
def end_all_logins(user):
    """Every browser logged in as this person is logged out (v0.20.3 login rows). The caller commits."""
    LoginSession.query.filter_by(user_id=user.id).delete()


def set_role(user, role, by):
    note(by, 'user.role', user.username, {'role': [user.role, role]})
    user.role = role
    forget_devices(user)   # v0.28.0: trust lasts 30 days for cashiers but 7 for admins, so it starts again
    if role != 'admin':
        user.can_invite = False   # "may invite" only means something for admins
    db.session.commit()


def set_active(user, active, by):
    """Switch an account off (it can't log in, and every login ends now) or on again. Never deleted."""
    note(by, 'user.switch-on' if active else 'user.switch-off', user.username, {'active': [user.is_active, active]})
    user.is_active = active
    if not active:
        end_all_logins(user)
        forget_devices(user)   # v0.28.0 (S13)
    db.session.commit()


def require_new_password(user, by):
    note(by, 'user.require-password', user.username, {'must choose a new password': [user.must_change_password, True]})
    user.must_change_password = True
    db.session.commit()


def set_can_invite(user, allowed, by):
    note(by, 'user.may-invite', user.username, {'may invite cashiers': [user.can_invite, allowed]})
    user.can_invite = allowed
    db.session.commit()


def reset_password(user, new_hash):
    """Forgot password, after the right code: the new password, and every login of this person ends."""
    user.password_hash = new_hash
    user.must_change_password = False
    end_all_logins(user)
    forget_devices(user)   # v0.28.0 (S13)
    note(user.id, 'user.password-reset', user.username)
    db.session.commit()


def clear_must_change(user):
    """After "Choose a new password" saved the new one (store.accounts.change_password already committed it)."""
    user.must_change_password = False
    note(user.id, 'user.password-chosen', user.username)
    db.session.commit()


def set_email(user, email):
    """A new address, proven by a code just now (Profile)."""
    note(user.id, 'user.email', user.username, {'email': [user.email or '', email]})
    user.email, user.email_verified_at = email.lower(), utc_now()
    db.session.commit()


def confirm_email(user):
    """The owner proved the address setup_shop.py stored (owner's decision 1 in DEC-029)."""
    note(user.id, 'user.email-confirmed', user.username)
    user.email_verified_at = utc_now()
    db.session.commit()


def add_email_for(user, email, by):
    """v0.28.0 (owner's decision 1 in DEC-030): the owner, or an admin for a cashier, types the address of an account
    that has none. It is confirmed by the code that person's next login sends there."""
    note(by, 'user.email', user.username, {'email': [user.email or '', email]})
    user.email, user.email_verified_at = email.lower(), None
    db.session.commit()


def confirm_email_by_login(user):
    """The login code sent to an unconfirmed address was typed: the address is now proven (v0.28.0)."""
    if user.email and not user.email_verified_at:
        note(user.id, 'user.email-confirmed', user.username)
        user.email_verified_at = utc_now()
        db.session.commit()
