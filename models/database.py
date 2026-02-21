"""Database initialization and configuration"""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

# Initialize SQLAlchemy
db = SQLAlchemy()


# Enable SQLite foreign key constraints
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Enable foreign key constraints for SQLite"""
    if isinstance(dbapi_conn, sqlite3.Connection):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def init_db(app):
    """Initialize database"""
    db.init_app(app)

    with app.app_context():
        # Create all tables
        db.create_all()
        print("Database initialized successfully!")


def reset_db(app):
    """Reset database (drop all tables and recreate)"""
    db.init_app(app)

    with app.app_context():
        db.drop_all()
        db.create_all()
        print("Database reset successfully!")
