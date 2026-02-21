"""
Weekly Job Scraper Scheduler
Automatically runs scrapers every Sunday at 2 AM
"""

import os
import sys
from datetime import datetime
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from scraper_runner import run_all_scrapers

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/logs/scheduler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def scheduled_scraper_job():
    """Wrapper function for scheduled scraper run"""
    logger.info("=" * 80)
    logger.info("SCHEDULED SCRAPER JOB TRIGGERED")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    try:
        run_all_scrapers()
        logger.info("Scheduled scraper job completed successfully")
    except Exception as e:
        logger.error(f"Error in scheduled scraper job: {e}")


def start_scheduler():
    """Start the background scheduler"""
    scheduler = BackgroundScheduler()

    # Schedule: Every Sunday at 2:00 AM
    scheduler.add_job(
        func=scheduled_scraper_job,
        trigger=CronTrigger(day_of_week='sun', hour=2, minute=0),
        id='weekly_scraper',
        name='Weekly Job Scraper',
        replace_existing=True
    )

    # Start the scheduler
    scheduler.start()
    logger.info("Scheduler started - Jobs will run every Sunday at 2:00 AM")

    # Print scheduled jobs
    logger.info(f"Next run: {scheduler.get_job('weekly_scraper').next_run_time}")

    # Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())

    return scheduler


if __name__ == '__main__':
    # For testing: run immediately when script is executed directly
    logger.info("Running scraper immediately for testing...")
    scheduled_scraper_job()
