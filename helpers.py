from functools import wraps
from flask import session, request, redirect, url_for


# https://flask.palletsprojects.com/en/1.1.x/patterns/viewdecorators/

# TODO in case of user interaction, redirect to a login page

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for('admin_page'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("superuser") is None:
            return redirect(url_for('admin_page'))
        return f(*args, **kwargs)
    return decorated_function
