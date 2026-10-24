"""Log in, log out, the login limit, profile picture and password (v0.6.0, v0.12.0, v0.13.3, v0.13.5, v0.20.3).
Moved from app.py in v0.25.0 (DEC-027): the same rules; database changes now go through store/accounts.py.
Since v0.26.0 (DEC-028) the wrong passwords are counted in the database, on Change password too."""
import os
import time
from datetime import timedelta
from flask import (Blueprint, render_template, request, redirect, url_for, session, flash, current_app,
                   make_response, abort)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
from models import db, User, utc_now
from common import AVATAR_FOLDER, detect_image_type, delete_picture_file, keyed_hash, network_address, shop_now
from store import accounts as account_store
from store import users as user_store
from store import signin as signin_store
import totp
from store.shop import shop_profile
from mail import send_mail, mail_settings, check_email_address

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
    user = db.session.get(User, row.user_id)
    if user is None or not user.is_active:   # v0.27.0: an account switched off since this login started
        forget_login()
        return None
    return user


@bp.before_app_request
def must_choose_password():
    """v0.27.0 (audit A5, DEC-029): after "Require a new password" on Users, every page sends the person to
    Choose a new password until they have; they can still log out."""
    if (current_user.is_authenticated and current_user.must_change_password
            and request.endpoint not in ('accounts.choose_password', 'accounts.logout', 'static')):
        return redirect(url_for('accounts.choose_password'))


# ---------------- Login attempt limit (v0.13.3; in the database since v0.26.0) ----------------
# Without a limit, a program can try thousands of passwords a minute. After
# MAX_LOGIN_FAILURES wrong passwords for one username from one computer (IP address),
# that computer must wait LOCKOUT_MINUTES before trying that username again.
# Counting per username AND computer means a stranger can't lock the real owner out.
# v0.26.0 (DEF-70, DEC-028, audit R2): the tries are rows in the login_attempt table, so a restart no
# longer clears them; until then they lived in memory.
MAX_LOGIN_FAILURES = 5
LOCKOUT_MINUTES = 5
LOCKOUT_WINDOW = timedelta(minutes=LOCKOUT_MINUTES)
# v0.19.3 (DEF-50): usernames are at most 50 characters (models.py), so only that much is
# counted. Before, a 450 KB "username" was kept in memory at full length.
MAX_USERNAME_LENGTH = 50
# v0.21.4 (DEF-62): a hash of a random password nobody knows, made the same slow way as real ones,
# checked when the username doesn't exist (see login())
DUMMY_PASSWORD_HASH = generate_password_hash(secrets.token_hex(16))


def attempt_key(*parts):
    """The key a try is counted under (v0.26.0, DEC-028): a keyed hash (HMAC-SHA256 with the secret key) of the
    parts, e.g. attempt_key('login', 'cashier', '192.168.1.20'). The table never holds what someone typed:
    people sometimes type their password into the username box. Always 64 characters, however long the input."""
    return keyed_hash(*parts)   # common.py since v0.27.0: tokens and codes use the same keyed hash


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
        key = attempt_key('login', username.strip().lower()[:MAX_USERNAME_LENGTH], request.remote_addr)
        # v0.26.0: the try is recorded first, then counted (store/accounts.py); a 6th try within 5 minutes is refused
        if not account_store.record_try(key, LOCKOUT_WINDOW, MAX_LOGIN_FAILURES):
            # 429 = "Too Many Requests"
            return render_template('login.html', error=f'Too many failed attempts. Please wait '
                                   f'{LOCKOUT_MINUTES} minutes and try again.'), 429
        user = User.query.filter_by(username=username).first()
        # v0.21.4 (DEF-62, audit A8): an unknown username checks a dummy hash too, so it takes as long as a
        # wrong password and the time taken can't tell anyone which usernames exist
        password_ok = check_password_hash(user.password_hash if user else DUMMY_PASSWORD_HASH, password)
        if user and password_ok and not user.is_active:
            # v0.27.0: switched off on the Users page. Said only after the right password, so it reveals nothing new
            return render_template('login.html', error='This account is switched off. Ask the shop\'s owner.'), 403
        plain = current_app.config.get('TEST_PLAIN_LOGIN')   # only automated tests of other features (DEC-030)
        if user and password_ok and password in DEMO_PASSWORDS and not (current_app.config.get('DEMO_MODE') or plain):
            # v0.28.0 (rule P3): the published demo passwords work only in demo mode
            return render_template('login.html', error='That is the demo\'s public password, so it only works in '
                                   'the demo. Use "Forgot your password?" to choose your own.'), 403
        if user and password_ok:
            account_store.forget_tries(key)   # a correct password resets the count
            # v0.28.0 (rule S13, DEC-030): a trusted browser skips the code; everyone else goes to /verify
            if plain or signin_store.trusted_device_for(user, trust_tokens()):
                return finish_login(user, page_after_login())
            if user.second_step != 'app' and not user.email:
                # Owner's decision 1 in DEC-030: the owner adds the address on Users; the next login confirms it
                return render_template('login.html', error='Your account has no email yet, so the login code can\'t '
                                       'be sent. Ask the shop\'s owner to add your email on the Users page.'), 403
            session.clear()   # nothing from a previous login on this browser is kept
            session['pending_login'] = {'user_id': user.id, 'at': time.time(), 'next': page_after_login()}
            if user.second_step != 'app':
                problem = email_code('login', user.email, user_id=user.id)
                if problem:
                    flash(f'The code could not be sent: {problem} You can type one of your backup codes instead.',
                          'danger')
            return redirect(url_for('accounts.verify'))
        return render_template('login.html', error='Invalid username or password')   # the try stays counted
    return render_template('login.html')


