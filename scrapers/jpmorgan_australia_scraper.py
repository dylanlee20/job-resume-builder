from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import time
import re


class JPMorganAustraliaScraper(BaseScraper):
    """JP Morgan Australia 爬虫 - 筛选澳大利亚悉尼地区的 CIB 职位"""

    def __init__(self):
        super().__init__(
            company_name='JPMorgan',
            source_url='https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs?keyword=CIB&location=Sydney%2C+NSW%2C+Australia&locationId=300000024729598&locationLevel=city&mode=location&radius=25&radiusUnit=KM'
        )

    def scrape_jobs(self):
        """抓取 JP Morgan Australia 职位列表（支持分页）"""
        all_jobs = []

        try:
            # Oracle Cloud 使用 start 参数进行分页，每页20个职位
            base_url = self.source_url
            jobs_per_page = 20
            max_pages = 20  # 安全限制

            page = 0
            consecutive_duplicates = 0  # 连续重复计数
            seen_urls = set()

            while page < max_pages:
                # 构建当前页URL
                start_index = page * jobs_per_page
                if page == 0:
                    current_url = base_url
                else:
                    current_url = f"{base_url}&start={start_index}"

                self.logger.info(f"Loading page {page + 1} (start={start_index}): {current_url}")
                self.driver.get(current_url)
                time.sleep(10)  # 等待页面加载

                # 获取职位卡片
                job_tiles = self.driver.find_elements(By.CSS_SELECTOR, 'div.job-tile')
                self.logger.info(f"Found {len(job_tiles)} job tiles on page {page + 1}")

                if len(job_tiles) == 0:
                    self.logger.info(f"No jobs found on page {page + 1}, stopping")
                    break

                page_new_jobs = 0
                for idx, job_tile in enumerate(job_tiles):
                    try:
                        # 提取职位链接
                        link_elem = job_tile.find_element(By.CSS_SELECTOR, 'a.job-grid-item__link')
                        job_url = link_elem.get_attribute('href')

                        # 检查是否已经爬取过（去重）
                        if job_url in seen_urls:
                            continue

                        seen_urls.add(job_url)
                        page_new_jobs += 1

                        # 提取职位标题
                        try:
                            title_elem = job_tile.find_element(By.CSS_SELECTOR, 'span.job-tile__title')
                            title = title_elem.text.strip()
                        except:
                            self.logger.warning(f"Could not extract title for job {idx + 1}")
                            continue

                        # 提取地点
                        try:
                            # Oracle Cloud 的地点信息在 posting-locations 组件中
                            location_elem = job_tile.find_element(By.CSS_SELECTOR, 'posting-locations span')
                            location = location_elem.text.strip()
                        except:
                            location = "Sydney, NSW, Australia"  # 默认值

                        job = {
                            'company': self.company_name,
                            'title': title,
                            'location': location,
                            'description': 'CIB Positions - Australia',
                            'post_date': None,
                            'deadline': None,
                            'source_website': self.source_url,
                            'job_url': job_url
                        }

                        all_jobs.append(job)
                        self.logger.info(f"Page {page + 1}, Job {idx + 1}: {title[:50]}...")

                    except Exception as e:
                        self.logger.warning(f"Error scraping job {idx + 1} on page {page + 1}: {e}")
                        continue

                # 检查是否有新职位
                if page_new_jobs == 0:
                    consecutive_duplicates += 1
                    self.logger.info(f"No new jobs on page {page + 1} (all duplicates)")

                    # 如果连续2页都是重复的，停止爬取
                    if consecutive_duplicates >= 2:
                        self.logger.info("Two consecutive pages with no new jobs, stopping")
                        break
                else:
                    consecutive_duplicates = 0

                page += 1

            self.logger.info(f"Completed scraping {len(all_jobs)} jobs from {page} pages")

        except Exception as e:
            self.logger.error(f"Error scraping JP Morgan Australia jobs: {e}")
            import traceback
            traceback.print_exc()

        return all_jobs
