"""Job scheduler for automated scraping"""
from apscheduler.schedulers.background import BackgroundScheduler
import logging

logger = logging.getLogger(__name__)


class JobScheduler:
    """Background job scheduler"""
    
    def __init__(self, app):
        self.app = app
        self.scheduler = BackgroundScheduler()
        self._setup_jobs()
    
    def _setup_jobs(self):
        """Setup scheduled jobs (placeholder)"""
        # Will add scraping jobs later
        pass
    
    def start(self):
        """Start the scheduler"""
        self.scheduler.start()
        logger.info("Job scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Job scheduler stopped")
