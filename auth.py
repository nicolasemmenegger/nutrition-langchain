from functools import wraps
from flask import session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User


def login_required(f):
    """Decorator to require login for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('views.login'))
        return f(*args, **kwargs)
    return decorated_function


def hash_password(password: str) -> str:
    """Hash a password using Werkzeug's security functions"""
    return generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a password against its hash"""
    return check_password_hash(password_hash, password)


def create_user(username: str, email: str, password: str) -> User:
    """Create a new user with hashed password"""
    password_hash = hash_password(password)
    user = User(username=username, email=email, password_hash=password_hash)
    db.session.add(user)
    db.session.commit()
    return user


def authenticate_user(username: str, password: str) -> User:
    """Authenticate a user by username and password"""
    user = User.query.filter_by(username=username).first()
    if user and verify_password(user.password_hash, password):
        return user
    return None

def get_user_by_id(user_id: int) -> User:
    """Get a user by their ID"""
    return User.query.get(user_id)


def get_user_by_username(username: str) -> User:
    """Get a user by their username"""
    return User.query.filter_by(username=username).first()


def get_user_by_email(email: str) -> User:
    """Get a user by their email"""
    return User.query.filter_by(email=email).first() 