"""Authenticator-app codes (v0.28.0, rules S13 and S14, DEC-017, DEC-030).

The standard every authenticator app follows (TOTP, RFC 6238): the phone and the server share a random key; every
30 seconds both work out a 6-digit code from the key and the clock (HMAC-SHA1). No internet is needed on either side.

The key can't be stored as a hash like other codes, because the server must work out the code from it, so it is
stored ENCRYPTED (Fernet from the `cryptography` package) with a key of its own: the TOTP_ENCRYPTION_KEY
environment variable, or instance/totp_key.txt, made once and never put in Git (rule P1).
"""
import base64
import hmac
import hashlib
import os
import secrets
import struct
import time
from urllib.parse import quote
from flask import current_app

STEP_SECONDS = 30
DIGITS = 6
WINDOW = 1   # also accept the step just before and just after, for a phone clock a little off


# ---------------- The codes (RFC 6238) ----------------
def new_key():
    """A new random 160-bit key, in the base-32 letters authenticator apps use (32 characters)."""
    return base64.b32encode(secrets.token_bytes(20)).decode()


def code_at(key, step):
    """The 6-digit code for one 30-second step (RFC 4226 "dynamic truncation")."""
    digest = hmac.new(base64.b32decode(key), struct.pack('>Q', step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f'{number % 10 ** DIGITS:0{DIGITS}d}'


def current_step(now=None):
    return int((time.time() if now is None else now) // STEP_SECONDS)


def matching_step(key, typed, now=None):
    """The step (-1, 0 or +1 around now) whose code matches what was typed, or None. Each candidate is compared with
    hmac.compare_digest (S14). Whether that step was already used is checked by the caller (store/signin.py)."""
    typed = ''.join(ch for ch in (typed or '') if ch.isdigit())
    if len(typed) != DIGITS:
        return None
    step = current_step(now)
    for candidate in range(step - WINDOW, step + WINDOW + 1):
        if hmac.compare_digest(code_at(key, candidate), typed):
            return candidate
    return None


def setup_link(key, account, issuer):
    """The otpauth:// address an app reads from the QR code, e.g. for account "maria" at "Sample Café"."""
    label = quote(f'{issuer}:{account}')
    return (f'otpauth://totp/{label}?secret={key}&issuer={quote(issuer)}'
            f'&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}')


def qr_image(link):
    """The QR code as an SVG "data:" address for an <img>, drawn here by segno (DEC-017): no file is written and no
    outside service sees the key. Shown only during set-up, on a page the browser is told not to keep."""
    import segno
    return segno.make(link, error='m').svg_data_uri(scale=5, border=2, dark='#000', light='#fff')


# ---------------- Keeping the key encrypted ----------------
def _box():
    """The Fernet "box" that locks and unlocks authenticator keys. Its own key comes from TOTP_ENCRYPTION_KEY or
    instance/totp_key.txt (made the first time it is needed), never from the database it protects."""
    from cryptography.fernet import Fernet
    secret = os.environ.get('TOTP_ENCRYPTION_KEY')
    if not secret:
        path = os.path.join(current_app.instance_path, 'totp_key.txt')
        if not os.path.exists(path):
            os.makedirs(current_app.instance_path, exist_ok=True)
            with open(path, 'wb') as f:
                f.write(Fernet.generate_key())
        with open(path, 'rb') as f:
            secret = f.read().strip()
    return Fernet(secret)


def lock(key):
    return _box().encrypt(key.encode()).decode()


def unlock(locked):
    """The key again, or None if it can't be read (a different encryption key, or a damaged value)."""
    from cryptography.fernet import InvalidToken
    try:
        return _box().decrypt(locked.encode()).decode()
    except (InvalidToken, ValueError, AttributeError):
        return None
