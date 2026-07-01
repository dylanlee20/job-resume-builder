"""Direct Morgan Stanley ingestion — bypasses the CI-IP block.

The WhaleStreet job-scraper (GitHub Actions) cannot reach Morgan Stanley:
MS blocks the CI datacenter egress IP, so its careers API times out and MS
lands 0 rows in jobs_finance.csv every day. This box (the newwhaletech
droplet) reaches the same pure-HTTP JSON API fine, so we fetch MS *here*
during the daily import and feed each role through the identical
`JobService.process_scraped_job()` path CSV rows take — dedupe, expiry and
classification all stay consistent.

MS exposes the Students & Graduates bucket at:
  /web/career_services/webapp/service/careerservice/resultset.json?opportunity=sg
It returns the whole bucket in one shot (no pagination).

Everything here is best-effort: a network hiccup or an MS-side change logs a
warning and returns whatever was gathered, never raising into the importer.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

import requests

from services.job_service import JobService
from services.program_classifier import classify_program

logger = logging.getLogger(__name__)

MS_API_URL = (
    "https://www.morganstanley.com/web/career_services/webapp/service/"
    "careerservice/resultset.json"
)
# Students & Graduates is the only bucket published via this endpoint;
# experienced-professional roles live on a separate system MS does not expose.
MS_OPPORTUNITY_KEYS = ("sg",)
MS_SOURCE = "morganstanley.com"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
_TIMEOUT = 30


def _parse_ms_date(raw) -> Optional[datetime]:
    """Parse an MS date. Handles both shapes MS returns:

      - applicationDate: a string like 'Sep 27, 2026'
      - sortingDate:     epoch milliseconds as an int (e.g. 1798693200000)

    Returns None on anything unparseable. Never raises.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        try:
            return datetime.utcfromtimestamp(raw / 1000)
        except (ValueError, OverflowError, OSError):
            return None
    raw = str(raw).strip()
    if not raw:
        return None
    for fmt in ("%b %d, %Y", "%Y-%m-%d", "%d %b %Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def fetch_morgan_stanley_jobs() -> List[Dict]:
    """Fetch MS Students & Graduates roles as job_data dicts. Never raises."""
    headers = {"User-Agent": _UA, "Accept": "application/json, text/plain, */*"}
    jobs: List[Dict] = []
    seen = set()

    for key in MS_OPPORTUNITY_KEYS:
        try:
            resp = requests.get(
                f"{MS_API_URL}?opportunity={key}", headers=headers, timeout=_TIMEOUT
            )
        except Exception as exc:
            logger.warning("Morgan Stanley fetch failed (opportunity=%s): %s", key, exc)
            continue

        if resp.status_code != 200:
            logger.warning(
                "Morgan Stanley API returned HTTP %s (opportunity=%s)",
                resp.status_code,
                key,
            )
            continue

        try:
            payload = resp.json()
        except Exception as exc:
            logger.warning(
                "Morgan Stanley API returned non-JSON (opportunity=%s): %s", key, exc
            )
            continue

        for item in payload.get("resultSet") or []:
            title = (item.get("jobTitle") or "").strip()
            job_url = (item.get("url") or "").strip()
            if not title or not job_url or job_url in seen:
                continue
            seen.add(job_url)
            jobs.append(
                {
                    "company": "Morgan Stanley",
                    "title": title,
                    "location": (item.get("location") or "").strip() or "Unknown",
                    "description": "",
                    "post_date": _parse_ms_date(item.get("sortingDate")),
                    "deadline": _parse_ms_date(item.get("applicationDate")),
                    "source_website": MS_SOURCE,
                    "job_url": job_url,
                    "program_type": classify_program(title),
                }
            )

    return jobs


def ingest_morgan_stanley() -> Dict:
    """Fetch + ingest MS roles via JobService. Returns {found, ingested, errors}.

    Idempotent: process_scraped_job dedupes on (company, title, location) and
    refreshes last_seen, so calling this every import keeps MS roles active and
    lets them expire naturally once MS stops returning them.
    """
    jobs = fetch_morgan_stanley_jobs()
    stats = {"found": len(jobs), "ingested": 0, "errors": 0}

    for job_data in jobs:
        try:
            JobService.process_scraped_job(job_data)
            stats["ingested"] += 1
        except Exception as exc:
            stats["errors"] += 1
            logger.warning(
                "Morgan Stanley row failed (%s): %s", job_data.get("title"), exc
            )

    logger.info(
        "Morgan Stanley direct ingest: found=%s ingested=%s errors=%s",
        stats["found"],
        stats["ingested"],
        stats["errors"],
    )
    return stats


if __name__ == "__main__":
    # Manual smoke test against the live API (no DB writes).
    for j in fetch_morgan_stanley_jobs():
        print(f"{j['location']:<28} | {j['title']}")
