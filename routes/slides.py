"""Slides blueprint: deck index + per-slide viewer + watermarked PNG stream.

All routes require login. Source PNGs are never served directly — every
image request runs through Pillow to burn in the viewer's identity.
"""

from __future__ import annotations

from flask import Blueprint, Response, abort, render_template, request
from flask_login import current_user, login_required

from services.slides_service import (
    Deck,
    get_deck,
    list_decks,
    render_watermarked_png,
    slide_path,
)


slides_bp = Blueprint("slides", __name__, url_prefix="/slides")


def _client_ip() -> str:
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or ""


def _viewer_label() -> str:
    return getattr(current_user, "email", None) or current_user.username


@slides_bp.route("/")
@login_required
def index():
    decks = list_decks()
    return render_template("slides_index.html", decks=decks)


@slides_bp.route("/<slug>/")
@login_required
def deck_redirect(slug: str):
    deck = get_deck(slug)
    if deck is None:
        abort(404)
    return view_slide(slug, 1)


@slides_bp.route("/<slug>/<int:slide_number>")
@login_required
def view_slide(slug: str, slide_number: int):
    deck = get_deck(slug)
    if deck is None:
        abort(404)
    if not 1 <= slide_number <= deck.slide_count:
        abort(404)
    return render_template(
        "slide_viewer.html",
        deck=deck,
        slide_number=slide_number,
        total=deck.slide_count,
        viewer_email=_viewer_label(),
    )


@slides_bp.route("/<slug>/<int:slide_number>/image.png")
@login_required
def slide_image(slug: str, slide_number: int):
    path = slide_path(slug, slide_number)
    if path is None:
        abort(404)
    png = render_watermarked_png(path, _viewer_label(), _client_ip())
    resp = Response(png, mimetype="image/png")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Content-Disposition"] = "inline"
    return resp
