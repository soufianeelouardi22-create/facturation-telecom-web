from functools import wraps
from flask import redirect, url_for, abort
from flask_login import current_user


def role_required(*roles):
    """Décorateur — refuse l'accès si le rôle courant n'est pas dans la liste."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator
