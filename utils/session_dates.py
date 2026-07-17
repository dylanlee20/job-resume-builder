"""Parsing for the optional 'session date' field on the log-a-session forms.

A logged session is dated by its SessionRecord.created_at, which drives both
the weekly payroll bucketing and the rate-effective-at lookup. Letting a mentor
pick the date the session actually happened therefore just means setting
created_at from the form instead of always using "now".
"""
from datetime import datetime


def parse_session_date(raw, now):
    """Turn a 'YYYY-MM-DD' form value into a datetime for SessionRecord.created_at.

    Returns (dt, error):
      * blank            -> (now, None)                 # default to right now
      * valid past/today -> (that day at 12:00, None)   # noon keeps the day
                                                        # stable under tz skew
      * malformed        -> (None, message)
      * future date      -> (None, message)
    """
    text = (raw or "").strip()
    if not text:
        return now, None
    try:
        day = datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None, "Enter a valid session date (YYYY-MM-DD)."
    dt = day.replace(hour=12, minute=0, second=0, microsecond=0)
    if dt.date() > now.date():
        return None, "Session date cannot be in the future."
    return dt, None
