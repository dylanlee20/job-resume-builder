from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
import time


class HSBCScraper(BaseScraper):
    """HSBC scraper - Students and Graduates programmes"""

    def __init__(self):
        super().__init__(
            company_name='HSBC',
            source_url='https://www.hsbc.com/careers/students-and-graduates/find-a-programme?page=1&location=hong-kong-sar|mainland-china|singapore|usa'
        )

    def scrape_jobs(self):
        """Scrape HSBC job listings"""
        all_jobs = []

        try:
            self.logger.info(f"Loading {self.source_url}")
            self.driver.get(self.source_url)
            time.sleep(15)

            # Dismiss cookie banner if present
            try:
                cookie_selectors = ['#onetrust-accept-btn-handler', '#accept-cookies', '.cookie-accept', 'button[class*="accept"]']
                for selector in cookie_selectors:
                    try:
                        btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                        self.driver.execute_script("arguments[0].click();", btn)
                        self.logger.info("Cookie banner dismissed")
                        time.sleep(2)
                        break
                    except:
                        continue
            except:
                pass

            # Click "Load more" to get all results
            max_load_more = 5
            for _ in range(max_load_more):
                try:
                    load_more = self.driver.find_element(By.CSS_SELECTOR, 'button[class*="load-more"], .load-more, button:contains("Load more")')
                    if load_more.is_displayed():
                        self.driver.execute_script("arguments[0].click();", load_more)
                        self.logger.info("Clicked Load more")
                        time.sleep(3)
                    else:
                        break
                except:
                    break

            # Scroll to load all content
            for _ in range(3):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)

            # Look for programme links - HSBC uses hsbcearlycareers.groupgti.com domain
            job_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="hsbcearlycareers.groupgti.com"]')
            self.logger.info(f"Found {len(job_links)} programme links (groupgti.com)")

            if not job_links:
                # Try alternate selectors
                alternate_selectors = [
                    '.program-text__link a',
                    '.in-page-link',
                    'a[href*="/students-and-graduates/"]',
                    '[class*="program"] a',
                    '[class*="vacancy"] a'
                ]
                for selector in alternate_selectors:
                    job_links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if job_links:
                        self.logger.info(f"Found {len(job_links)} links using: {selector}")
                        break

            # Process all job links
            for link in job_links:
                try:
                    href = link.get_attribute('href')
                    text = link.text.strip()

                    # Skip empty or invalid
                    if not href:
                        continue

                    # Only accept groupgti.com links (actual programme pages)
                    if 'groupgti.com' not in href:
                        continue

                    # Try to get title from various sources
                    if not text or len(text) < 5:
                        # Try parent element
                        try:
                            parent = link.find_element(By.XPATH, '..')
                            text = parent.text.strip().split('\n')[0]
                        except:
                            pass

                    if not text or len(text) < 5:
                        # Try grandparent
                        try:
                            grandparent = link.find_element(By.XPATH, '../..')
                            lines = grandparent.text.strip().split('\n')
                            # Find first line that looks like a title (not just a button text)
                            for line in lines:
                                line = line.strip()
                                if len(line) > 10 and 'view' not in line.lower() and 'apply' not in line.lower():
                                    text = line
                                    break
                        except:
                            pass

                    if not text or len(text) < 5:
                        # Extract title from URL slug
                        try:
                            # URL format: .../programme-name-location/id/apply
                            slug = href.split('/')[-3]
                            text = slug.replace('-', ' ').title()
                        except:
                            continue

                    # Clean up title - take first line if multiline
                    if '\n' in text:
                        text = text.split('\n')[0]

                    # Skip navigation items
                    skip_texts = ['view vacancy', 'apply now', 'learn more', 'read more', 'talent community']
                    if any(skip in text.lower() for skip in skip_texts):
                        continue

                    # Skip duplicates
                    if any(j['job_url'] == href for j in all_jobs):
                        continue

                    # Extract location from URL or default
                    location = 'Global'
                    if 'hong-kong' in href.lower():
                        location = 'Hong Kong'
                    elif 'singapore' in href.lower():
                        location = 'Singapore'
                    elif 'china' in href.lower() or 'mainland' in href.lower():
                        location = 'Mainland China'
                    elif 'usa' in href.lower() or 'united-states' in href.lower():
                        location = 'USA'

                    job = {
                        'company': self.company_name,
                        'title': text,
                        'location': location,
                        'description': '',
                        'post_date': None,
                        'deadline': None,
                        'source_website': self.source_url,
                        'job_url': href
                    }
                    all_jobs.append(job)
                    self.logger.info(f"Job {len(all_jobs)}: {text[:60]}...")

                except:
                    continue

            self.logger.info(f"Completed scraping {len(all_jobs)} HSBC jobs")

        except Exception as e:
            self.logger.error(f"Error scraping HSBC jobs: {e}")
            import traceback
            traceback.print_exc()

        return all_jobs
