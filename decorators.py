from functools import wraps
from flask import abort
from flask_login import current_user


def roles_required(*roles):
    """Restrict a route to specific roles (e.g. businessman, store_manager)."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def permission_required(module, action):
    """Restrict a route based on the Access Control Matrix (models.User.can)."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.can(module, action):
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator
