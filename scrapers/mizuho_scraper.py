from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
import time


class MizuhoScraper(BaseScraper):
    """Mizuho scraper - Workday platform"""

    def __init__(self):
        super().__init__(
            company_name='Mizuho',
            source_url='https://mizuho.wd1.myworkdayjobs.com/mizuhoamericas?jobFamilyGroup=6c507b7295da107a6615fea08dd99b0d&jobFamilyGroup=6c507b7295da107a6616033fe3bc9b11&jobFamilyGroup=6c507b7295da107a66161886fc069b23&jobFamilyGroup=e2908a27d8a701011ab8cd9b6b4d0000'
        )

    def scrape_jobs(self):
        """Scrape Mizuho job listings"""
        all_jobs = []

        try:
            page = 1
            max_pages = 10  # Safety limit

            while page <= max_pages:
                if page == 1:
                    self.logger.info(f"Loading page {page}: {self.source_url}")
                    self.driver.get(self.source_url)
                else:
                    # Click next button
                    try:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label="next"]')
                        if not next_button.is_enabled():
                            self.logger.info(f"Next button disabled on page {page}, stopping")
                            break

                        self.logger.info(f"Clicking next button to load page {page}")
                        next_button.click()
                    except Exception as e:
                        self.logger.info(f"No next button found, stopping at page {page-1}: {e}")
                        break

                # Wait for page to load
                time.sleep(15)

                # Find all job title links
                title_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[data-automation-id="jobTitle"]')
                self.logger.info(f"Found {len(title_links)} job titles on page {page}")

                if len(title_links) == 0:
                    self.logger.info(f"No jobs found on page {page}, stopping")
                    break

                for idx, title_link in enumerate(title_links):
                    try:
                        # Extract title and link
                        title = title_link.text.strip()
                        job_url = title_link.get_attribute('href')

                        if not title or not job_url:
                            continue

                        # Find parent li container
                        try:
                            parent_li = title_link.find_element(By.XPATH, './ancestor::li')

                            # Extract location (first dd element)
                            try:
                                location_dd = parent_li.find_element(By.TAG_NAME, 'dd')
                                location = location_dd.text.strip()
                            except:
                                location = "United States"

                        except:
                            location = "United States"

                        # Build job dictionary
                        job = {
                            'company': self.company_name,
                            'title': title,
                            'location': location,
                            'description': '',
                            'post_date': None,
                            'deadline': None,
                            'source_website': self.source_url,
                            'job_url': job_url
                        }

                        all_jobs.append(job)
                        self.logger.info(f"Page {page}, Job {idx + 1}: {title[:50]}...")

                    except Exception as e:
                        self.logger.warning(f"Error scraping job {idx + 1} on page {page}: {e}")
                        continue

                page += 1

            self.logger.info(f"Completed scraping {len(all_jobs)} jobs from {page - 1} pages")

        except Exception as e:
            self.logger.error(f"Error scraping Mizuho jobs: {e}")
            import traceback
            traceback.print_exc()

        return all_jobs
