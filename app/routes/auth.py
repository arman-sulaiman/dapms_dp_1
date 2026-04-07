from flask import Blueprint, render_template, request, redirect, session, url_for, flash

from app.core.security import load_user, login_required
from app.db import get_db
from app.managers import AuthManager

bp = Blueprint('auth', __name__)


@bp.before_app_request
def before():
    load_user()


@bp.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in, redirect to dashboard
    if session.get('user_id') and session.get('role'):
        return redirect(url_for(f"{session.get('role')}.dashboard"))

    if request.method == 'POST':
        manager = AuthManager(get_db())
        user = manager.authenticate(
            request.form.get('email', ''),
            request.form.get('password', '')
        )

        if user:
            session['user_id'] = user.id
            session['role'] = user.role
            return redirect(url_for(user.dashboard_endpoint))

        flash('Invalid login', 'error')

    return render_template('auth/login.html')


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    manager = AuthManager(get_db())
    if request.method == 'POST':
        manager.update_profile(
            session['user_id'],
            request.form.get('name', ''),
            request.form.get('department', '')
        )
        flash('Profile updated', 'success')
        return redirect(url_for('auth.profile'))

    profile = manager.user_profile(session['user_id'])
    return render_template('auth/profile.html', profile=profile)


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        ok, msg = AuthManager(get_db()).request_password_reset(
            request.form.get('email', ''),
            request.form.get('note', '')
        )
        flash(msg, 'success' if ok else 'error')
        return redirect(url_for('auth.forgot_password'))

    return render_template('auth/forgot_password.html')


@bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if new_password != confirm_password:
            flash('New password and confirm password do not match.', 'error')
            return redirect(url_for('auth.change_password'))

        ok, message = AuthManager(get_db()).change_password(
            session.get('user_id'),
            request.form.get('current_password', ''),
            new_password
        )
        flash(message, 'success' if ok else 'error')

        if ok:
            return redirect(url_for(f"{session.get('role')}.dashboard"))

    return render_template('auth/change_password.html')


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))