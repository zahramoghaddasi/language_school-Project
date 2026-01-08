from functools import wraps
from flask import session, redirect, url_for
import os
from dotenv import load_dotenv

load_dotenv()

# اطلاعات ادمین پیشفرض
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

def login_required(f):
    """دکوراتور برای صفحاتی که نیاز به ورود دارند"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def check_credentials(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD

def logout_user():
    session.clear() 