# ---------------- The second step: a code, unless the browser is trusted (v0.28.0, S13, DEC-030) ----------------
PENDING_SECONDS = 5 * 60    # "half logged in" lasts 5 minutes after the right password
TRUST_COOKIE = 'trusted'    # holds up to 10 random tokens; each counts only for the user it was made for
DEMO_PASSWORDS = {'admin123', 'cashier123'}   # published in the README for the demo (rule P3)


def finish_login(user, next_page):
    """The real login (v0.6.0, v0.20.3): a login row that log-out can end, then back to the page they asked for."""
    session.clear()                # nothing from a previous login on this browser is kept
    start_login_session(user)      # v0.20.3: a login that log-out can really end
    login_user(user)
    return redirect(next_page)     # v0.20.6 (DEF-06): back to the page they first asked for


def trust_tokens():
    """The tokens in this browser's trust cookie (random text without dots)."""
    return [t for t in request.cookies.get(TRUST_COOKIE, '').split('.') if 20 <= len(t) <= 64][:signin_store.MAX_TRUSTED_IN_COOKIE]


def device_label():
    """A short name for this browser, e.g. "Edge on Windows", from what the browser says about itself."""
    agent = request.headers.get('User-Agent', '')
    browser = next((name for key, name in [('Edg/', 'Edge'), ('OPR/', 'Opera'), ('Firefox/', 'Firefox'),
                                           ('Chrome/', 'Chrome'), ('Safari/', 'Safari')] if key in agent), 'A browser')
    system = next((name for key, name in [('Windows', 'Windows'), ('Android', 'Android'), ('iPhone', 'iPhone'),
                                          ('iPad', 'iPad'), ('Mac OS', 'Mac'), ('Linux', 'Linux')] if key in agent), '')
    return f'{browser} on {system}' if system else browser


def pending_user():
    """The person who typed the right password in the last 5 minutes, or None."""
    pending = session.get('pending_login') or {}
    if not pending or time.time() - pending.get('at', 0) > PENDING_SECONDS:
        return None
    user = db.session.get(User, pending.get('user_id'))
    return user if user is not None and user.is_active else None


def masked(address):
    """m•••@gmail.com: enough to recognise your own address, not enough to learn someone else's."""
    name, _, domain = (address or '').partition('@')
    return f'{name[:1]}•••@{domain}' if domain else ''


