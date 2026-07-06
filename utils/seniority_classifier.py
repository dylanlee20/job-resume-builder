"""Full-Time vs Internship classification.

The tracker splits every posting into exactly two buckets so students can
filter for the right thing:

  * ``'Internship'`` — internships, summer analyst/associate seats, off-cycle
    placements, co-ops, spring weeks / insight days and other pre-internship
    programmes.
  * ``'Full Time'`` — everything else, including graduate analyst programmes
    (which are permanent jobs, not internships).

`classify_job_type(title, description, hint)` returns one of those two strings.
`hint` is the raw signal from the scraper (its ``seniority_level`` /
``job_type`` columns) and is consulted alongside the title/description.
"""
import re

INTERNSHIP = "Internship"
FULL_TIME = "Full Time"

# Phrases that mark a posting as an internship / pre-internship programme.
_INTERN_PHRASES = [
    "intern", "internship", "summer analyst", "summer associate",
    "summer intern", "winter intern", "spring intern", "off-cycle",
    "off cycle", "co-op", "co op", "coop", "industrial placement",
    "work placement", "placement year", "placement programme",
    "placement program", "vacation scheme", "spring week", "spring insight",
    "insight week", "insight day", "insight programme", "insight program",
    "insight series", "discovery program", "discovery programme",
    "sophomore program", "sophomore programme", "penultimate", "praktikum",
    "werkstudent", "working student", "student assistant", "trainee intern",
    "campus intern", "pre-internship", "pre internship",
]

# Explicit full-time hints that should win even if a weak intern token appears
# in the description (e.g. "work alongside our interns").
_FULLTIME_HINTS = {
    "full time", "full-time", "fulltime", "permanent", "regular", "perm",
}


def _normalize(value):
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def classify_job_type(title, description="", hint=""):
    """Return ``'Internship'`` or ``'Full Time'`` for a posting."""
    title_n = _normalize(title)
    hint_n = _normalize(hint)
    text = _normalize(f"{title} {description}")

    # The title is the strongest signal — an explicit intern title wins.
    if any(p in title_n for p in _INTERN_PHRASES):
        return INTERNSHIP

    # Scraper hint (seniority_level == 'intern', job_type == 'Internship', ...).
    if "intern" in hint_n or "placement" in hint_n:
        return INTERNSHIP
    if hint_n in _FULLTIME_HINTS:
        return FULL_TIME

    # Fall back to scanning the description for an internship signal.
    if any(p in text for p in _INTERN_PHRASES):
        return INTERNSHIP

    return FULL_TIME
