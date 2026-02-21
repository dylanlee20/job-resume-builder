from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
import time
from datetime import datetime


class NomuraScraper(BaseScraper):
    """Nomura 爬虫 - 筛选美国地区的特定部门职位"""

    def __init__(self):
        super().__init__(
            company_name='Nomura',
            source_url='https://nomuracampus.tal.net/vx/lang-en-GB/mobile-0/appcentre-ext/brand-4/xf-3348347fc789/candidate/jobboard/vacancy/1/adv/?f_Item_Opportunity_84825_lk=749&f_Item_Opportunity_408_lk=522954&f_Item_Opportunity_408_lk=522951&f_Item_Opportunity_408_lk=522952&f_Item_Opportunity_408_lk=522953'
        )

    def scrape_jobs(self):
        """抓取 Nomura 职位列表"""
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

                    # 提取地点
                    try:
                        tds = row.find_elements(By.TAG_NAME, 'td')
                        if len(tds) >= 2:
                            location = tds[1].text.strip()
                        else:
                            location = "United States"
                    except:
                        location = "United States"

                    # 提取截止日期
                    try:
                        if len(tds) >= 3:
                            deadline_str = tds[2].text.strip()
                            # 尝试解析日期格式 "30 Jan 2026"
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
            self.logger.error(f"Error scraping Nomura jobs: {e}")
            import traceback
            traceback.print_exc()

        return all_jobs
