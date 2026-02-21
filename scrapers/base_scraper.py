"""Base scraper class with Selenium WebDriver management"""
from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import time
import random
import logging
import os
from config import Config

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT,
    handlers=[
        logging.FileHandler(Config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)


class BaseScraper(ABC):
    """Abstract base class for all job scrapers with Selenium WebDriver"""

    def __init__(self, company_name, source_url):
        self.company_name = company_name
        self.source_url = source_url
        self.driver = None
        self.logger = logging.getLogger(f"{__name__}.{company_name}")

    def init_driver(self):
        """Initialize Selenium WebDriver"""
        try:
            chrome_options = Options()

            if Config.HEADLESS_MODE:
                chrome_options.add_argument('--headless')

            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')

            chrome_options.add_argument(
                'user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )

            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            try:
                driver_path = ChromeDriverManager().install()

                # Fix: webdriver-manager may return wrong file path
                if 'THIRD_PARTY_NOTICES' in driver_path or not os.path.exists(driver_path):
                    cache_base = os.path.expanduser('~/.wdm/drivers/chromedriver')

                    found = False
                    for root, dirs, files in os.walk(cache_base):
                        if 'chromedriver' in files:
                            potential_path = os.path.join(root, 'chromedriver')
                            try:
                                os.chmod(potential_path, 0o755)
                                if os.path.getsize(potential_path) > 1000000:
                                    driver_path = potential_path
                                    self.logger.info(f"Found chromedriver at: {driver_path}")
                                    found = True
                                    break
                            except Exception:
                                continue

                    if not found:
                        raise Exception("Could not find valid chromedriver executable")

                service = Service(driver_path)
            except Exception as e:
                self.logger.error(f"ChromeDriver setup failed: {e}")
                raise
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            self.driver.set_page_load_timeout(Config.SCRAPER_TIMEOUT)

            self.logger.info(f"WebDriver initialized for {self.company_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize WebDriver for {self.company_name}: {e}")
            return False

    def close_driver(self):
        """Close the browser"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info(f"WebDriver closed for {self.company_name}")
            except Exception as e:
                self.logger.error(f"Error closing WebDriver for {self.company_name}: {e}")

    def random_delay(self):
        """Random delay to avoid detection"""
        delay = random.uniform(Config.SCRAPER_DELAY_MIN, Config.SCRAPER_DELAY_MAX)
        time.sleep(delay)

    def wait_for_element(self, by, value, timeout=10):
        """Wait for an element to appear on the page"""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except Exception as e:
            self.logger.warning(f"Element not found: {by}={value}, {e}")
            return None

    def scroll_to_bottom(self, pause_time=1):
        """Scroll to the bottom of the page (handles lazy loading)"""
        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")

            while True:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(pause_time)

                new_height = self.driver.execute_script("return document.body.scrollHeight")

                if new_height == last_height:
                    break

                last_height = new_height

        except Exception as e:
            self.logger.warning(f"Error scrolling to bottom: {e}")

    @abstractmethod
    def scrape_jobs(self):
        """
        Scrape job listings (abstract method, implemented by subclasses).

        Returns:
            List[Dict]: List of jobs, each containing:
                - company: Company name
                - title: Job title
                - location: Work location
                - description: Job description
                - post_date: Post date (optional)
                - deadline: Deadline (optional)
                - source_website: Source website
                - job_url: Job URL
        """
        pass

    def scrape_with_retry(self, max_retries=None):
        """
        Scrape with retry logic.

        Args:
            max_retries: Maximum retry count, defaults to config value

        Returns:
            List[Dict]: List of jobs
        """
        if max_retries is None:
            max_retries = Config.SCRAPER_RETRY_COUNT

        for attempt in range(max_retries):
            try:
                self.logger.info(
                    f"Starting scrape for {self.company_name} (attempt {attempt + 1}/{max_retries})"
                )

                if not self.init_driver():
                    raise Exception("Failed to initialize WebDriver")

                jobs = self.scrape_jobs()

                self.logger.info(
                    f"Successfully scraped {len(jobs)} jobs from {self.company_name}"
                )

                return jobs

            except Exception as e:
                self.logger.error(
                    f"Scrape failed for {self.company_name} (attempt {attempt + 1}/{max_retries}): {e}"
                )

                if attempt < max_retries - 1:
                    self.logger.info("Retrying in 5 seconds...")
                    time.sleep(5)
                else:
                    self.logger.error(f"All retry attempts failed for {self.company_name}")
                    return []

            finally:
                self.close_driver()

        return []

    def get_page_source(self):
        """Get current page source"""
        return self.driver.page_source if self.driver else None

    def get_soup(self):
        """Get BeautifulSoup object for current page"""
        page_source = self.get_page_source()
        return BeautifulSoup(page_source, 'lxml') if page_source else None
