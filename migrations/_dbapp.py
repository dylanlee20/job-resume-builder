"""Minimal Flask+SQLAlchemy app for migration scripts.

Importing the full app.py runs create_app() at import time (scheduler, blueprints,
eager DB connect). Migrations only need a DB session, so build a bare app the
same way scraper_runner does.

Driver note: the deploy venv has no MySQL driver of its own, and mysqlclient
can't build there (no libmysqlclient headers). So we use the pure-Python pymysql
driver. The prod DATABASE_URL carries an `ssl-mode` query param that mysqlclient
understands but pymysql does not, so we strip it and translate it into a real
SSL context passed through SQLALCHEMY_ENGINE_OPTIONS.
"""
import os
import ssl as ssl_lib
import sys
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask

from config import Config
from models.database import db
import models  # noqa: F401  (registers every model on db's metadata)

_SSL_MODE_KEYS = {"ssl-mode", "ssl_mode", "sslmode"}


def _build_db_config(uri: str):
    """Return (uri, engine_options) using pymysql for any mysql URL.

    Strips the mysqlclient-only `ssl-mode` param and, unless it was DISABLED,
    enables an encrypted (no-verify) connection via a real SSL context.
    Non-mysql URLs (e.g. sqlite in local testing) pass through untouched.
    """
    if not uri.startswith("mysql"):
        return uri, {}

    parts = urlsplit(uri)
    ssl_on = False
    kept = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in _SSL_MODE_KEYS:
            if value.upper() != "DISABLED":
                ssl_on = True
        else:
            kept.append((key, value))

    new_uri = urlunsplit(
        ("mysql+pymysql", parts.netloc, parts.path, urlencode(kept), parts.fragment)
    )

    engine_options = {}
    if ssl_on:
        ctx = ssl_lib.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl_lib.CERT_NONE
        engine_options = {"connect_args": {"ssl": ctx}}
    return new_uri, engine_options


def create_db_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    uri, engine_options = _build_db_config(app.config.get("SQLALCHEMY_DATABASE_URI", ""))
    app.config["SQLALCHEMY_DATABASE_URI"] = uri
    if engine_options:
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options
    db.init_app(app)
    return app
