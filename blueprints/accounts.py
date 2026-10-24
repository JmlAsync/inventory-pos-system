"""Log in, log out, the login limit, profile picture and password (v0.6.0, v0.12.0, v0.13.3, v0.13.5, v0.20.3).
Moved from app.py in v0.25.0 (DEC-027): the same rules; database changes now go through store/accounts.py."""
import os
from datetime import timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
from models import db, User, utc_now
from common import AVATAR_FOLDER, detect_image_type, delete_picture_file
from store import accounts as account_store

bp = Blueprint('accounts', __name__)

# ---------------- Logins that can be ended (v0.20.3, DEF-51) ----------------
# The login cookie is signed but kept by the browser, so before v0.20.3 a copied cookie kept
# working after log-out and after a password change. Now each login is a row in the
# login_session table and the cookie only carries that row's random token.
IDLE_TIMEOUT = timedelta(hours=8)          # a login unused for this long ends by itself
LAST_SEEN_EVERY = timedelta(minutes=1)     # write "last seen" at most once a minute (fewer database writes)


def start_login_session(user):
    """Called right after a correct password: remember this browser's login (v0.20.3)."""
    session['login_token'] = account_store.start_login(user, IDLE_TIMEOUT)


def forget_login():
    """Forget an ended login in this browser: who it was and the basket. The form token
    (_csrf_token) is kept, so a login page already on screen still works."""
    for key in ('_user_id', '_fresh', '_id', 'login_token', 'basket'):
        session.pop(key, None)


def load_user(user_id):
    """Runs on every request of a logged-in browser (registered in app.py). The user only counts as
    logged in if the cookie's token is still in the login_session table and was used in the last 8 hours."""
    row = account_store.find_login(session.get('login_token'))
    if row is None or str(row.user_id) != str(user_id):
        forget_login()    # logged out elsewhere, or a copied/forged cookie: forget it, basket included
        return None
    now = utc_now()   # v0.23.1: UTC, like last_seen
    if now - row.last_seen > IDLE_TIMEOUT:
        account_store.end_login(row)
        forget_login()    # the next person at this computer starts with an empty basket (like DEF-09)
        return None
    if now - row.last_seen > LAST_SEEN_EVERY:
        account_store.mark_seen(row, now)
    return db.session.get(User, row.user_id)


# ---------------- Login attempt limit (v0.13.3) ----------------
# Without a limit, a program can try thousands of passwords a minute. After
# MAX_LOGIN_FAILURES wrong passwords for one username from one computer (IP address),
# that computer must wait LOCKOUT_MINUTES before trying that username again.
# Counting per username AND computer means a stranger can't lock the real owner out.
# The counts live in memory, so restarting the app clears them.
MAX_LOGIN_FAILURES = 5
LOCKOUT_MINUTES = 5
failed_logins = {}   # (username, IP address) -> times of recent wrong passwords
# v0.19.3 (DEF-50): usernames are at most 50 characters (models.py), so only that much is
# remembered. Before, a 450 KB "username" was kept in memory at full length.
MAX_USERNAME_LENGTH = 50
# v0.21.4 (DEF-62): a hash of a random password nobody knows, made the same slow way as real ones,
# checked when the username doesn't exist (see login())
DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_hex(16))


def forget_old_failures():
    """v0.19.3 (DEF-50): drop every username whose wrong passwords are all older than the
    lockout window, not just the one being checked, so the list can't grow forever."""
    cutoff = utc_now() - timedelta(minutes=LOCKOUT_MINUTES)
    for key in [k for k, moments in failed_logins.items() if all(m <= cutoff for m in moments)]:
        del failed_logins[key]


def recent_failures(key):
    """Wrong-password times for this key within the lockout window (older ones are forgotten)."""
    cutoff = utc_now() - timedelta(minutes=LOCKOUT_MINUTES)
    recent = [moment for moment in failed_logins.get(key, []) if moment > cutoff]
    if recent:
        failed_logins[key] = recent
    else:
        failed_logins.pop(key, None)
    return recent


