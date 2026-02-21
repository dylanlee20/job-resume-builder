"""
Scraper Runner with AI-Proof Classification
Runs all scrapers and classifies jobs as AI-proof or excluded
"""

import sys
import os
from datetime import datetime
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask
from models.database import db
from models.job import Job
from models.scraper_run import ScraperRun
from utils.ai_proof_filter import classify_ai_proof_role
from utils.seniority_classifier import classify_seniority
from config import Config
import json
import time

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/logs/scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Import all scrapers
from scrapers.goldman_scraper import GoldmanSachsScraper
from scrapers.jpmorgan_scraper import JPMorganScraper
from scrapers.morgan_stanley_scraper import MorganStanleyScraper
from scrapers.bofa_scraper import BofAScraper
from scrapers.citi_scraper import CitiScraper
from scrapers.barclays_scraper import BarclaysScraper
from scrapers.deutsche_bank_scraper import DeutscheBankScraper
from scrapers.ubs_scraper import UBSScraper
from scrapers.hsbc_scraper import HSBCScraper
from scrapers.bnp_paribas_scraper import BNPParibasScraper
from scrapers.jefferies_scraper import JefferiesScraper
from scrapers.evercore_scraper import EvercoreScraper
from scrapers.piper_sandler_scraper import PiperSandlerScraper
from scrapers.blackstone_scraper import BlackstoneScraper
from scrapers.nomura_scraper import NomuraScraper
from scrapers.mizuho_scraper import MizuhoScraper
from scrapers.jpmorgan_hongkong_scraper import JPMorganHongKongScraper
from scrapers.jpmorgan_australia_scraper import JPMorganAustraliaScraper
from scrapers.goldman_sachs_international_scraper import GoldmanSachsInternationalScraper

# All scraper classes
SCRAPERS = [
    GoldmanSachsScraper,
    JPMorganScraper,
    MorganStanleyScraper,
    BofAScraper,
    CitiScraper,
    BarclaysScraper,
    DeutscheBankScraper,
    UBSScraper,
    HSBCScraper,
    BNPParibasScraper,
    JefferiesScraper,
    EvercoreScraper,
    PiperSandlerScraper,
    BlackstoneScraper,
    NomuraScraper,
    MizuhoScraper,
    JPMorganHongKongScraper,
    JPMorganAustraliaScraper,
    GoldmanSachsInternationalScraper,
]


