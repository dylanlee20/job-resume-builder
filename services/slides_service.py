"""Slide catalog (auto-discovered from disk) + per-request watermarking.

Layout on disk:
  slides_data/decks/<section-slug>/<deck-slug>/slide_NNN.png

The catalog is rebuilt from the filesystem each time list_decks() /
get_deck() is called (cached in-process for one second). No hand-curated
list — drop a new section folder + deck folder + PNGs and it shows up.

Display titles are derived from the slug:
  '01-behavioral-and-fit' -> '01 — Behavioral and Fit'
  'b07-understanding-banking' -> 'B07 — Understanding Banking'
"""

from __future__ import annotations

import io
import os
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont


SLIDES_ROOT = Path(__file__).resolve().parent.parent / "slides_data" / "decks"
FILES_ROOT = Path(__file__).resolve().parent.parent / "slides_data" / "files"
# Companion artifact extensions that are surfaced in the curriculum index.
_COMPANION_EXTS = {".pdf", ".ipynb", ".csv", ".xlsx", ".py", ".md", ".txt"}


@dataclass(frozen=True)
class Deck:
    slug: str
    section_slug: str
    title: str
    section_title: str
    slide_count: int


@dataclass
class _CatalogCache:
    catalog: Dict[str, Deck] = field(default_factory=dict)
    sections: List[str] = field(default_factory=list)
    built_at: float = 0.0


_cache = _CatalogCache()
_cache_lock = threading.Lock()
# 1318 PNGs across 5 sections — scanning the tree on every request is wasteful.
# A 5-minute cache is fine because deck folders only change on deploy.
_CACHE_TTL = 300.0  # seconds

# Section 01 is the Behavioral curriculum, everything else is Technical.
BEHAVIORAL_SECTION_SLUG = "01-behavioral-and-fit"

# Hand-curated display names for section folders. Anything not listed
# falls back to the slug-humanizer.
SECTION_TITLE_OVERRIDES = {
    "01-behavioral-and-fit": "Behavioral Curriculum",
    "02-technical-generalist": "Investment Banking Technical Curriculum",
    "03-industry-specific": "Industry Specific Curriculum",
    "04-sales-and-trading": "Sales and Trading Technical Curriculum",
    "05-quant": "Quantitative Technical Curriculum",
    "07-modeling-quant": "Quantitative Hands-On Modeling Curriculum",
    "08-consulting": "Consulting Technical Curriculum",
}


def _humanize(slug: str) -> str:
    """'01-behavioral-and-fit' -> '01 Behavioral and Fit'.
    'b07-understanding-banking' -> 'B07 Understanding Banking'.
    No em dashes (user rule).
    """
    parts = slug.split("-")
    if not parts:
        return slug

    prefix = parts[0]
    if re.fullmatch(r"\d{1,3}", prefix):
        head = prefix
        tail = " ".join(p.capitalize() for p in parts[1:])
        return f"{head} {tail}".strip() if tail else head
    if re.fullmatch(r"[a-z]{1,3}\d{1,3}", prefix):
        head = prefix.upper()
        tail = " ".join(p.capitalize() for p in parts[1:])
        return f"{head} {tail}".strip() if tail else head
    return " ".join(p.capitalize() for p in parts)


def _section_title(slug: str) -> str:
    return SECTION_TITLE_OVERRIDES.get(slug, _humanize(slug))


def _build_catalog() -> None:
    catalog: Dict[str, Deck] = {}
    sections: List[str] = []
    if not SLIDES_ROOT.is_dir():
        _cache.catalog = catalog
        _cache.sections = sections
        _cache.built_at = time.time()
        return
    for section_dir in sorted(SLIDES_ROOT.iterdir()):
        if not section_dir.is_dir():
            continue
        section_slug = section_dir.name
        sections.append(section_slug)
        for deck_dir in sorted(section_dir.iterdir()):
            if not deck_dir.is_dir():
                continue
            slides = sorted(deck_dir.glob("slide_*.png"))
            if not slides:
                continue
            deck = Deck(
                slug=deck_dir.name,
                section_slug=section_slug,
                title=_humanize(deck_dir.name),
                section_title=_section_title(section_slug),
                slide_count=len(slides),
            )
            catalog[deck.slug] = deck
    _cache.catalog = catalog
    _cache.sections = sections
    _cache.built_at = time.time()


