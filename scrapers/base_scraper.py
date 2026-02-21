"""Base scraper class with common functionality"""
import logging
import time
import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional

from config import Config

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all job scrapers"""

    name = 'BaseScraper'
    source_website = 'Unknown'

    def __init__(self, run_id: str = None, log_callback=None):
        """
        Args:
            run_id: UUID for this scraper run (for logging)
            log_callback: callable(message) to stream logs to DB
        """
        self.run_id = run_id
        self.log_callback = log_callback
        self.logger = logging.getLogger(f'scrapers.{self.name}')
        self.jobs_found = 0
        self.jobs_new = 0
    