@bp.route('/verify', methods=['GET', 'POST'])
def verify():
    """Type the emailed code, the authenticator app's code, or a backup code. Tick "Trust this device" to skip
    this step on this browser for 30 days (7 for admins and the owner)."""
    user = pending_user()
    if user is None:
        session.pop('pending_login', None)
        flash('Please log in again (the 5 minutes to type the code have passed).', 'info')
        return redirect(url_for('accounts.login'))
    details = dict(user=user, email=masked(user.email), days=signin_store.trust_days(user),
                   backup_left=signin_store.backup_codes_left(user))
    if request.method == 'POST':
        key = attempt_key('verify', user.id)
        if not account_store.record_try(key, LOCKOUT_WINDOW, MAX_LOGIN_FAILURES):
            return render_template('verify.html', error=f'Too many wrong codes. Please wait {LOCKOUT_MINUTES} '
                                   f'minutes and try again.', **details), 429
        typed = request.form.get('code', '')
        letters = signin_store.tidy_backup_code(typed)
        ok, tries_left = False, None
        if len(letters) == 8:   # backup codes have 8 characters; login codes 6 digits
            ok = signin_store.use_backup_code(user, typed)
        elif user.second_step == 'app':
            ok = signin_store.check_app_code(user, typed)
        else:
            row, tries_left = user_store.check_code('login', user.email, typed)
            ok = row is not None and row.user_id == user.id
            if ok:
                user_store.confirm_email_by_login(user)   # owner's decision 1: the code proves an added address
        if not ok:
            error = code_problem(tries_left) if tries_left is not None else 'That code is not right.'
            return render_template('verify.html', error=error, **details)
        account_store.forget_tries(key)
        next_page = session['pending_login'].get('next') or url_for('catalog.products')
        trust = request.form.get('trust') == '1'
        response = make_response(finish_login(user, next_page))
        if trust:
            tokens = [t for t in trust_tokens()][-(signin_store.MAX_TRUSTED_IN_COOKIE - 1):]
            tokens.append(signin_store.trust_device(user, device_label()))
            response.set_cookie(TRUST_COOKIE, '.'.join(tokens), max_age=signin_store.trust_days(user) * 86400,
                                httponly=True, samesite='Lax', secure=request.is_secure)
        return response
    return render_template('verify.html', **details)


@bp.route('/verify/resend', methods=['POST'])
def verify_resend():
    """A new emailed code (one a minute, 5 an hour, as in v0.27.0)."""
    user = pending_user()
    if user is None:
        return redirect(url_for('accounts.verify'))
    if user.second_step != 'app':
        problem = email_code('login', user.email, user_id=user.id)
        flash(problem or f'A new code was sent to {masked(user.email)}.', 'danger' if problem else 'info')
    return redirect(url_for('accounts.verify'))


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
    # v0.28.0: the trusted devices and how many backup codes are left, for the sign-in cards
    return render_template('profile.html', devices=signin_store.devices(current_user),
                           backup_left=signin_store.backup_codes_left(current_user))


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


def current_password_ok(current):
    """Check the current password with the 5-tries limit (v0.26.0, DEF-69, audit A7, DEC-028), counted per user, so
    someone using a stolen login can't guess it faster than on the login page. Returns None or a message.
    v0.27.0: shared by Change password, Choose a new password and changing the email on Profile."""
    key = attempt_key('password', current_user.id)
    if not account_store.record_try(key, LOCKOUT_WINDOW, MAX_LOGIN_FAILURES):
        return (f'Too many wrong current passwords. Please wait {LOCKOUT_MINUTES} minutes and try again. '
                'Nothing was changed.')
    if not check_password_hash(current_user.password_hash, current):
        return 'Current password is wrong. Nothing was changed.'   # the try stays counted
    account_store.forget_tries(key)   # the right current password resets the count, as on the login page
    return None


def new_password_problem(new, confirm, username, current=None):
    """The rules for a new password (v0.13.5), or None if it is fine. Also used by signup and Forgot password."""
    if new != confirm:
        return 'The new passwords do not match.'
    if new.lower() == username.lower():
        return "Your password can't be the same as your username."
    if len(new) < MIN_PASSWORD_LENGTH:
        return f'The new password must be at least {MIN_PASSWORD_LENGTH} characters long.'
    if current is not None and new == current:
        return 'The new password is the same as the current one.'
    return None


def save_new_password(new):
    """v0.20.3 (DEF-51): every login of this user ends, and this browser gets a new one. Returns the message."""
    token, ended = account_store.change_password(current_user, generate_password_hash(new),   # stored scrambled
                                                 session.get('login_token', ''), IDLE_TIMEOUT)
    session['login_token'] = token
    others = f'{ended} other device(s) logged in as you were logged out.' if ended else 'Other devices logged in as you would have been logged out.'
    return 'Password changed. Use the new one next time you log in. ' + others


@bp.route('/profile/password', methods=['POST'])
@login_required
def change_password():
    """Lets a user replace a default password like admin123 with their own."""
    current = request.form.get('current_password', '')
    new = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')
    problem = current_password_ok(current) or new_password_problem(new, confirm, current_user.username, current)
    if problem:
        flash(problem, 'danger')
    else:
        flash(save_new_password(new), 'success')
    return redirect(url_for('accounts.profile'))


