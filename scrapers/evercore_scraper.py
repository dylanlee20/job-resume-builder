from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
import time
from datetime import datetime


class EvercoreScraper(BaseScraper):
    """Evercore 爬虫 - 筛选美国地区的学生和毕业生职位"""

    def __init__(self):
        super().__init__(
            company_name='Evercore',
            source_url='https://evercore.tal.net/vx/lang-en-GB/mobile-0/channel-1/appcentre-ext/brand-6/candidate/jobboard/vacancy/2/adv/'
        )

    def scrape_jobs(self):
        """抓取 Evercore 职位列表"""
        all_jobs = []

        try:
            self.logger.info(f"Loading {self.source_url}")
            self.driver.get(self.source_url)
            time.sleep(15)  # 等待页面加载

            # 获取职位表格中的所有行
            job_rows = self.driver.find_elements(By.CSS_SELECTOR, 'tr.search_res.details_row')
            self.logger.info(f"Found {len(job_rows)} job rows")

            if len(job_rows) == 0:
                self.logger.warning("No jobs found")
                return all_jobs

            for idx, row in enumerate(job_rows):
                try:
                    # 提取职位标题和链接
                    try:
                        link_elem = row.find_element(By.CSS_SELECTOR, 'a.subject')
                        title = link_elem.text.strip()
                        job_url = link_elem.get_attribute('href')
                    except Exception as e:
                        self.logger.warning(f"Could not extract title/link for job {idx + 1}: {e}")
                        continue

                    # 提取截止日期（第2列）
                    try:
                        tds = row.find_elements(By.TAG_NAME, 'td')
                        if len(tds) >= 2:
                            deadline_str = tds[1].text.strip()
                            # 尝试解析日期格式 "1 Feb 2026"
                            try:
                                deadline = datetime.strptime(deadline_str, "%d %b %Y")
                            except:
                                deadline = None
                        else:
                            deadline = None
                    except:
                        deadline = None

                    # Evercore 表格没有地点列，从标题推断或默认为 Americas
                    location = "United States"
                    if "New York" in title:
                        location = "New York"
                    elif "Chicago" in title:
                        location = "Chicago"
                    elif "San Francisco" in title:
                        location = "San Francisco"
                    elif "Los Angeles" in title:
                        location = "Los Angeles"

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
            self.logger.error(f"Error scraping Evercore jobs: {e}")
            import traceback
            traceback.print_exc()

        return all_jobs
