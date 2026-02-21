from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By


class DeutscheBankScraper(BaseScraper):
    """Deutsche Bank 爬虫"""

    def __init__(self):
        super().__init__(
            company_name='Deutsche Bank',
            source_url='https://careers.db.com/students-graduates/index?language_id=1#/graduate/'
        )

    def scrape_jobs(self):
        """抓取 Deutsche Bank 职位列表"""
        jobs = []

        try:
            self.logger.info(f"Loading {self.source_url}")
            self.driver.get(self.source_url)
            self.random_delay()

            self.wait_for_element(By.CSS_SELECTOR, '.job, .vacancy, .position', timeout=15)
            self.scroll_to_bottom(pause_time=2)

            job_elements = self.driver.find_elements(By.CSS_SELECTOR, '.job, .vacancy, .position, [data-position]')

            self.logger.info(f"Found {len(job_elements)} job elements")

            for idx, job_element in enumerate(job_elements):
                try:
                    title = job_element.find_element(By.CSS_SELECTOR, 'h2, h3, .title, a.job-title').text.strip()
                    job_url = job_element.find_element(By.CSS_SELECTOR, 'a').get_attribute('href')
                    location = job_element.find_element(By.CSS_SELECTOR, '.location, .job-location').text.strip()

                    try:
                        description = job_element.find_element(By.CSS_SELECTOR, '.description, p').text.strip()
                    except:
                        description = ""

                    job = {
                        'company': self.company_name,
                        'title': title,
                        'location': location,
                        'description': description,
                        'post_date': None,
                        'deadline': None,
                        'source_website': self.source_url,
                        'job_url': job_url
                    }

                    jobs.append(job)

                except Exception as e:
                    self.logger.warning(f"Error scraping job element {idx + 1}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error scraping Deutsche Bank jobs: {e}")

        return jobs
