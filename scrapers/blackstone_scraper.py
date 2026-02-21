from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
import time


class BlackstoneScraper(BaseScraper):
    """Blackstone 爬虫 - Workday 平台"""

    def __init__(self):
        super().__init__(
            company_name='Blackstone',
            source_url='https://blackstone.wd1.myworkdayjobs.com/en-US/Blackstone_Campus_Careers?locations=ef375a2335bb0101284ca9065e1f6f2b&locations=9d4c631a9cd501ef51ff910af90138e3&locations=ef375a2335bb019369c586065e1f3d2b&locations=ef375a2335bb01d8c87897065e1f562b&locations=1bf5259d5ff60172b4ac9e926bdb60af&locations=ef375a2335bb01f2aacb0a075e1ff62b&locations=ef375a2335bb01d5993383065e1f382b'
        )

    def scrape_jobs(self):
        """抓取 Blackstone 职位列表"""
        all_jobs = []

        try:
            page = 1
            max_pages = 10  # 安全限制

            while page <= max_pages:
                if page == 1:
                    self.logger.info(f"Loading page {page}: {self.source_url}")
                    self.driver.get(self.source_url)
                else:
                    # 点击下一页按钮
                    try:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, 'button[aria-label="next"]')
                        if not next_button.is_enabled():
                            self.logger.info(f"Next button disabled on page {page}, stopping")
                            break

                        self.logger.info(f"Clicking next button to load page {page}")
                        next_button.click()
                    except Exception as e:
                        self.logger.info(f"No next button found, stopping at page {page-1}: {e}")
                        break

                # 等待页面加载
                time.sleep(15)

                # 查找所有职位标题链接
                title_links = self.driver.find_elements(By.CSS_SELECTOR, 'a[data-automation-id="jobTitle"]')
                self.logger.info(f"Found {len(title_links)} job titles on page {page}")

                if len(title_links) == 0:
                    self.logger.info(f"No jobs found on page {page}, stopping")
                    break

                for idx, title_link in enumerate(title_links):
                    try:
                        # 提取标题和链接
                        title = title_link.text.strip()
                        job_url = title_link.get_attribute('href')

                        if not title or not job_url:
                            continue

                        # 查找父级 li 容器
                        try:
                            parent_li = title_link.find_element(By.XPATH, './ancestor::li')

                            # 提取地点（第一个 dd 元素）
                            try:
                                location_dd = parent_li.find_element(By.TAG_NAME, 'dd')
                                location = location_dd.text.strip()
                            except:
                                location = "United States"

                        except:
                            location = "United States"

                        # 构建职位字典
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

                        all_jobs.append(job)
                        self.logger.info(f"Page {page}, Job {idx + 1}: {title[:50]}...")

                    except Exception as e:
                        self.logger.warning(f"Error scraping job {idx + 1} on page {page}: {e}")
                        continue

                page += 1

            self.logger.info(f"Completed scraping {len(all_jobs)} jobs from {page - 1} pages")

        except Exception as e:
            self.logger.error(f"Error scraping Blackstone jobs: {e}")
            import traceback
            traceback.print_exc()

        return all_jobs
