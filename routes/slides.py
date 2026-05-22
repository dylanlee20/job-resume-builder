"""Curriculum blueprint: deck index + per-slide viewer + watermarked PNG.

Two index pages share the same deck-viewer URL:
  /curriculum/behavioral  -> section 01 only
  /curriculum/technical   -> sections 02-05
  /curriculum/<slug>/<n>  -> deck viewer (any deck)
  /curriculum/<slug>/<n>/image.png  -> watermarked stream
  /curriculum/files/<section_slug>/<filename>  -> companion artifact download
"""

from __future__ import annotations

import re
from pathlib import Path

from flask import Blueprint, Response, abort, render_template, request, redirect, send_from_directory, url_for
from flask_login import current_user, login_required

from services.slides_service import (
    Deck,
    deck_track,
    get_deck,
    list_sections,
    render_watermarked_png,
    slide_path,
)


_FILES_ROOT = Path(__file__).resolve().parent.parent / "slides_data" / "files"
_SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_ALLOWED_EXTS = {".pdf", ".ipynb", ".csv", ".xlsx", ".py", ".md", ".txt"}


slides_bp = Blueprint("slides", __name__, url_prefix="/curriculum")


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
    return redirect(url_for("slides.behavioral"))


@slides_bp.route("/behavioral")
@login_required
def behavioral():
    return render_template(
        "curriculum_index.html",
        sections=list_sections(track="behavioral"),
        track="behavioral",
        track_label="Behavioral Curriculum",
    )


@slides_bp.route("/technical")
@login_required
def technical():
    return render_template(
        "curriculum_index.html",
        sections=list_sections(track="technical"),
        track="technical",
        track_label="Technical Curriculums",
    )


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
    track = deck_track(deck)
    back_endpoint = "slides.behavioral" if track == "behavioral" else "slides.technical"
    return render_template(
        "slide_viewer.html",
        deck=deck,
        slide_number=slide_number,
        total=deck.slide_count,
        viewer_email=_viewer_label(),
        back_url=url_for(back_endpoint),
        back_label="Behavioral Curriculum" if track == "behavioral" else "Technical Curriculums",
    )


@slides_bp.route("/files/<section_slug>/<path:filename>")
@login_required
def companion_file(section_slug: str, filename: str):
    """Serve a companion artifact (PDF, notebook, CSV, etc) for a deck.

    Path traversal defenses: both the section slug and the filename are
    validated against a strict allowlist regex, the resolved path is then
    checked to be inside _FILES_ROOT, and the extension is allowlisted.
    """
    if not _SAFE_NAME.fullmatch(section_slug):
        abort(404)
    # filename may contain a single subdirectory (e.g. qm02-xs-momentum/notebook.ipynb)
    parts = filename.split("/")
    if not (1 <= len(parts) <= 2):
        abort(404)
    for part in parts:
        if not _SAFE_NAME.fullmatch(part):
            abort(404)
    leaf = parts[-1]
    ext = ("." + leaf.rsplit(".", 1)[-1].lower()) if "." in leaf else ""
    if ext not in _ALLOWED_EXTS:
        abort(404)
    candidate = (_FILES_ROOT / section_slug / Path(*parts)).resolve()
    try:
        candidate.relative_to(_FILES_ROOT.resolve())
    except ValueError:
        abort(404)
    if not candidate.is_file():
        abort(404)
    return send_from_directory(candidate.parent, candidate.name, as_attachment=False)


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
