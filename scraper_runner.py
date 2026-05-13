"""Compat shim — replaced the in-process bank scrapers with a CSV importer.

The WhaleStreet job-scraper runs daily on GitHub Actions across 349 firms
and writes services/job-scraper/jobs_finance.csv. This script reads that
CSV, ingests rows via JobService.process_scraped_job(), and records the
operation in the ScraperRun table so the existing /admin/scraper-status
UI keeps working.

Preserves the public API:
    run_all_scrapers(trigger='scheduled', skip_scraped_today=False)
    python scraper_runner.py [trigger] [--skip-scraped-today]
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask

from config import Config
from models.database import db
from models.scraper_run import ScraperRun
from services.csv_import_service import CSVImportService, resolve_csv_path

os.makedirs('data/logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/logs/scraper.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def _create_flask_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app


def run_all_scrapers(trigger: str = 'scheduled', skip_scraped_today: bool = False):
    """Single-source-of-truth ingest. Reads the WhaleStreet CSV, records a ScraperRun row."""
    app = _create_flask_app()
    with app.app_context():
        csv_path = resolve_csv_path()
        logger.info("=" * 80)
        logger.info(f"Starting CSV import (trigger={trigger}, source={csv_path})")
        logger.info("=" * 80)

        run = ScraperRun(
            started_at=datetime.utcnow(),
            status='running',
            trigger=trigger,
            current_company='WhaleStreet CSV',
        )
        db.session.add(run)
        db.session.commit()

        t0 = time.time()
        try:
            stats = CSVImportService.import_all()
            companies = CSVImportService.get_available_companies()
            run.completed_at = datetime.utcnow()
            run.duration_seconds = time.time() - t0
            run.status = 'completed'
            run.total_jobs_scraped = stats['total_rows']
            run.new_jobs_added = stats['ingested']
            run.jobs_updated = 0
            run.companies_scraped = len(companies)
            run.companies_failed = 0
            run.total_companies = len(companies)
            run.current_company = None
            run.company_results = json.dumps({
                'source': str(csv_path),
                'mode': 'csv-import',
                'stats': stats,
                'companies': companies,
            })
            db.session.commit()
            logger.info(
                f"Done: rows={stats['total_rows']} ingested={stats['ingested']} "
                f"skipped={stats['skipped']} errors={stats['errors']} "
                f"firms={len(companies)} duration={run.duration_seconds:.1f}s"
            )
            return run.id
        except Exception as exc:
            logger.exception("CSV import failed")
            run.completed_at = datetime.utcnow()
            run.duration_seconds = time.time() - t0
            run.status = 'failed'
            run.error_log = str(exc)
            db.session.commit()
            raise


if __name__ == '__main__':
    arg_trigger = sys.argv[1] if len(sys.argv) > 1 else 'scheduled'
    arg_skip = '--skip-scraped-today' in sys.argv
    run_all_scrapers(trigger=arg_trigger, skip_scraped_today=arg_skip)
