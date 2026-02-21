from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import time
import re


class JPMorganHongKongScraper(BaseScraper):
    """JP Morgan Hong Kong 爬虫 - 筛选香港地区的职位"""

    def __init__(self):
        super().__init__(
            company_name='JPMorgan',
            source_url='https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs?location=Hong+Kong&locationId=300000000289330&locationLevel=country&mode=location'
        )

    def scrape_jobs(self):
        """抓取 JP Morgan Hong Kong 职位列表（支持分页）"""
        all_jobs = []

        try:
            # Oracle Cloud 使用无限滚动加载所有职位
            self.logger.info(f"Loading page: {self.source_url}")
            self.driver.get(self.source_url)
            time.sleep(5)  # 初始页面加载等待

            # 处理无限滚动加载 - 滚动到底部多次以加载所有职位
            last_height = 0
            scroll_attempts = 0
            max_scroll_attempts = 15  # 最多滚动15次
            seen_urls = set()

            while scroll_attempts < max_scroll_attempts:
                # 滚动到页面底部
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)  # 等待新内容加载

                # 检查页面高度是否变化
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                job_tiles = self.driver.find_elements(By.CSS_SELECTOR, 'div.job-tile')

                self.logger.info(f"Scroll attempt {scroll_attempts + 1}: Found {len(job_tiles)} job tiles, height {new_height}")

                if new_height == last_height:
                    # 页面高度没变化，可能已经加载完所有内容
                    break

                last_height = new_height
                scroll_attempts += 1

            # 最终获取所有职位卡片
            job_tiles = self.driver.find_elements(By.CSS_SELECTOR, 'div.job-tile')
            self.logger.info(f"After scrolling, found {len(job_tiles)} total job tiles")

            if len(job_tiles) == 0:
                self.logger.info("No jobs found")
                return []

            all_jobs = []
            for idx, job_tile in enumerate(job_tiles):
                try:
                    # 提取职位链接
                    link_elem = job_tile.find_element(By.CSS_SELECTOR, 'a.job-grid-item__link')
                    job_url = link_elem.get_attribute('href')

                    # 检查是否已经爬取过（去重）
                    if job_url in seen_urls:
                        continue

                    seen_urls.add(job_url)

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
                        location = "Hong Kong"  # 默认值

                    job = {
                        'company': self.company_name,
                        'title': title,
                        'location': location,
                        'description': 'Positions - Hong Kong',
                        'post_date': None,
                        'deadline': None,
                        'source_website': self.source_url,
                        'job_url': job_url
                    }

                    all_jobs.append(job)
                    self.logger.info(f"Job {idx + 1}: {title[:50]}...")

                except Exception as e:
                    self.logger.warning(f"Error scraping job {idx + 1}: {e}")
                    continue

            self.logger.info(f"Completed scraping {len(all_jobs)} unique jobs")

        except Exception as e:
            self.logger.error(f"Error scraping JP Morgan Hong Kong jobs: {e}")
            import traceback
            traceback.print_exc()

        return all_jobs