# ---------------- Choose a new password (v0.27.0, audit A5, DEC-029) ----------------
@bp.route('/password/new', methods=['GET', 'POST'])
@login_required
def choose_password():
    """After "Require a new password" on Users: the person must choose one before using anything else.
    The current password is asked too, so a stolen login can't pick a new password without knowing the old one."""
    if not current_user.must_change_password:
        return redirect(url_for('reports.home'))
    if request.method == 'POST':
        current = request.form.get('current_password', '')
        new = request.form.get('new_password', '')
        problem = (current_password_ok(current)
                   or new_password_problem(new, request.form.get('confirm_password', ''), current_user.username, current))
        if problem:
            return render_template('choose_password.html', error=problem)
        message = save_new_password(new)
        user_store.clear_must_change(current_user)
        flash(message, 'success')
        return redirect(url_for('reports.home'))
    return render_template('choose_password.html')


# ---------------- Emails with links and codes (v0.27.0, DEC-029) ----------------
def link_to(endpoint, **values):
    """A full web address for an email. When the sender uses 127.0.0.1 on a setup that allows other devices, the
    link uses this computer's network address instead, so it also opens on a cashier's phone."""
    url = url_for(endpoint, _external=True, **values)
    host = request.host.split(':')[0]
    if host in ('127.0.0.1', 'localhost') and current_app.config.get('SERVER_HOST') == '0.0.0.0':
        lan = network_address()
        if lan:
            url = url.replace(f'//{host}', f'//{lan}', 1)
    return url


CODE_EMAILS = {   # purpose: (subject, what the code is for)
    'login': ('Your login code for {shop}', 'log in to your {shop} account'),   # v0.28.0
    'signup': ('Your code to join {shop}', 'finish joining {shop}'),
    'reset': ('Your code to choose a new password', 'choose a new password for your {shop} account'),
    'email': ('Your code to confirm this email address', 'confirm this email address for your {shop} account'),
}


def email_code(purpose, address, user_id=None, invitation_id=None):
    """Send a new 6-digit code (plan §2.4: what it is for, when, from which computer). Returns None or a problem
    to show: the one-a-minute and 5-an-hour limits, or the mail error."""
    problem = user_store.may_send_code(purpose, address)
    if problem:
        return problem
    code = user_store.new_code(purpose, address, user_id=user_id, invitation_id=invitation_id)
    shop = shop_profile().name
    subject, what = (text.format(shop=shop) for text in CODE_EMAILS[purpose])
    body = (f'Your code is {code[:3]} {code[3:]}\n\n'
            f'Type it to {what}. It works for {user_store.CODE_MINUTES} minutes, once.\n\n'
            f'Asked for on {shop_now():%d %b %Y at %I:%M %p} from the computer {request.remote_addr}.\n'
            f'If this wasn\'t you, ignore this email. If it keeps happening, tell the shop\'s owner'
            f'{" and change your password" if purpose == "reset" else ""}.\n')
    return send_mail(address, subject, body, sender_name=shop)


def code_problem(tries_left):
    """The message for a wrong or used-up code."""
    if tries_left:
        return f'That code is not right. {tries_left} {"try" if tries_left == 1 else "tries"} left.'
    return 'That code no longer works (10 minutes passed, it was used, or 5 wrong tries). Ask for a new code.'


