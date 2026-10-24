"""The Users page, invitations, signing up from an invitation, and the audit log (v0.27.0, F24, DEC-029).

Who may do what (rules S12, S15): every admin may open Users. The owner may invite cashiers and admins, change roles,
let admins invite, and switch any account but their own off or on. An admin may switch cashiers off or on, and
invite cashiers only if the owner allowed it. Nobody can change the owner here. Anything else gets 403, even when
the button is hidden. Every change is written in the audit log by store/users.py.
"""
import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from flask_login import login_required, current_user, login_user
from werkzeug.security import generate_password_hash
from common import admin_required, find_by_id
from models import User, Invitation, utc_now
from mail import mail_settings, send_mail, check_email_address
from store import users as user_store
from store import audit as audit_store
from store import signin as signin_store
from store.shop import shop_profile
from blueprints.accounts import (link_to, email_code, code_problem, new_password_problem, start_login_session,
                                 MAX_USERNAME_LENGTH, tell_method_changed)

bp = Blueprint('users', __name__)

ROLE_NAMES = {'owner': 'Owner', 'admin': 'Admin', 'cashier': 'Cashier'}
USERNAME_PATTERN = re.compile(r'^[A-Za-z0-9._-]{3,50}$')   # letters, numbers, dot, dash, underscore; 3 to 50


# ---------------- Who may do what (S15) ----------------
def may_manage(user):
    """Switch off or on, require a new password: never the owner or yourself; admins only manage cashiers."""
    if user.is_owner or user.id == current_user.id:
        return False
    return current_user.is_owner or user.role == 'cashier'


def roles_i_may_invite():
    if current_user.is_owner:
        return ['cashier', 'admin']
    return ['cashier'] if current_user.can_invite else []


def may_handle_invitation(invitation):
    return current_user.is_owner or invitation.invited_by == current_user.id


def target_user(user_id):
    """The account a Users button acts on, or 404."""
    return find_by_id(User, user_id) or abort(404)


# ---------------- The Users page ----------------
@bp.route('/admin/users')
@login_required
@admin_required
def users():
    _, mail_problem = mail_settings()
    return render_template('users.html', people=user_store.all_users(), invitations=user_store.invitations(),
                           roles=roles_i_may_invite(), mail_problem=mail_problem, ROLE_NAMES=ROLE_NAMES,
                           may_manage=may_manage, may_handle_invitation=may_handle_invitation,
                           now=utc_now())


def send_invitation(invitation, token):
    """Email the link. Returns None or the mail problem."""
    shop = shop_profile().name
    role = ROLE_NAMES[invitation.role].lower()
    body = (f'{current_user.username} invited you to join {shop} as {"an" if role == "admin" else "a"} {role}.\n\n'
            f'Open this link within {user_store.INVITATION_HOURS} hours to choose your username and password:\n'
            f'{link_to("users.signup", token=token)}\n\n'
            f'The link works once. If you weren\'t expecting this email, ignore it.\n')
    return send_mail(invitation.email, f'You\'re invited to {shop}', body, sender_name=shop)


@bp.route('/admin/users/invite', methods=['POST'])
@login_required
@admin_required
def invite():
    role = request.form.get('role', 'cashier')
    if role not in roles_i_may_invite():
        abort(403)   # an admin without "may invite", or an admin trying to invite an admin
    address = check_email_address(request.form.get('email', ''))
    _, mail_problem = mail_settings()
    if mail_problem:
        flash(mail_problem, 'danger')
    elif address is None:
        flash('Type the person\'s own email address, like name@example.com.', 'danger')
    elif user_store.email_taken(address):
        flash(f'{address} already has an account.', 'danger')
    elif user_store.open_invitation_for(address):
        flash(f'{address} has already been invited. Use "Send again" below if the email went missing.', 'danger')
    else:
        invitation, token = user_store.create_invitation(address.lower(), role, by=current_user.id)
        problem = send_invitation(invitation, token)
        if problem:
            flash(f'The invitation was saved, but the email could not be sent: {problem} '
                  f'Use "Send again" when it works.', 'danger')
        else:
            flash(f'Invitation sent to {address}. The link works for {user_store.INVITATION_HOURS} hours.', 'success')
    return redirect(url_for('users.users'))


