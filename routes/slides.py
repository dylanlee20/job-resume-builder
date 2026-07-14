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

from flask import Blueprint, Response, abort, jsonify, render_template, request, redirect, send_from_directory, url_for
from flask_login import current_user, login_required

from models.database import db
from models.saved_question import SavedQuestion
from services.slides_service import (
    Deck,
    deck_toc,
    deck_track,
    get_deck,
    list_sections,
    render_watermarked_png,
    slide_path,
    toc_unit_for_slide,
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


def _allowed_sections():
    """Section slugs the current user may see, or None for no restriction.

    Only mentors are gated (to their granted curriculums); admins and students
    see everything.
    """
    if getattr(current_user, "is_mentor", False):
        return current_user.curriculum_set
    return None


def _guard_deck(deck: Deck) -> None:
    """403 if the current user (a gated mentor) may not view this deck's section."""
    if not current_user.has_curriculum(deck.section_slug):
        abort(403)


@slides_bp.route("/")
@login_required
def index():
    return redirect(url_for("slides.behavioral"))


@slides_bp.route("/behavioral")
@login_required
def behavioral():
    return render_template(
        "curriculum_index.html",
        sections=list_sections(track="behavioral", allowed=_allowed_sections()),
        track="behavioral",
        track_label="Behavioral Curriculum",
    )


@slides_bp.route("/technical")
@login_required
def technical():
    return render_template(
        "curriculum_index.html",
        sections=list_sections(track="technical", allowed=_allowed_sections()),
        track="technical",
        track_label="Technical Curriculums",
    )


@slides_bp.route("/<slug>/")
@login_required
def deck_redirect(slug: str):
    deck = get_deck(slug)
    if deck is None:
        abort(404)
    _guard_deck(deck)
    return view_slide(slug, 1)


@slides_bp.route("/<slug>/<int:slide_number>")
@login_required
def view_slide(slug: str, slide_number: int):
    deck = get_deck(slug)
    if deck is None:
        abort(404)
    _guard_deck(deck)
    if not 1 <= slide_number <= deck.slide_count:
        abort(404)
    track = deck_track(deck)
    back_endpoint = "slides.behavioral" if track == "behavioral" else "slides.technical"
    toc = deck_toc(slug)
    current_unit = toc_unit_for_slide(toc, slide_number) if toc else None
    saved_keys = set()
    if toc:
        saved_keys = {
            row.question_key
            for row in SavedQuestion.query.filter_by(
                user_id=current_user.id, deck_slug=slug
            ).with_entities(SavedQuestion.question_key)
        }
    return render_template(
        "slide_viewer.html",
        deck=deck,
        slide_number=slide_number,
        total=deck.slide_count,
        viewer_email=_viewer_label(),
        back_url=url_for(back_endpoint),
        back_label="Behavioral Curriculum" if track == "behavioral" else "Technical Curriculums",
        toc=toc,
        current_unit=current_unit,
        saved_keys=saved_keys,
    )


@slides_bp.route("/api/questions/toggle-save", methods=["POST"])
@login_required
def toggle_save_question():
    """Save or unsave a question unit for the current user.

    Body: {"deck_slug": ..., "question_key": ...}. The unit metadata is taken
    from the deck's toc.json server-side (never trusted from the client).
    Returns {"saved": true|false}.
    """
    data = request.get_json(silent=True) or {}
    slug = str(data.get("deck_slug", ""))
    key = str(data.get("question_key", ""))
    toc = deck_toc(slug)
    if not toc:
        abort(404)
    unit = next((u for u in toc if u["key"] == key), None)
    if unit is None:
        abort(404)
    existing = SavedQuestion.query.filter_by(
        user_id=current_user.id, deck_slug=slug, question_key=key
    ).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"saved": False})
    db.session.add(SavedQuestion(
        user_id=current_user.id,
        deck_slug=slug,
        question_key=key,
        label=unit["label"],
        topic=unit.get("topic") or None,
        question_slide=unit["question_slide"],
        answer_slide=unit.get("answer_slide"),
        end_slide=unit["end_slide"],
    ))
    db.session.commit()
    return jsonify({"saved": True})


@slides_bp.route("/saved")
@login_required
def saved_questions():
    """The student's saved questions, grouped by deck, newest first."""
    rows = (SavedQuestion.query
            .filter_by(user_id=current_user.id)
            .order_by(SavedQuestion.created_at.desc())
            .all())
    groups = []
    by_deck = {}
    for row in rows:
        deck = get_deck(row.deck_slug)
        if deck is None:
            continue  # deck was renamed/removed; hide silently
        if row.deck_slug not in by_deck:
            by_deck[row.deck_slug] = {"deck": deck, "questions": []}
            groups.append(by_deck[row.deck_slug])
        by_deck[row.deck_slug]["questions"].append(row)
    return render_template("saved_questions.html", groups=groups, total=len(rows))


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
    # Mentors may only download companion files for curriculums they were granted.
    if not current_user.has_curriculum(section_slug):
        abort(403)
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
    deck = get_deck(slug)
    if deck is None:
        abort(404)
    _guard_deck(deck)
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
