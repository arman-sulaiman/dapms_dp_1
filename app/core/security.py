from functools import wraps
from flask import session, redirect, url_for, g
from app.db import get_db


def load_user():
    user_id = session.get('user_id')
    if not user_id:
        g.user = None
        return
    g.user = get_db().execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        return view(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get('role') not in roles:
                return redirect(url_for('auth.login'))
            return view(*args, **kwargs)
        return wrapped
    return decorator