@bp.route('/admin/invitations/<int:invitation_id>/resend', methods=['POST'])
@login_required
@admin_required
def resend_invitation(invitation_id):
    invitation = find_by_id(Invitation, invitation_id) or abort(404)
    if not may_handle_invitation(invitation) or invitation.role not in roles_i_may_invite():
        abort(403)
    if invitation.used_at or invitation.cancelled_at:
        abort(404)
    _, mail_problem = mail_settings()
    if mail_problem:
        flash(mail_problem, 'danger')
        return redirect(url_for('users.users'))
    token = user_store.renew_invitation(invitation, by=current_user.id)
    problem = send_invitation(invitation, token)
    flash(problem or f'A new link was sent to {invitation.email}; the old one no longer works.',
          'danger' if problem else 'success')
    return redirect(url_for('users.users'))


@bp.route('/admin/invitations/<int:invitation_id>/cancel', methods=['POST'])
@login_required
@admin_required
def cancel_invitation(invitation_id):
    invitation = find_by_id(Invitation, invitation_id) or abort(404)
    if not may_handle_invitation(invitation):
        abort(403)
    if not invitation.used_at and not invitation.cancelled_at:
        user_store.cancel_invitation(invitation, by=current_user.id)
        flash(f'The invitation to {invitation.email} was cancelled; its link no longer works.', 'success')
    return redirect(url_for('users.users'))


@bp.route('/admin/users/<int:user_id>/role', methods=['POST'])
@login_required
@admin_required
def change_role(user_id):
    """Owner only: cashier <-> admin. The owner role itself is never given or taken here (S12)."""
    user = target_user(user_id)
    role = request.form.get('role')
    if not current_user.is_owner or user.is_owner or role not in ('admin', 'cashier'):
        abort(403)
    if role != user.role:
        user_store.set_role(user, role, by=current_user.id)
        flash(f'{user.username} is now {"an admin" if role == "admin" else "a cashier"}.', 'success')
    return redirect(url_for('users.users'))


@bp.route('/admin/users/<int:user_id>/active', methods=['POST'])
@login_required
@admin_required
def switch_active(user_id):
    """Switch an account off (it can't log in; every login ends now) or on again. Never deleted."""
    user = target_user(user_id)
    if not may_manage(user):
        abort(403)
    active = request.form.get('active') == '1'
    if active != user.is_active:
        user_store.set_active(user, active, by=current_user.id)
        flash(f'{user.username} is switched {"on again" if active else "off and was logged out everywhere"}.', 'success')
    return redirect(url_for('users.users'))


@bp.route('/admin/users/<int:user_id>/require-password', methods=['POST'])
@login_required
@admin_required
def require_password(user_id):
    user = target_user(user_id)
    if not may_manage(user):
        abort(403)
    user_store.require_new_password(user, by=current_user.id)
    flash(f'{user.username} must choose a new password on their next page.', 'success')
    return redirect(url_for('users.users'))


@bp.route('/admin/users/<int:user_id>/may-invite', methods=['POST'])
@login_required
@admin_required
def may_invite(user_id):
    """Owner only: let an admin invite cashiers (DEC-003)."""
    user = target_user(user_id)
    if not current_user.is_owner or user.role != 'admin':
        abort(403)
    allowed = request.form.get('allowed') == '1'
    if allowed != user.can_invite:
        user_store.set_can_invite(user, allowed, by=current_user.id)
        flash(f'{user.username} {"may" if allowed else "may no longer"} invite cashiers.', 'success')
    return redirect(url_for('users.users'))


@bp.route('/admin/users/<int:user_id>/email', methods=['POST'])
@login_required
@admin_required
def add_email(user_id):
    """v0.28.0 (owner's decision 1 in DEC-030): the address of an account made before v0.27.0, typed by the owner (or an
    admin, for a cashier). That person's next login sends the code there, which confirms it."""
    user = target_user(user_id)
    if not may_manage(user) or user.email:
        abort(403)
    address = check_email_address(request.form.get('email', ''))
    if address is None:
        flash("Type the person's own email address, like name@example.com.", 'danger')
    elif user_store.email_taken(address):
        flash(f'{address} is already used by another account.', 'danger')
    else:
        user_store.add_email_for(user, address, by=current_user.id)
        flash(f"{user.username}'s next login sends the code to {address}, which confirms it.", 'success')
    return redirect(url_for('users.users'))