def page_after_login():
    """Where to go after a correct password: the page the user first asked for (?next=...), but only
    a page on THIS site, so a crafted link can't send them to another website. Otherwise Products. (v0.20.6, DEF-06)"""
    wanted = request.args.get('next', '')
    # A real local address starts with one "/" and has no second "/" or backslash after it
    # (browsers read "//host" and "/" + backslash + "host" as another website).
    if wanted.startswith('/') and not wanted.startswith(('//', '/' + chr(92))):
        return wanted
    return url_for('catalog.products')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    # Check the username and password, with the 5-tries limit, then start a login (v0.6.0)
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        key = (username.strip().lower()[:MAX_USERNAME_LENGTH], request.remote_addr)
        forget_old_failures()
        if len(recent_failures(key)) >= MAX_LOGIN_FAILURES:
            # 429 = "Too Many Requests"
            return render_template('login.html', error=f'Too many failed attempts. Please wait '
                                   f'{LOCKOUT_MINUTES} minutes and try again.'), 429
        user = User.query.filter_by(username=username).first()
        # v0.21.4 (DEF-62, audit A8): an unknown username checks a dummy hash too, so it takes as long as a
        # wrong password and the time taken can't tell anyone which usernames exist
        password_ok = check_password_hash(user.password_hash if user else DUMMY_PASSWORD_HASH, password)
        if user and password_ok:
            failed_logins.pop(key, None)   # a correct password resets the count
            session.clear()                # nothing from a previous login on this browser is kept
            start_login_session(user)      # v0.20.3: a login that log-out can really end
            login_user(user)
            return redirect(page_after_login())    # v0.20.6 (DEF-06): back to the page they first asked for
        failed_logins.setdefault(key, []).append(utc_now())
        return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')


@bp.route('/logout', methods=['POST'])   # a button, not a link, so other sites can't log you out (v0.13.2)
@login_required
def logout():
    # v0.20.3 (DEF-51): delete this browser's login row, so a copy of the cookie stops working too.
    # Other tills logged in with the same account stay logged in.
    account_store.end_login_by_token(session.get('login_token', ''))
    logout_user()
    session.clear()              # empties the basket too, so the next user starts fresh
    return redirect(url_for('reports.home'))


# ---------------- Profile picture (v0.12.0) ----------------
def delete_avatar_file(user):
    """Remove the user's current picture file, if any."""
    delete_picture_file(AVATAR_FOLDER, user.avatar)


@bp.app_template_global()
def avatar_url(user):
    """Web address of the user's picture, or None to show initials instead
    (also None if the file has gone missing)."""
    if user.avatar and os.path.exists(os.path.join(AVATAR_FOLDER, os.path.basename(user.avatar))):
        return url_for('static', filename='avatars/' + user.avatar)
    return None


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    # Profile page: change the profile picture and the password (v0.12.0, v0.13.1)
    if request.method == 'POST':
        file = request.files.get('picture')
        data = file.read() if file else b''
        if not data:
            flash('Choose a picture first.', 'danger')
            return redirect(url_for('accounts.profile'))
        kind = detect_image_type(data)
        if kind is None:
            flash('That file isn\'t a PNG, JPG or WebP picture.', 'danger')
            return redirect(url_for('accounts.profile'))
        os.makedirs(AVATAR_FOLDER, exist_ok=True)
        # A random file name, so nobody can guess or overwrite another user's picture
        filename = f'user{current_user.id}_{secrets.token_hex(8)}.{kind}'
        with open(os.path.join(AVATAR_FOLDER, filename), 'wb') as f:
            f.write(data)
        delete_avatar_file(current_user)   # remove the old picture
        account_store.set_avatar(current_user, filename)
        flash('Profile picture updated.', 'success')
        return redirect(url_for('accounts.profile'))
    return render_template('profile.html')


@bp.route('/profile/remove', methods=['POST'])
@login_required
def remove_avatar():
    # Remove the profile picture and go back to the initials circle (v0.12.0)
    delete_avatar_file(current_user)
    account_store.set_avatar(current_user, None)
    flash('Profile picture removed.', 'success')
    return redirect(url_for('accounts.profile'))


# ---------------- Change password (v0.13.5) ----------------
MIN_PASSWORD_LENGTH = 8


@bp.route('/profile/password', methods=['POST'])
@login_required
def change_password():
    """Lets a user replace a default password like admin123 with their own."""
    current = request.form.get('current_password', '')
    new = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')
    if not check_password_hash(current_user.password_hash, current):
        flash('Current password is wrong. Nothing was changed.', 'danger')
    elif new != confirm:
        flash('The new passwords do not match.', 'danger')
    elif new.lower() == current_user.username.lower():
        flash("Your password can't be the same as your username.", 'danger')
    elif len(new) < MIN_PASSWORD_LENGTH:
        flash(f'The new password must be at least {MIN_PASSWORD_LENGTH} characters long.', 'danger')
    elif new == current:
        flash('The new password is the same as the current one.', 'danger')
    else:
        # v0.20.3 (DEF-51): every login of this user ends, and this browser gets a new one
        token, ended = account_store.change_password(current_user, generate_password_hash(new),   # stored scrambled
                                                     session.get('login_token', ''), IDLE_TIMEOUT)
        session['login_token'] = token
        others = f'{ended} other device(s) logged in as you were logged out.' if ended else 'Other devices logged in as you would have been logged out.'
        flash('Password changed. Use the new one next time you log in. ' + others, 'success')
    return redirect(url_for('accounts.profile'))
