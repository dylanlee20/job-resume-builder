from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
import time


class BarclaysScraper(BaseScraper):
    """Barclays scraper - US positions"""

    def __init__(self):
        super().__init__(
            company_name='Barclays',
            source_url='https://search.jobs.barclays/search-jobs?alcpm=6252001'
        )

    def scrape_jobs(self):
        """Scrape Barclays job listings"""
        all_jobs = []

        try:
            self.logger.info(f"Loading {self.source_url}")
            self.driver.get(self.source_url)
            time.sleep(8)

            # Dismiss any popups/alerts blocking the page
            try:
                # Try to close system-ialert popup
                alert_close = self.driver.find_elements(By.CSS_SELECTOR, '#system-ialert .system-ialert-close-button, .system-ialert-remove-button, [class*="ialert"] button')
                for btn in alert_close:
                    try:
                        self.driver.execute_script("arguments[0].click();", btn)
                        self.logger.info("Dismissed system alert")
                        time.sleep(1)
                    except:
                        pass

                # Also try to remove the element entirely via JS
                self.driver.execute_script("var el = document.getElementById('system-ialert'); if(el) el.remove();")
                time.sleep(1)
            except:
                pass

            # Dismiss cookie banner if present
            try:
                cookie_selectors = ['#onetrust-accept-btn-handler', '.onetrust-close-btn-handler', '[id*="cookie"] button.accept', '.cookie-accept']
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

            # Add Singapore and Hong Kong filters (US is already in URL)
            countries_to_add = ['singapore', 'hong kong']
            for country in countries_to_add:
                try:
                    # Click country filter toggle
                    country_toggle = self.driver.find_element(By.ID, 'country-toggle')
                    self.driver.execute_script("arguments[0].click();", country_toggle)
                    time.sleep(2)

                    # Re-fetch checkboxes each time to avoid stale elements
                    country_checkboxes = self.driver.find_elements(By.CSS_SELECTOR, 'input[id^="country-filter-"]')
                    for checkbox in country_checkboxes:
                        try:
                            label = checkbox.find_element(By.XPATH, './following-sibling::label | ../label')
                            label_text = label.text.lower()
                            if country in label_text:
                                if not checkbox.is_selected():
                                    self.driver.execute_script("arguments[0].click();", checkbox)
                                    self.logger.info(f"Selected: {label.text}")
                                    time.sleep(2)
                                break
                        except:
                            continue

                    # Close filter dropdown and wait for page to update
                    country_toggle = self.driver.find_element(By.ID, 'country-toggle')
                    self.driver.execute_script("arguments[0].click();", country_toggle)
                    time.sleep(3)
                except Exception as e:
                    self.logger.warning(f"Could not add {country} filter: {e}")

            # Get total pages
            try:
                search_results_section = self.driver.find_element(By.ID, 'search-results')
                total_pages = int(search_results_section.get_attribute('data-total-pages') or '1')
                total_results = int(search_results_section.get_attribute('data-total-results') or '0')
                self.logger.info(f"Total results: {total_results} across {total_pages} pages")
            except Exception as e:
                self.logger.warning(f"Could not get total pages: {e}, assuming 1 page")
                total_pages = 1

            # Scrape all pages
            current_page = 1
            max_pages = min(total_pages, 20)  # Safety limit

            while current_page <= max_pages:
                self.logger.info(f"Scraping page {current_page}/{max_pages}...")
                time.sleep(3)

                # Get job cards - try multiple selectors
                job_cards = []
                selectors = [
                    '#search-results-list > ul > li',
                    'section#search-results ul li',
                    'ul.search-results-list > li',
                    'li[data-job-id]',
                    '.search-results li a[href*="/job/"]'
                ]

                for selector in selectors:
                    job_cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if job_cards:
                        self.logger.info(f"Found {len(job_cards)} job cards using: {selector}")
                        break

                if not job_cards:
                    self.logger.warning(f"No job cards found on page {current_page}")
                    # Try getting links directly
                    job_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[href*="/job/"]')
                    self.logger.info(f"Found {len(job_links)} job links directly")

                    for link in job_links:
                        try:
                            job_url = link.get_attribute('href')
                            title = link.text.strip()

                            if not title or not job_url or '/job/' not in job_url:
                                continue

                            # Skip duplicate URLs
                            if any(j['job_url'] == job_url for j in all_jobs):
                                continue

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
                        except:
                            continue
                else:
                    for idx, job_card in enumerate(job_cards):
                        try:
                            # Extract job link and title
                            try:
                                link_elem = job_card.find_element(By.CSS_SELECTOR, 'a[href*="/job/"]')
                                job_url = link_elem.get_attribute('href')
                                title = link_elem.text.strip()

                                if not title:
                                    title = job_card.find_element(By.CSS_SELECTOR, 'h2, h3, .job-title').text.strip()
                            except:
                                continue

                            if not title or not job_url:
                                continue

                            # Extract location
                            try:
                                location = job_card.find_element(By.CSS_SELECTOR, '.job-location, .location, span[class*="location"]').text.strip()
                            except:
                                location = "United States"

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

                            # Skip duplicates
                            if any(j['job_url'] == job_url for j in all_jobs):
                                continue

                            all_jobs.append(job)
                            self.logger.info(f"Job {len(all_jobs)}: {title[:50]}...")

                        except Exception as e:
                            continue

                # Go to next page
                if current_page < max_pages:
                    try:
                        # Use JavaScript to click next to avoid popup blocking
                        next_button = self.driver.find_element(By.CSS_SELECTOR, 'a.next')
                        self.driver.execute_script("arguments[0].click();", next_button)
                        self.logger.info(f"Navigating to page {current_page + 1}")
                        time.sleep(5)
                    except Exception as e:
                        self.logger.warning(f"Could not navigate to next page: {e}")
                        break

                current_page += 1

            self.logger.info(f"Completed scraping {len(all_jobs)} Barclays jobs")

        except Exception as e:
            self.logger.error(f"Error scraping Barclays jobs: {e}")
            import traceback
            traceback.print_exc()

        return all_jobs