@bp.route('/admin/users/<int:user_id>/reset-second-step', methods=['POST'])
@login_required
@admin_required
def reset_second_step(user_id):
    """A lost phone (DEC-017): back to emailed codes. Logged and emailed. Never for the owner (may_manage)."""
    user = target_user(user_id)
    if not may_manage(user) or user.second_step != 'app' or not user.email:
        abort(403)
    signin_store.back_to_email(user, by=current_user.id)
    tell_method_changed(user, 'a code sent by email (reset by ' + current_user.username + ')')
    flash(f'{user.username} gets the login code by email again.', 'success')
    return redirect(url_for('users.users'))


# ---------------- Signing up from an invitation (public page, rule S1) ----------------
def username_problem(username):
    if not USERNAME_PATTERN.match(username):
        return (f'Choose a username of 3 to {MAX_USERNAME_LENGTH} letters or numbers '
                f'(dots, dashes and underscores are fine, no spaces).')
    if user_store.username_taken(username):
        return 'That username is taken. Choose another one.'
    return None


@bp.route('/signup/<token>', methods=['GET', 'POST'])
def signup(token):
    """Step 1: choose a username and password. Step 2: the code sent to the invited address. Then the account exists
    with the role the inviter chose, and the person is logged in. Nothing typed here can change the role (S12)."""
    invitation = user_store.invitation_by_token(token)
    if invitation is None:
        return render_template('signup.html', closed=True), 404
    details = dict(invitation=invitation, role=ROLE_NAMES[invitation.role], shop=shop_profile().name)
    if request.method == 'POST' and request.form.get('step') == 'code':
        if not invitation.pending_username:
            return redirect(url_for('users.signup', token=token))
        if request.form.get('again'):
            problem = email_code('signup', invitation.email, invitation_id=invitation.id)
            flash(problem or f'A new code was sent to {invitation.email}.', 'danger' if problem else 'info')
            return render_template('signup.html', step='code', **details)
        row, tries_left = user_store.check_code('signup', invitation.email, request.form.get('code', ''))
        if row is None or row.invitation_id != invitation.id:
            return render_template('signup.html', step='code', error=code_problem(tries_left if row is None else 0),
                                   **details)
        user = user_store.finish_signup(invitation)
        if user is None:
            return render_template('signup.html', step='details', error='That username was taken a moment ago, or '
                                   'the invitation was just used. Choose another username.', **details)
        session.clear()   # nothing from an earlier login on this browser is kept
        start_login_session(user)
        login_user(user)
        flash(f'Welcome, {user.username}! Your account is ready.', 'success')
        return redirect(url_for('reports.home'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        problem = (username_problem(username)
                   or new_password_problem(password, request.form.get('confirm_password', ''), username))
        if problem:
            return render_template('signup.html', step='details', error=problem, username=username, **details)
        user_store.save_pending_signup(invitation, username, generate_password_hash(password))
        problem = email_code('signup', invitation.email, invitation_id=invitation.id)
        if problem:
            return render_template('signup.html', step='code', error=problem, **details)
        return render_template('signup.html', step='code', **details)
    return render_template('signup.html', step='details', **details)


# ---------------- The audit log (admins) ----------------
AREAS = {'product': 'Products', 'option': 'Servings & add-ons', 'ingredient': 'Ingredients', 'recipe': 'Recipes',
         'shop': 'Shop details', 'user': 'Accounts'}


@bp.route('/admin/audit')
@login_required
@admin_required
def audit():
    page = max(1, min(request.args.get('page', 1, type=int), 100_000))
    who = request.args.get('who', type=int)
    area = request.args.get('area') if request.args.get('area') in AREAS else None
    lines, older = audit_store.entries(page=page, user_id=who, area=area)
    return render_template('audit.html', lines=lines, older=older, page=page, who=who, area=area, AREAS=AREAS,
                           people=audit_store.people(), details_of=audit_store.details_of)