# ---------------- Forgot password (v0.27.0, DEC-029; public pages, rule S1) ----------------
FORGOT_PER_HOUR = 10   # requests per computer per hour


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Ask for the email, and answer the SAME way whether or not an account uses it, so a stranger can't find out
    which addresses belong to the staff. Only a switched-on account with a confirmed email gets a code."""
    if request.method == 'POST':
        _, not_set_up = mail_settings()
        if not_set_up:   # true for every address alike, so saying it reveals nothing about accounts
            return render_template('forgot_password.html', error='Email isn\'t set up in this shop yet, so a code '
                                   'can\'t be sent. Ask the shop\'s owner to set a new password for you.')
        address = check_email_address(request.form.get('email', ''))
        if address is None:
            return render_template('forgot_password.html', error='Type your email address, like name@example.com.')
        if not account_store.record_try(keyed_hash('forgot', request.remote_addr), timedelta(hours=1), FORGOT_PER_HOUR):
            return render_template('forgot_password.html', error='Too many requests from this computer. '
                                   'Please try again in an hour.'), 429
        user = user_store.active_user_with_email(address)
        if user:
            problem = email_code('reset', address, user_id=user.id)
            if problem:
                current_app.logger.warning('Forgot password: no code sent (%s)', problem)   # not shown: same answer
        session['reset_email'] = address.lower()
        flash(f'If an account uses {address}, we sent it a 6-digit code. It works for 10 minutes.', 'info')
        return redirect(url_for('accounts.forgot_code'))
    return render_template('forgot_password.html')


@bp.route('/forgot-password/code', methods=['GET', 'POST'])
def forgot_code():
    """The emailed code and the new password, twice. Success ends every login of that account."""
    address = session.get('reset_email')
    if not address:
        return redirect(url_for('accounts.forgot_password'))
    if request.method == 'POST':
        new = request.form.get('new_password', '')
        # The rules that don't depend on the account first, so a typo doesn't use up the code
        problem = new_password_problem(new, request.form.get('confirm_password', ''), username='')
        if problem:
            return render_template('forgot_code.html', email=address, error=problem)
        row, tries_left = user_store.check_code('reset', address, request.form.get('code', ''))
        user = db.session.get(User, row.user_id) if row else None
        if user is None or not user.is_active:
            return render_template('forgot_code.html', email=address, error=code_problem(tries_left if not row else 0))
        if new.lower() == user.username.lower():
            # Only checked after the right code, so it can't be used to find out a username. The code is used up.
            return render_template('forgot_code.html', email=address, error="Your password can't be the same as "
                                   "your username. Ask for a new code and try again.")
        user_store.reset_password(user, generate_password_hash(new))
        session.pop('reset_email', None)
        flash('Your new password is saved. Log in with it. Every device that was logged in as you was logged out.',
              'success')
        return redirect(url_for('accounts.login'))
    return render_template('forgot_code.html', email=address)


# ---------------- The email on Profile (v0.27.0, DEC-029) ----------------
# Cashiers and admins may change their email: current password, then a code sent to the NEW address proves it.
# The owner's email is fixed (rule S12); the owner can only confirm it with a code.

@bp.route('/profile/email', methods=['POST'])
@login_required
def change_email():
    if current_user.is_owner:
        if not current_user.email:
            flash('The owner\'s email is set by "python setup_shop.py" on the shop\'s computer.', 'danger')
            return redirect(url_for('accounts.profile'))
        address = current_user.email
    else:
        address = check_email_address(request.form.get('email', ''))
        if address is None:
            flash('Type the new email address, like name@example.com.', 'danger')
            return redirect(url_for('accounts.profile'))
        problem = current_password_ok(request.form.get('current_password', ''))
        if problem:
            flash(problem, 'danger')
            return redirect(url_for('accounts.profile'))
        if address.lower() != (current_user.email or '') and user_store.email_taken(address):
            flash('Another account already uses that email address.', 'danger')
            return redirect(url_for('accounts.profile'))
    problem = email_code('email', address, user_id=current_user.id)
    if problem:
        flash(problem, 'danger')
    else:
        session['pending_email'] = address.lower()
        flash(f'We sent a 6-digit code to {address}. Type it below to confirm the address.', 'info')
    return redirect(url_for('accounts.profile') + '#email')


@bp.route('/profile/email/confirm', methods=['POST'])
@login_required
def confirm_email():
    address = session.get('pending_email')
    if not address:
        return redirect(url_for('accounts.profile'))
    row, tries_left = user_store.check_code('email', address, request.form.get('code', ''))
    if row is None or row.user_id != current_user.id:
        flash(code_problem(tries_left if row is None else 0), 'danger')
        return redirect(url_for('accounts.profile') + '#email')
    session.pop('pending_email', None)
    if current_user.is_owner:
        user_store.confirm_email(current_user)
    elif user_store.email_taken(address) and address != (current_user.email or ''):
        flash('Another account started using that email address a moment ago. Nothing was changed.', 'danger')
        return redirect(url_for('accounts.profile') + '#email')
    else:
        user_store.set_email(current_user, address)
    flash(f'Email confirmed: {address}. It can now be used if you forget your password.', 'success')
    return redirect(url_for('accounts.profile') + '#email')


# ---------------- Trusted devices, Log out everywhere, backup codes (v0.28.0, S13, DEC-030) ----------------
def no_store(html):
    """A page the browser must not keep (backup codes, the authenticator key): Cache-Control no-store (DEC-017)."""
    response = make_response(html)
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.route('/profile/devices/<int:device_id>/remove', methods=['POST'])
@login_required
def remove_device(device_id):
    if not signin_store.remove_device(current_user, device_id):
        abort(404)   # not one of this person's devices
    flash('That device is no longer trusted: it will ask for a code at the next login.', 'success')
    return redirect(url_for('accounts.profile') + '#devices')


@bp.route('/profile/logout-everywhere', methods=['POST'])
@login_required
def logout_everywhere():
    """Every login of this person ends, here too, and no device stays trusted (S13)."""
    signin_store.logout_everywhere(current_user)
    logout_user()
    session.clear()
    response = make_response(redirect(url_for('accounts.login')))
    flash('You were logged out everywhere, and no device is trusted any more.', 'success')
    return response


@bp.route('/profile/backup-codes', methods=['POST'])
@login_required
def backup_codes():
    """New backup codes, shown once. The current password is asked, with the A7 limit."""
    problem = current_password_ok(request.form.get('current_password', ''))
    if problem:
        flash(problem, 'danger')
        return redirect(url_for('accounts.profile') + '#backup')
    return no_store(render_template('backup_codes.html', codes=signin_store.new_backup_codes(current_user)))


# ---------------- The authenticator app (v0.28.0, DEC-017) ----------------
def tell_method_changed(user, method):
    """S13: turning the app on or off emails the person, so a change they didn't make is noticed."""
    if user.email:
        shop = shop_profile().name
        send_mail(user.email, 'Your sign-in method changed',
                  f'Your {shop} account now uses {method} for the login code.\n\n'
                  f'Changed on {shop_now():%d %b %Y at %I:%M %p} from the computer {request.remote_addr}.\n'
                  f'If this wasn\'t you, tell the shop\'s owner at once and change your password.\n',
                  sender_name=shop)


