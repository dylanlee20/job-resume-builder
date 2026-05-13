"""Import jobs from the WhaleStreet job-scraper CSV into the local SQLite.

Replaces the in-process bank scrapers. The WhaleStreet pipeline runs
on GitHub Actions, scrapes 349 firms daily, and writes
`services/job-scraper/jobs_finance.csv` to disk. This service reads
that CSV and calls the existing `JobService.process_scraped_job(row)`
per row so all dedupe and AI-proof classification logic is preserved.

CSV path resolution order:
  1. JOBS_CSV_PATH env var
  2. ~/whalestreet/services/job-scraper/jobs_finance.csv
"""

from __future__ import annotations

import csv
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from services.job_service import JobService

logger = logging.getLogger(__name__)


DEFAULT_CSV_PATH = Path.home() / "whalestreet" / "services" / "job-scraper" / "jobs_finance.csv"


def resolve_csv_path() -> Path:
    env = os.environ.get("JOBS_CSV_PATH")
    if env:
        return Path(env).expanduser()
    return DEFAULT_CSV_PATH


def _parse_post_date(raw: str) -> Optional[datetime]:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _row_to_job_dict(row: Dict[str, str]) -> Optional[Dict]:
    company = (row.get("company_name") or "").strip()
    title = (row.get("job_title") or "").strip()
    job_url = (row.get("job_url") or "").strip()
    if not company or not title or not job_url:
        return None
    if (row.get("scrape_status") or "").strip().lower() not in ("", "success"):
        return None
    return {
        "company": company,
        "title": title,
        "location": (row.get("location") or "").strip() or "Unknown",
        "description": "",
        "post_date": _parse_post_date(row.get("date_posted", "")),
        "deadline": None,
        "source_website": (row.get("source_url") or "").strip() or "whalestreet.ai",
        "job_url": job_url,
    }


class CSVImportService:
    _state = {"is_running": False, "started_at": None, "last_result": None}
    _lock = threading.Lock()

    @classmethod
    def is_running(cls) -> bool:
        with cls._lock:
            return cls._state["is_running"]

    @classmethod
    def get_state(cls) -> Dict:
        with cls._lock:
            return dict(cls._state)

    @classmethod
    def import_all(cls) -> Dict:
        csv_path = resolve_csv_path()
        if not csv_path.is_file():
            raise FileNotFoundError(f"WhaleStreet CSV not found at {csv_path}")

        logger.info(f"Importing jobs from CSV: {csv_path}")
        with cls._lock:
            cls._state.update(is_running=True, started_at=datetime.utcnow().isoformat(), last_result=None)

        stats = {"total_rows": 0, "ingested": 0, "skipped": 0, "errors": 0}
        try:
            with csv_path.open("r", encoding="utf-8", newline="") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    stats["total_rows"] += 1
                    job_data = _row_to_job_dict(row)
                    if job_data is None:
                        stats["skipped"] += 1
                        continue
                    try:
                        JobService.process_scraped_job(job_data)
                        stats["ingested"] += 1
                    except Exception as exc:
                        stats["errors"] += 1
                        logger.warning(f"Row failed ({job_data.get('company')} / {job_data.get('title')}): {exc}")
        finally:
            with cls._lock:
                cls._state.update(is_running=False, last_result=stats)

        logger.info(
            f"CSV import complete. rows={stats['total_rows']} "
            f"ingested={stats['ingested']} skipped={stats['skipped']} errors={stats['errors']}"
        )
        return stats

    @classmethod
    def run_async(cls, app=None) -> bool:
        if cls.is_running():
            return False

        def worker():
            if app is not None:
                with app.app_context():
                    try:
                        cls.import_all()
                    except Exception:
                        logger.exception("Async CSV import failed")
                        with cls._lock:
                            cls._state["is_running"] = False
            else:
                try:
                    cls.import_all()
                except Exception:
                    logger.exception("Async CSV import failed")
                    with cls._lock:
                        cls._state["is_running"] = False

        threading.Thread(target=worker, daemon=True, name="csv-import").start()
        return True

    @classmethod
    def get_available_companies(cls) -> List[str]:
        try:
            csv_path = resolve_csv_path()
            companies = set()
            with csv_path.open("r", encoding="utf-8", newline="") as fh:
                for row in csv.DictReader(fh):
                    name = (row.get("company_name") or "").strip()
                    if name:
                        companies.add(name)
            return sorted(companies)
        except FileNotFoundError:
            return []
