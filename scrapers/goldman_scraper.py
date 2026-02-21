from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
from datetime import datetime
import re


class GoldmanSachsScraper(BaseScraper):
    """Goldman Sachs 爬虫 - 爬取美国地区的所有 Global Banking & Markets 部门职位"""

    def __init__(self):
        # 配置筛选条件：美国地区 + Global Banking & Markets 部门 + 所有职位类型
        super().__init__(
            company_name='Goldman Sachs',
            source_url='https://higher.gs.com/results?DIVISION=Global%20Banking%20%26%20Markets&JOB_FUNCTION=&LOCATION=Albany|New%20York|Atlanta|Boston|Chicago|Dallas|Houston|Richardson|Detroit|Jersey%20City|Los%20Angeles|Menlo%20Park|Newport%20Beach|San%20Francisco|Miami|West%20Palm%20Beach|Philadelphia|Pittsburgh|Salt%20Lake%20City|Seattle|Washington|Wilmington&page=1&sort=RELEVANCE'
        )

    def scrape_jobs(self):
        """抓取 Goldman Sachs 职位列表（支持多页）"""
        all_jobs = []
        import time

        try:
            # 构建基础URL（移除page参数）
            base_url = self.source_url.split('&page=')[0] if '&page=' in self.source_url else self.source_url.split('?page=')[0]

            page = 1
            max_pages = 10  # 安全限制，避免无限循环

            while page <= max_pages:
                # 构建当前页URL
                current_url = f"{base_url}&page={page}&sort=RELEVANCE"

                self.logger.info(f"Loading page {page}: {current_url}")
                self.driver.get(current_url)

                # 等待页面JavaScript加载完成
                self.logger.info("Waiting for page to load dynamically...")
                time.sleep(20)

                # 滚动页面触发懒加载
                self.scroll_to_bottom(pause_time=3)
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(2)

                # 获取职位元素
                job_elements = self.driver.find_elements(By.CSS_SELECTOR, 'div.gs-uitk-mb-2')

                # 过滤出真正的职位卡片
                valid_job_elements = []
                for elem in job_elements:
                    try:
                        elem.find_element(By.CSS_SELECTOR, 'a[href*="/roles/"]')
                        valid_job_elements.append(elem)
                    except:
                        pass

                self.logger.info(f"Page {page}: Found {len(valid_job_elements)} job cards")

                # 如果当前页没有职位，说明到了最后一页
                if len(valid_job_elements) == 0:
                    self.logger.info(f"No more jobs found. Stopping at page {page}")
                    break

                # 提取当前页的职位
                for idx, job_element in enumerate(valid_job_elements):
                    try:
                        # 提取职位链接
                        link_elem = job_element.find_element(By.CSS_SELECTOR, 'a[href*="/roles/"]')
                        job_url = link_elem.get_attribute('href')
                        if job_url.startswith('/'):
                            job_url = f"https://higher.gs.com{job_url}"

                        # 提取职位标题
                        title = job_element.find_element(By.CSS_SELECTOR, 'span.gs-uitk-c-nv7fiq--text-root').text.strip()

                        # 提取地点
                        location_elem = job_element.find_element(By.CSS_SELECTOR, '[data-testid="location"]')
                        location = location_elem.text.strip()

                        # 尝试提取职级
                        try:
                            experience_level = job_element.find_element(By.CSS_SELECTOR, 'span.gs-uitk-c-d1sssb--text-root').text.strip()
                            experience_level = experience_level.replace('·', '').strip()
                        except:
                            experience_level = ""

                        description = f"Experience Level: {experience_level}" if experience_level else ""

                        job = {
                            'company': self.company_name,
                            'title': title,
                            'location': location,
                            'description': description,
                            'post_date': None,
                            'deadline': None,
                            'source_website': current_url,
                            'job_url': job_url
                        }

                        all_jobs.append(job)
                        self.logger.info(f"Page {page}, Job {idx + 1}: {title[:50]}...")

                    except Exception as e:
                        self.logger.warning(f"Error scraping job on page {page}: {e}")
                        continue

                # 移到下一页
                page += 1

            self.logger.info(f"Completed scraping {len(all_jobs)} jobs across {page-1} pages")

        except Exception as e:
            self.logger.error(f"Error scraping Goldman Sachs jobs: {e}")

        return all_jobs
