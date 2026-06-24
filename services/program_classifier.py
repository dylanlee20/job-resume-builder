"""Classify a job/posting title as an early-career and/or diversity program.

Used both to tag scraped listings and to label curated program entries, so the
tracker can surface bank early programs (spring/insight/sophomore/freshman) and
women/diversity programs from a single signal: the `program_type` field, which
holds 'early', 'diversity', 'early,diversity', or None.
"""
import re

# High-precision phrases that mark an early-career / pre-internship program.
_EARLY = [
    "spring insight", "spring week", "spring intern", "sophomore", "freshman",
    "first year", "first-year", "1st year", "second year", "insight day",
    "insight week", "insight program", "insight programme", "early insight",
    "early career", "early talent", "pre-internship", "pre internship",
    "rising sophomore", "rising junior", "underclassmen", "undergraduate insight",
    "discovery program", "discovery programme", "explore program",
]

# Women / diversity / inclusion program markers.
_DIVERSITY = [
    "women", "womens", "women's", "female", "diversity", "diverse",
    "inclusion", "lgbt", "returnship", "return to work", "veteran",
    "disability", "multicultural", "bipoc", "hispanic", "latino", "latina",
    "latinx", "indigenous", "first generation", "first-generation",
    "out for undergrad",
]


def _matches(text: str, phrases) -> bool:
    return any(p in text for p in phrases)


def classify_program(title: str, description: str = "") -> str | None:
    """Return 'early', 'diversity', 'early,diversity', or None for a title."""
    text = f"{title or ''} {description or ''}".lower()
    # Normalise punctuation/whitespace so "women's" and "women s" both hit.
    text = re.sub(r"\s+", " ", text)

    tags = []
    if _matches(text, _DIVERSITY):
        tags.append("diversity")
    if _matches(text, _EARLY):
        tags.append("early")
    return ",".join(tags) if tags else None
