from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
from datetime import datetime
import re


class GoldmanSachsInternationalScraper(BaseScraper):
    """Goldman Sachs International 爬虫 - 爬取国际地区的职位（亚太、欧洲、中东）"""

    def __init__(self):
        # 配置筛选条件：国际地区（香港、墨尔本、悉尼、卡尔加里、多伦多、北京、上海、深圳、东京、首尔、奥克兰、新加坡、迪拜、伯明翰、伦敦）
        super().__init__(
            company_name='Goldman Sachs',
            source_url='https://higher.gs.com/results?LOCATION=Hong%20Kong|Melbourne|Sydney|Sydney|Calgary|Toronto|Beijing|Shanghai|Shenzhen|Minato-Ku|Seoul|Auckland|Singapore|Dubai|Birmingham|London&page=1&sort=RELEVANCE'
        )

    def scrape_jobs(self):
        """抓取 Goldman Sachs International 职位列表（支持多页）"""
        all_jobs = []
        import time

        try:
            # 构建基础URL（移除page参数）
            base_url = self.source_url.split('&page=')[0] if '&page=' in self.source_url else self.source_url.split('?page=')[0]

            page = 1
            max_pages = 15  # 安全限制，避免无限循环

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
            self.logger.error(f"Error scraping Goldman Sachs International jobs: {e}")

        return all_jobs
