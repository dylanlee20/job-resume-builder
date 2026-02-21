"""Job scheduler for automated scraping"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class JobScheduler:
    """Background job scheduler for weekly scraping"""

    def __init__(self, app):
        self.app = app
        self.scheduler = BackgroundScheduler()
        self._setup_jobs()

    def _setup_jobs(self):
        """Setup scheduled jobs - weekly scraping every Sunday at 2 AM"""
        self.scheduler.add_job(
            func=self._run_scrapers,
            trigger=CronTrigger(day_of_week='sun', hour=2, minute=0),
            id='weekly_scraper',
            name='Weekly Job Scraper',
            replace_existing=True
        )
        logger.info("Scheduled weekly scraper job: Every Sunday at 2:00 AM")

    def _run_scrapers(self):
        """Run all scrapers with app context"""
        logger.info("=" * 80)
        logger.info("SCHEDULED SCRAPER JOB TRIGGERED")
        logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        with self.app.app_context():
            try:
                # Import here to avoid circular imports
                from scraper_runner import run_all_scrapers
                run_all_scrapers()
                logger.info("Scheduled scraper job completed successfully")
            except Exception as e:
                logger.error(f"Error in scheduled scraper job: {e}")

    def run_now(self):
        """Manually trigger scraper run (for testing)"""
        logger.info("Manual scraper run triggered")
        self._run_scrapers()

    def start(self):
        """Start the scheduler"""
        self.scheduler.start()
        next_run = self.scheduler.get_job('weekly_scraper').next_run_time
        logger.info(f"Job scheduler started - Next scraper run: {next_run}")

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Job scheduler stopped")
