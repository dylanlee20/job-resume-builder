"""Minimal Flask+SQLAlchemy app for migration scripts.

Importing the full app.py runs create_app() at import time (scheduler, blueprints,
eager DB connect). Migrations only need a DB session, so build a bare app the
same way scraper_runner does — same Config, same DATABASE_URL (and therefore the
same mysqlclient/MySQLdb driver the live app uses, which accepts the prod URL's
ssl-mode parameter).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask

from config import Config
from models.database import db
import models  # noqa: F401  (registers every model on db's metadata)


def create_db_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app
