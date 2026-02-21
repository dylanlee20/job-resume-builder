"""Base scraper class with Selenium WebDriver management"""
from abc import ABC, abstractmethod
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from bs4 import BeautifulSoup
import shutil
import subprocess
import tempfile
import time
import random
import logging
import os
from config import Config

# Logging is configured by scraper_runner.py (the entry point).
# Do NOT call logging.basicConfig() here to avoid duplicate log lines.


class BaseScraper(ABC):
    """Abstract base class for all job scrapers with Selenium WebDriver"""

    def __init__(self, company_name, source_url):
        self.company_name = company_name
        self.source_url = source_url
        self.driver = None
        self._user_data_dir = None
        self.logger = logging.getLogger(f"{__name__}.{company_name}")

    @staticmethod
    def _detect_chrome_binary():
        """Detect available Chrome or Chromium binary on the system"""
        if Config.CHROME_BINARY_PATH:
            return Config.CHROME_BINARY_PATH, 'chrome'

        # Check for Google Chrome first, then Chromium
        chrome_names = [
            ('google-chrome-stable', 'chrome'),
            ('google-chrome', 'chrome'),
            ('chromium-browser', 'chromium'),
            ('chromium', 'chromium'),
        ]
        for binary_name, browser_type in chrome_names:
            path = shutil.which(binary_name)
            if path:
                return path, browser_type

        return None, None

    @staticmethod
    def _kill_zombie_chrome():
        """Kill any orphaned Chrome/Chromium processes to free memory"""
        try:
            result = subprocess.run(
                ['pkill', '-f', 'chromium.*--headless'],
                capture_output=True, timeout=5
            )
            # Also kill any orphaned chromedriver processes
            subprocess.run(
                ['pkill', '-f', 'chromedriver'],
                capture_output=True, timeout=5
            )
            time.sleep(1)  # Let OS reclaim memory
        except Exception:
            pass

    def init_driver(self):
        """Initialize Selenium WebDriver with Chrome or Chromium"""
        try:
            # Kill zombie Chrome processes before starting a new one
            self._kill_zombie_chrome()

            chrome_binary, browser_type = self._detect_chrome_binary()
            if not chrome_binary:
                raise Exception(
                    "No Chrome or Chromium binary found. Install google-chrome-stable "
                    "or chromium-browser, or set CHROME_BINARY_PATH in .env"
                )
            self.logger.info(f"Using browser: {chrome_binary} (type: {browser_type})")

            chrome_options = Options()
            chrome_options.binary_location = chrome_binary

            if Config.HEADLESS_MODE:
                chrome_options.add_argument('--headless=new')

            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')

            # Memory-saving flags for low-RAM environments
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-background-networking')
            chrome_options.add_argument('--disable-default-apps')
            chrome_options.add_argument('--disable-translate')
            chrome_options.add_argument('--disable-sync')
            chrome_options.add_argument('--no-first-run')
            chrome_options.add_argument('--disable-features=VizDisplayCompositor')
            chrome_options.add_argument('--disable-software-rasterizer')
            chrome_options.add_argument('--crash-dumps-dir=/tmp')

            # Use unique temp profile to avoid lock conflicts between runs
            self._user_data_dir = tempfile.mkdtemp(prefix='chrome_scraper_')
            chrome_options.add_argument(f'--user-data-dir={self._user_data_dir}')

            chrome_options.add_argument(
                'user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )

            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            try:
                if browser_type == 'chromium':
                    driver_path = ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install()
                else:
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
                        # Last resort: try system chromedriver
                        system_chromedriver = shutil.which('chromedriver')
                        if system_chromedriver:
                            driver_path = system_chromedriver
                            self.logger.info(f"Using system chromedriver: {driver_path}")
                        else:
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
        """Close the browser and clean up temp profile"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info(f"WebDriver closed for {self.company_name}")
            except Exception as e:
                self.logger.error(f"Error closing WebDriver for {self.company_name}: {e}")
            finally:
                self.driver = None

        # Clean up temp user-data-dir
        if self._user_data_dir and os.path.exists(self._user_data_dir):
            try:
                shutil.rmtree(self._user_data_dir, ignore_errors=True)
            except Exception:
                pass
            self._user_data_dir = None

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
