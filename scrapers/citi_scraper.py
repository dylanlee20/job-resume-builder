from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time


class CitiScraper(BaseScraper):
    """Citi 爬虫 - 筛选美国地区的学生和毕业生项目职位"""

    def __init__(self):
        super().__init__(
            company_name='Citi',
            source_url='https://jobs.citi.com/search-jobs'
        )

    def scrape_jobs(self):
        """抓取 Citi 职位列表（支持筛选和分页）"""
        all_jobs = []

        try:
            self.logger.info(f"Loading {self.source_url}")
            self.driver.get(self.source_url)
            time.sleep(10)

            # 关闭 cookie 提示
            try:
                accept_button = self.driver.find_element(By.ID, 'system-ialert-button')
                accept_button.click()
                time.sleep(2)
                self.logger.info("Cookie banner dismissed")
            except Exception as e:
                self.logger.info(f"No cookie banner found: {e}")

            # 应用筛选：United States
            self.logger.info("Applying 'United States' filter...")
            try:
                country_toggle = self.driver.find_element(By.ID, 'country-toggle')
                country_toggle.click()
                time.sleep(2)

                us_checkbox = self.driver.find_element(By.ID, 'country-filter-56')
                us_checkbox.click()
                time.sleep(5)
                self.logger.info("'United States' filter applied")
            except Exception as e:
                self.logger.error(f"Failed to apply United States filter: {e}")
                return all_jobs

            # 应用筛选：Student and Grad Programs
            self.logger.info("Applying 'Student and Grad Programs' filter...")
            try:
                job_level_toggle = self.driver.find_element(By.ID, 'custom_fields.cfcareerlevel-toggle')
                self.driver.execute_script("arguments[0].scrollIntoView(true);", job_level_toggle)
                time.sleep(1)
                job_level_toggle.click()
                time.sleep(2)

                student_checkbox = self.driver.find_element(By.ID, 'custom_fields.cfcareerlevel-filter-3')
                student_checkbox.click()
                time.sleep(5)
                self.logger.info("'Student and Grad Programs' filter applied")
            except Exception as e:
                self.logger.error(f"Failed to apply Student and Grad Programs filter: {e}")
                return all_jobs

            # 获取总页数
            try:
                search_results_section = self.driver.find_element(By.ID, 'search-results')
                total_pages = int(search_results_section.get_attribute('data-total-pages'))
                total_results = int(search_results_section.get_attribute('data-total-results'))
                self.logger.info(f"Total results: {total_results} across {total_pages} pages")
            except Exception as e:
                self.logger.warning(f"Could not get total pages: {e}, assuming 1 page")
                total_pages = 1

            # 遍历所有页面
            current_page = 1
            while current_page <= total_pages:
                self.logger.info(f"Scraping page {current_page}/{total_pages}...")

                # 等待职位列表加载
                time.sleep(3)

                # 获取当前页的职位卡片
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, 'li.sr-job-item')
                self.logger.info(f"Found {len(job_cards)} job cards on page {current_page}")

                for idx, job_card in enumerate(job_cards):
                    try:
                        # 提取职位链接和标题
                        try:
                            link_elem = job_card.find_element(By.CSS_SELECTOR, 'a.sr-job-item__link')
                            job_url = link_elem.get_attribute('href')
                            title = link_elem.text.strip()

                            if not job_url.startswith('http'):
                                job_url = f"https://jobs.citi.com{job_url}"
                        except Exception as e:
                            self.logger.warning(f"Could not extract link/title for job {idx + 1}: {e}")
                            continue

                        # 提取地点
                        try:
                            location = job_card.find_element(By.CSS_SELECTOR, 'span.sr-job-location').text.strip()
                        except:
                            location = ""

                        job = {
                            'company': self.company_name,
                            'title': title,
                            'location': location,
                            'description': 'Student and Grad Programs - United States',
                            'post_date': None,
                            'deadline': None,
                            'source_website': self.source_url,
                            'job_url': job_url
                        }

                        all_jobs.append(job)
                        self.logger.info(f"Page {current_page}, Job {idx + 1}: {title[:50]}...")

                    except Exception as e:
                        self.logger.warning(f"Error scraping job {idx + 1} on page {current_page}: {e}")
                        continue

                # 检查是否有下一页
                if current_page < total_pages:
                    try:
                        # 查找并点击 Next 按钮
                        next_button = self.driver.find_element(By.CSS_SELECTOR, 'a.next')

                        if next_button.is_enabled():
                            # 滚动到按钮位置
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
                            time.sleep(1)

                            # 点击按钮
                            next_button.click()
                            self.logger.info(f"Clicked 'Next' button to go to page {current_page + 1}")
                            time.sleep(5)  # 等待新页面加载
                        else:
                            self.logger.info(f"Next button disabled, stopping at page {current_page}")
                            break
                    except Exception as e:
                        self.logger.warning(f"Could not find or click Next button: {e}")
                        break

                current_page += 1

            self.logger.info(f"Completed scraping {len(all_jobs)} jobs from {current_page - 1} pages")

        except Exception as e:
            self.logger.error(f"Error scraping Citi jobs: {e}")
            import traceback
            traceback.print_exc()

        return all_jobs
