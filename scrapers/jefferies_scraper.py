from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
import time
from datetime import datetime


class JefferiesScraper(BaseScraper):
    """Jefferies scraper - Taleo platform"""

    def __init__(self):
        super().__init__(
            company_name='Jefferies',
            source_url='https://jefferies.tal.net/vx/lang-en-GB/mobile-0/appcentre-ext/brand-4/xf-5d566aeb2688/candidate/jobboard/vacancy/2/adv/?f_Item_Opportunity_84825_lk=749&f_Item_Opportunity_84825_lk=765'
        )

    def scrape_jobs(self):
        """Scrape Jefferies job listings"""
        all_jobs = []

        try:
            self.logger.info(f"Loading {self.source_url}")
            self.driver.get(self.source_url)

            # Wait for the job table to appear
            time.sleep(25)  # Give more time for JavaScript to load

            # Scroll down to trigger lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)

            # Try the standard Taleo selector first
            job_rows = self.driver.find_elements(By.CSS_SELECTOR, 'tr.search_res.details_row')

            if len(job_rows) == 0:
                self.logger.info("Standard selector didn't work, trying alternatives...")
                # Try alternative selectors
                selectors = [
                    'tr.search_res',
                    'table tbody tr',
                    'tr[class*="details"]',
                ]

                for selector in selectors:
                    job_rows = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if len(job_rows) > 5:  # More than 5 to avoid header rows
                        self.logger.info(f"Found {len(job_rows)} rows using selector: {selector}")
                        break

            self.logger.info(f"Found {len(job_rows)} job rows")

            if len(job_rows) == 0:
                self.logger.warning("No jobs found")
                return all_jobs

            for idx, row in enumerate(job_rows):
                try:
                    # Extract job title and link - try multiple selectors
                    title = None
                    job_url = None
                    link_selectors = ['a.subject', 'a', 'h3 a', 'div.job-title a', '[data-automation-id="jobTitle"]']

                    for link_selector in link_selectors:
                        try:
                            link_elem = row.find_element(By.CSS_SELECTOR, link_selector)
                            title = link_elem.text.strip()
                            job_url = link_elem.get_attribute('href')
                            if title and job_url:
                                break
                        except:
                            continue

                    if not title or not job_url:
                        # Try getting text directly from the row
                        try:
                            title = row.text.strip().split('\n')[0] if row.text else None
                            # Try to find any link in the row
                            links = row.find_elements(By.TAG_NAME, 'a')
                            if links:
                                job_url = links[0].get_attribute('href')
                        except:
                            pass

                    if not title or not job_url:
                        self.logger.warning(f"Could not extract title/link for job {idx + 1}")
                        continue

                    # Extract location
                    try:
                        tds = row.find_elements(By.TAG_NAME, 'td')
                        if len(tds) >= 2:
                            location = tds[1].text.strip()
                        else:
                            location = "United States"
                    except:
                        location = "United States"

                    # Extract deadline
                    try:
                        if len(tds) >= 3:
                            deadline_str = tds[2].text.strip()
                            # Try to parse date format "30 Jan 2026"
                            try:
                                deadline = datetime.strptime(deadline_str, "%d %b %Y")
                            except:
                                deadline = None
                        else:
                            deadline = None
                    except:
                        deadline = None

                    job = {
                        'company': self.company_name,
                        'title': title,
                        'location': location,
                        'description': '',
                        'post_date': None,
                        'deadline': deadline,
                        'source_website': self.source_url,
                        'job_url': job_url
                    }

                    all_jobs.append(job)
                    self.logger.info(f"Job {idx + 1}: {title[:50]}...")

                except Exception as e:
                    self.logger.warning(f"Error scraping job {idx + 1}: {e}")
                    continue

            self.logger.info(f"Completed scraping {len(all_jobs)} jobs")

        except Exception as e:
            self.logger.error(f"Error scraping Jefferies jobs: {e}")
            import traceback
            traceback.print_exc()

        return all_jobs
