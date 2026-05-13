"""Slide catalog + per-request watermarking.

Decks live under slides_data/decks/<slug>/slide_NNN.png. Each slide is
served through a Flask route that opens the source PNG, overlays a
diagonal watermark with the viewer's email + timestamp, and streams it.
Source PNGs are never exposed directly.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont


SLIDES_ROOT = Path(__file__).resolve().parent.parent / "slides_data" / "decks"


@dataclass(frozen=True)
class Deck:
    slug: str
    title: str
    section: str
    slide_count: int


DECK_CATALOG: dict[str, Deck] = {
    "smoke-test": Deck(
        slug="smoke-test",
        title="Smoke Test — All Slide Types",
        section="00 — Engine Verification",
        slide_count=14,
    ),
}


def list_decks() -> List[Deck]:
    return list(DECK_CATALOG.values())


def get_deck(slug: str) -> Optional[Deck]:
    return DECK_CATALOG.get(slug)


def slide_path(slug: str, slide_number: int) -> Optional[Path]:
    deck = get_deck(slug)
    if deck is None:
        return None
    if not 1 <= slide_number <= deck.slide_count:
        return None
    path = SLIDES_ROOT / slug / f"slide_{slide_number:03d}.png"
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
    """Open source PNG, overlay diagonal watermark, return PNG bytes."""
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
