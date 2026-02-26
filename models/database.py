"""Database initialization and configuration"""
import logging

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine
import sqlite3

logger = logging.getLogger(__name__)

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


def _migrate_missing_columns(engine):
    """Add any columns defined in models but missing from the database.

    SQLAlchemy's create_all() only creates new tables — it never adds
    columns to existing tables.  This function bridges the gap for SQLite
    (which supports ALTER TABLE ADD COLUMN but not IF NOT EXISTS).
    """
    inspector = inspect(engine)
    metadata = db.metadata

    for table_name, table in metadata.tables.items():
        if not inspector.has_table(table_name):
            continue  # create_all() will handle brand-new tables

        existing_cols = {col['name'] for col in inspector.get_columns(table_name)}

        for column in table.columns:
            if column.name in existing_cols:
                continue

            # Build the column type string for ALTER TABLE
            col_type = column.type.compile(engine.dialect)
            sql = f'ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}'
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
            logger.info("Migration: added column %s.%s (%s)", table_name, column.name, col_type)


def init_db(app):
    """Initialize database — creates tables and adds missing columns."""
    db.init_app(app)

    with app.app_context():
        # Create any brand-new tables
        db.create_all()
        # Add columns that models define but the DB is missing
        _migrate_missing_columns(db.engine)
        print("Database initialized successfully!")


def reset_db(app):
    """Reset database (drop all tables and recreate)"""
    db.init_app(app)

    with app.app_context():
        db.drop_all()
        db.create_all()
        print("Database reset successfully!")