def authenticator_page(key, error=None):
    shop = shop_profile().name
    link = totp.setup_link(key, current_user.username, shop)
    spaced = ' '.join(key[i:i + 4] for i in range(0, len(key), 4))
    return no_store(render_template('authenticator.html', qr=totp.qr_image(link), key=spaced, error=error))


@bp.route('/profile/authenticator', methods=['POST'])
@login_required
def authenticator_start():
    """Step 1: the password again, then a new key as a QR code and as text."""
    problem = current_password_ok(request.form.get('current_password', ''))
    if problem:
        flash(problem, 'danger')
        return redirect(url_for('accounts.profile') + '#method')
    return authenticator_page(signin_store.start_app(current_user))


@bp.route('/profile/authenticator/confirm', methods=['POST'])
@login_required
def authenticator_confirm():
    """Step 2: the app's current code proves the scan worked; only then does the method change."""
    key = signin_store.pending_key(current_user)
    if key is None:
        return redirect(url_for('accounts.profile') + '#method')
    if not account_store.record_try(attempt_key('verify', current_user.id), LOCKOUT_WINDOW, MAX_LOGIN_FAILURES):
        return authenticator_page(key, f'Too many wrong codes. Please wait {LOCKOUT_MINUTES} minutes and try again.')
    if not signin_store.finish_app(current_user, request.form.get('code', '')):
        return authenticator_page(key, 'That code is not right. Check the app shows this shop, and the phone\'s time.')
    tell_method_changed(current_user, 'an authenticator app')
    return no_store(render_template('backup_codes.html', codes=signin_store.new_backup_codes(current_user),
                                    app_turned_on=True))


@bp.route('/profile/authenticator/off', methods=['POST'])
@login_required
def authenticator_off():
    """Back to emailed codes: the password AND a current app code or a backup code (S13)."""
    if current_user.second_step != 'app':
        return redirect(url_for('accounts.profile'))
    problem = current_password_ok(request.form.get('current_password', ''))
    if problem is None:
        typed = request.form.get('code', '')
        if not (signin_store.check_app_code(current_user, typed) or signin_store.use_backup_code(current_user, typed)):
            problem = 'That code is not right. Type the code your app shows now, or one of your backup codes.'
    if problem:
        flash(problem, 'danger')
        return redirect(url_for('accounts.profile') + '#method')
    if not current_user.email:
        flash('Add an email first: without one, the login code couldn\'t be sent.', 'danger')
        return redirect(url_for('accounts.profile') + '#email')
    signin_store.back_to_email(current_user, by=current_user.id)
    tell_method_changed(current_user, 'a code sent by email')
    flash('Your login code now comes by email again.', 'success')
    return redirect(url_for('accounts.profile') + '#method')
