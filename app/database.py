"""
Flask-SQLAlchemy Database Setup
Shared between Flask and FastAPI
"""
from contextlib import contextmanager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Initialize Flask-SQLAlchemy
db = SQLAlchemy()
migrate = Migrate()

# Global reference to Flask app (set during initialization)
_flask_app = None


def init_db(app):
    """Initialize database with Flask app"""
    global _flask_app
    _flask_app = app
    db.init_app(app)
    migrate.init_app(app, db)
    return db


def get_flask_app():
    """Get the Flask app instance"""
    global _flask_app
    return _flask_app


@contextmanager
def app_context():
    """
    Context manager for Flask app context.
    Use this in FastAPI routes to access Flask-SQLAlchemy.
    
    Example:
        with app_context():
            user = User.query.filter_by(email=email).first()
    """
    app = get_flask_app()
    if app is None:
        raise RuntimeError("Flask app not initialized. Call init_db first.")
    with app.app_context():
        yield


def get_db_session():
    """
    Get database session for use in FastAPI
    This allows FastAPI to use Flask-SQLAlchemy models
    """
    return db.session


def create_all_tables(app):
    """Create all database tables"""
    with app.app_context():
        db.create_all()
        print("✅ Database tables created successfully!")


def drop_all_tables(app):
    """Drop all database tables (use with caution!)"""
    with app.app_context():
        db.drop_all()
        print("⚠️ All database tables dropped!")
