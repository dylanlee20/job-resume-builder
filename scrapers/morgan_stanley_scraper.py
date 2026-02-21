from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By


class MorganStanleyScraper(BaseScraper):
    """Morgan Stanley 爬虫 - Students & Graduates positions"""

    def __init__(self):
        super().__init__(
            company_name='Morgan Stanley',
            source_url='https://www.morganstanley.com/careers/career-opportunities-search?opportunity=sg#'
        )

    def scrape_jobs(self):
        """抓取 Morgan Stanley 职位列表 - 支持分页"""
        all_jobs = []
        import time

        try:
            self.logger.info(f"Loading {self.source_url}")
            self.driver.get(self.source_url)

            # Wait for JavaScript to load and execute
            self.logger.info("Waiting for dynamic content to load...")
            time.sleep(20)

            page = 1
            max_pages = 10  # Safety limit

            while page <= max_pages:
                self.logger.info(f"Processing page {page}")

                # Scroll to ensure all content is loaded
                self.scroll_to_bottom(pause_time=2)
                time.sleep(2)

                # Find all job cards using the correct selector
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, 'div.jobcard div.cmp-jobcard')
                self.logger.info(f"Page {page}: Found {len(job_cards)} job cards")

                if len(job_cards) == 0:
                    self.logger.warning(f"No job cards found on page {page}")
                    break

                # Extract jobs from current page
                for idx, job_card in enumerate(job_cards):
                    try:
                        # Extract title
                        title_elem = job_card.find_element(By.CSS_SELECTOR, 'div.cmp-jobcard__title')
                        title = title_elem.text.strip()

                        if not title:
                            continue

                        # Extract location
                        try:
                            location_elem = job_card.find_element(By.CSS_SELECTOR, 'div.cmp-jobcard__location')
                            location = location_elem.text.strip()
                        except:
                            location = "Unknown"

                        # Extract job URL (try multiple selectors)
                        job_url = None
                        try:
                            link_elem = job_card.find_element(By.CSS_SELECTOR, 'a.button--done')
                            job_url = link_elem.get_attribute('href')
                        except:
                            # Fallback to Learn More link
                            try:
                                link_elem = job_card.find_element(By.CSS_SELECTOR, 'a.learn-more')
                                job_url = link_elem.get_attribute('href')
                            except:
                                # Try any link within the job card
                                try:
                                    links = job_card.find_elements(By.TAG_NAME, 'a')
                                    for link in links:
                                        href = link.get_attribute('href')
                                        if href and 'tal.net' in href:
                                            job_url = href
                                            break
                                except:
                                    pass

                        if not job_url:
                            self.logger.warning(f"No URL found for job: {title[:50]}...")
                            continue

                        # Extract role/business area
                        try:
                            role_elem = job_card.find_element(By.CSS_SELECTOR, 'div.cmp-jobcard__role')
                            description = f"Business Area: {role_elem.text.strip()}"
                        except:
                            description = ""

                        # Extract program type
                        try:
                            program_elem = job_card.find_element(By.CSS_SELECTOR, 'div.typeof-event')
                            program_type = program_elem.text.strip().replace('Program Type: ', '')
                            if description:
                                description += f" | {program_type}"
                            else:
                                description = program_type
                        except:
                            pass

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

                        all_jobs.append(job)
                        self.logger.info(f"Page {page}, Job {len(all_jobs)}: {title[:60]}... - {location}")

                    except Exception as e:
                        self.logger.warning(f"Error scraping job card {idx + 1} on page {page}: {e}")
                        continue

                # After processing all jobs on current page, try to go to next page
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, 'a.arrow.next')
                    if next_button.is_displayed() and next_button.is_enabled():
                        self.logger.info(f"Clicking next button to go to page {page + 1}")
                        # Use JavaScript click to avoid interception issues
                        self.driver.execute_script("arguments[0].click();", next_button)
                        time.sleep(7)  # Wait longer for next page to load
                        page += 1
                    else:
                        self.logger.info("Next button not available, reached last page")
                        break
                except Exception as e:
                    self.logger.info(f"No more pages available: {e}")
                    break

            self.logger.info(f"Successfully scraped {len(all_jobs)} jobs across {page} pages")

        except Exception as e:
            self.logger.error(f"Error scraping Morgan Stanley jobs: {e}")
            import traceback
            traceback.print_exc()

        return all_jobs
