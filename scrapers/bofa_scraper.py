from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
import time


class BofAScraper(BaseScraper):
    """Bank of America scraper - US Students/Campus positions"""

    def __init__(self):
        super().__init__(
            company_name='Bank of America',
            source_url='https://careers.bankofamerica.com/en-us/students/job-search?ref=search&rows=100&search=getAllJobs'
        )

    def scrape_jobs(self):
        """Scrape Bank of America job listings"""
        all_jobs = []
        seen_urls = set()

        try:
            # Load with high row count to get all jobs at once
            self.logger.info(f"Loading {self.source_url}")
            self.driver.get(self.source_url)
            time.sleep(12)

            # Dismiss cookie banner if present
            try:
                cookie_btn = self.driver.find_element(By.CSS_SELECTOR, '#onetrust-accept-btn-handler, .cookie-accept, [class*="cookie"] button')
                self.driver.execute_script("arguments[0].click();", cookie_btn)
                self.logger.info("Cookie banner dismissed")
                time.sleep(2)
            except:
                pass

            # Scroll to load all content
            for _ in range(5):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)

            # Look for job links with /job-detail/ pattern
            job_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/job-detail/"]')
            self.logger.info(f"Found {len(job_links)} job-detail links")

            for link in job_links:
                try:
                    job_url = link.get_attribute('href')
                    title = link.text.strip()

                    # Skip empty or invalid
                    if not job_url or '/job-detail/' not in job_url:
                        continue
                    if not title or len(title) < 3:
                        continue

                    # Skip navigation links
                    skip_words = ['search', 'filter', 'sign in', 'log in', 'next', 'previous', 'page']
                    if any(skip in title.lower() for skip in skip_words):
                        continue

                    # Skip duplicates using URL
                    if job_url in seen_urls:
                        continue
                    seen_urls.add(job_url)

                    job = {
                        'company': self.company_name,
                        'title': title,
                        'location': 'United States',
                        'description': '',
                        'post_date': None,
                        'deadline': None,
                        'source_website': self.source_url,
                        'job_url': job_url
                    }
                    all_jobs.append(job)
                    self.logger.info(f"Job {len(all_jobs)}: {title[:60]}...")

                except Exception as e:
                    continue

            self.logger.info(f"Completed scraping {len(all_jobs)} Bank of America jobs")

        except Exception as e:
            self.logger.error(f"Error scraping Bank of America jobs: {e}")
            import traceback
            traceback.print_exc()

        return all_jobs
