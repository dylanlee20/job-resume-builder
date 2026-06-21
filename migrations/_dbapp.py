"""Minimal Flask+SQLAlchemy app for migration scripts.

Importing the full app.py runs create_app() at import time (scheduler, blueprints,
eager DB connect) and assumes the MySQLdb driver. Migrations only need a DB
session, so build a bare app the same way scraper_runner does. The DB URL is
normalised to the pure-Python pymysql driver so it works in the deploy venv
without mysqlclient/MySQLdb.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask

from config import Config
from models.database import db
import models  # noqa: F401  (registers every model on db's metadata)


def _normalise_uri(uri: str) -> str:
    if uri.startswith("mysql+mysqldb://"):
        return "mysql+pymysql://" + uri[len("mysql+mysqldb://"):]
    if uri.startswith("mysql://"):
        return "mysql+pymysql://" + uri[len("mysql://"):]
    return uri


def create_db_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["SQLALCHEMY_DATABASE_URI"] = _normalise_uri(
        app.config.get("SQLALCHEMY_DATABASE_URI", "")
    )
    db.init_app(app)
    return app