def _ensure_catalog() -> None:
    with _cache_lock:
        if not _cache.catalog or (time.time() - _cache.built_at) > _CACHE_TTL:
            _build_catalog()


def list_decks() -> List[Deck]:
    _ensure_catalog()
    return list(_cache.catalog.values())


def list_section_files(section_slug: str) -> List[Dict]:
    """Companion artifacts for a section, as [{filename, label, ext}].

    Files live under slides_data/files/<section_slug>/. Only allowlisted
    extensions are surfaced. Label is a humanized version of the filename stem.
    """
    section_dir = FILES_ROOT / section_slug
    if not section_dir.is_dir():
        return []
    acronyms = {"dcf", "lbo", "ev", "ebitda", "ib", "ecm", "dcm", "fig", "tmt",
                "reit", "reits", "fsg", "mece", "ols", "pei", "fx", "npv", "irr",
                "wacc", "moic", "ipo", "pe", "vc", "ai", "us", "uk"}
    out = []
    for f in sorted(section_dir.iterdir()):
        if not f.is_file() or f.suffix.lower() not in _COMPANION_EXTS:
            continue
        words = f.stem.replace("-", " ").replace("_", " ").strip().split()
        label = " ".join(w.upper() if w.lower() in acronyms else w.capitalize() for w in words)
        out.append({"filename": f.name, "label": label, "ext": f.suffix.lstrip(".").upper()})
    return out


def list_sections(track: Optional[str] = None) -> List[Dict]:
    """Return decks grouped by section. ``track`` filters: 'behavioral' or 'technical'."""
    _ensure_catalog()
    grouped: Dict[str, List[Deck]] = {}
    for deck in _cache.catalog.values():
        grouped.setdefault(deck.section_slug, []).append(deck)
    out = []
    for section_slug in _cache.sections:
        if track == "behavioral" and section_slug != BEHAVIORAL_SECTION_SLUG:
            continue
        if track == "technical" and section_slug == BEHAVIORAL_SECTION_SLUG:
            continue
        decks = grouped.get(section_slug, [])
        if not decks:
            continue
        out.append({
            "section_slug": section_slug,
            "section_title": _section_title(section_slug),
            "decks": decks,
            "deck_count": len(decks),
            "slide_count": sum(d.slide_count for d in decks),
            "files": list_section_files(section_slug),
        })
    return out


def deck_track(deck: Deck) -> str:
    """'behavioral' for section-01 decks, 'technical' otherwise."""
    return "behavioral" if deck.section_slug == BEHAVIORAL_SECTION_SLUG else "technical"


def get_deck(slug: str) -> Optional[Deck]:
    _ensure_catalog()
    return _cache.catalog.get(slug)


def slide_path(slug: str, slide_number: int) -> Optional[Path]:
    deck = get_deck(slug)
    if deck is None:
        return None
    if not 1 <= slide_number <= deck.slide_count:
        return None
    path = SLIDES_ROOT / deck.section_slug / slug / f"slide_{slide_number:03d}.png"
    return path if path.is_file() else None


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def render_watermarked_png(
    source: Path,
    viewer_email: str,
    viewer_ip: str = "",
) -> bytes:
    img = Image.open(source).convert("RGBA")
    width, height = img.size

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(18, width // 60)
    font = _load_font(font_size)

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    label = f"{viewer_email}  ·  {timestamp}"
    if viewer_ip:
        label = f"{label}  ·  {viewer_ip}"

    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    tile = Image.new("RGBA", (text_w + 80, text_h + 80), (0, 0, 0, 0))
    tile_draw = ImageDraw.Draw(tile)
    tile_draw.text((40, 40), label, font=font, fill=(120, 120, 120, 70))

    rotated = tile.rotate(30, resample=Image.BICUBIC, expand=True)
    rw, rh = rotated.size

    step_x = int(rw * 0.9)
    step_y = int(rh * 1.4)
    for y in range(-rh, height + rh, step_y):
        offset = 0 if (y // step_y) % 2 == 0 else step_x // 2
        for x in range(-rw + offset, width + rw, step_x):
            overlay.alpha_composite(rotated, (x, y))

    out = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