def create_app():
    """Create Flask app for database access"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app


def save_job_to_db(job_data):
    """
    Save a job to database with AI-proof classification

    Args:
        job_data: Dict with keys: company, title, location, description,
                  post_date, deadline, source_website, job_url

    Returns:
        Tuple (saved: bool, reason: str)
    """
    try:
        # Check if job already exists (by unique URL)
        existing_job = Job.query.filter_by(job_url=job_data['job_url']).first()
        if existing_job:
            return (False, 'duplicate')

        # Classify job as AI-proof or excluded
        is_ai_proof, category = classify_ai_proof_role(
            job_data['title'],
            job_data.get('description', '')
        )

        # Classify seniority level
        seniority = classify_seniority(
            job_data['title'],
            job_data.get('description', '')
        )

        # Generate job hash for deduplication
        job_hash = Job.generate_job_hash(
            job_data['company'],
            job_data['title'],
            job_data['location']
        )

        # Create new job
        job = Job(
            job_hash=job_hash,
            company=job_data['company'],
            title=job_data['title'],
            location=job_data['location'],
            description=job_data.get('description', ''),
            post_date=job_data.get('post_date'),
            deadline=job_data.get('deadline'),
            source_website=job_data['source_website'],
            job_url=job_data['job_url'],
            is_ai_proof=is_ai_proof,
            ai_proof_category=category,
            seniority=seniority,
            status='active'
        )

        db.session.add(job)
        db.session.commit()

        return (True, category)

    except Exception as e:
        logger.error(f"Error saving job '{job_data.get('title', 'UNKNOWN')}': {e}")
        db.session.rollback()
        return (False, f'error: {e}')


def run_all_scrapers(trigger='scheduled'):
    """Run all scrapers and save jobs to database

    Args:
        trigger: 'scheduled', 'manual', or 'automatic'
    """
    app = create_app()

    with app.app_context():
        # Create scraper run record
        start_time = datetime.utcnow()
        scraper_run = ScraperRun(
            started_at=start_time,
            status='running',
            trigger=trigger
        )
        db.session.add(scraper_run)
        db.session.commit()

        logger.info("=" * 80)
        logger.info("Starting weekly scraper run")
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Run ID: {scraper_run.id}")
        logger.info("=" * 80)

        total_scraped = 0
        total_saved = 0
        ai_proof_count = 0
        excluded_count = 0
        duplicate_count = 0
        error_count = 0
        companies_scraped = 0
        companies_failed = 0

        stats_by_category = {}
        company_results = {}
        error_log = []

        for scraper_class in SCRAPERS:
            company_name = scraper_class.__name__.replace('Scraper', '')
            company_jobs_saved = 0

            try:
                logger.info(f"\n{'=' * 60}")
                logger.info(f"Running scraper: {scraper_class.__name__}")
                logger.info(f"{'=' * 60}")

                scraper = scraper_class()
                jobs = scraper.scrape_with_retry()

                logger.info(f"Scraped {len(jobs)} jobs from {scraper.company_name}")
                total_scraped += len(jobs)

                # Save each job to database
                for job_data in jobs:
                    saved, reason = save_job_to_db(job_data)

                    if saved:
                        total_saved += 1
                        company_jobs_saved += 1
                        if reason.startswith('error'):
                            error_count += 1
                        else:
                            # Track category stats
                            stats_by_category[reason] = stats_by_category.get(reason, 0) + 1

                            # Check if AI-proof or excluded
                            if reason in ['Investment Banking', 'Sales & Trading',
                                         'Portfolio Management', 'Risk Management',
                                         'M&A Advisory', 'Private Equity', 'Structuring']:
                                ai_proof_count += 1
                            else:
                                excluded_count += 1
                    else:
                        if reason == 'duplicate':
                            duplicate_count += 1
                        else:
                            error_count += 1

                logger.info(f"Completed {scraper.company_name}: "
                           f"{company_jobs_saved} new jobs saved")

                companies_scraped += 1
                company_results[company_name] = {
                    'scraped': len(jobs),
                    'saved': company_jobs_saved,
                    'status': 'success'
                }

            except Exception as e:
                error_msg = f"Error running {scraper_class.__name__}: {e}"
                logger.error(error_msg)
                error_log.append(error_msg)
                companies_failed += 1
                company_results[company_name] = {
                    'scraped': 0,
                    'saved': 0,
                    'status': 'failed',
                    'error': str(e)
                }
                continue

        # Update scraper run record
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        scraper_run.completed_at = end_time
        scraper_run.duration_seconds = duration
        scraper_run.status = 'completed' if companies_failed == 0 else 'failed'
        scraper_run.total_jobs_scraped = total_scraped
        scraper_run.new_jobs_added = total_saved
        scraper_run.jobs_updated = 0  # We don't update jobs in this version
        scraper_run.companies_scraped = companies_scraped
        scraper_run.companies_failed = companies_failed
        scraper_run.error_log = '\n'.join(error_log) if error_log else None
        scraper_run.company_results = json.dumps(company_results, indent=2)

        db.session.commit()

        # Print summary
        logger.info("\n" + "=" * 80)
        logger.info("SCRAPER RUN SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Run ID: {scraper_run.id}")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Total jobs scraped: {total_scraped}")
        logger.info(f"New jobs saved: {total_saved}")
        logger.info(f"  - AI-proof jobs: {ai_proof_count}")
        logger.info(f"  - Excluded jobs: {excluded_count}")
        logger.info(f"Duplicates skipped: {duplicate_count}")
        logger.info(f"Errors: {error_count}")
        logger.info(f"Companies scraped: {companies_scraped}")
        logger.info(f"Companies failed: {companies_failed}")
        logger.info("\nBreakdown by category:")
        for category, count in sorted(stats_by_category.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {category}: {count}")
        logger.info("=" * 80)
        logger.info(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        return scraper_run.id


if __name__ == '__main__':
    import sys
    # Check if trigger argument is provided
    trigger = sys.argv[1] if len(sys.argv) > 1 else 'scheduled'
    run_all_scrapers(trigger=trigger)
