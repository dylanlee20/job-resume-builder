from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
import time


class BNPParibasScraper(BaseScraper):
    """BNP Paribas 爬虫 - 筛选美国地区的实习职位"""

    def __init__(self):
        super().__init__(
            company_name='BNP Paribas',
            source_url='https://group.bnpparibas/en/careers/all-job-offers?page=1&type=28%7C2134&rh_entity=94&country=10'
        )

    def scrape_jobs(self):
        """抓取 BNP Paribas 职位列表（支持分页）"""
        all_jobs = []

        try:
            # 分页爬取
            page = 1
            max_pages = 20  # 安全限制

            while page <= max_pages:
                # 构建当前页URL
                current_url = self.source_url.replace('page=1', f'page={page}')

                self.logger.info(f"Loading page {page}: {current_url}")
                self.driver.get(current_url)
                time.sleep(12)  # 等待页面加载

                # 滚动页面以触发懒加载
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(3)
                self.driver.execute_script("window.scrollTo(0, 0);")
                time.sleep(2)

                # 直接查找所有职位标题元素
                title_elements = self.driver.find_elements(By.CSS_SELECTOR, 'h3.title-4')
                self.logger.info(f"Found {len(title_elements)} job titles on page {page}")

                if len(title_elements) == 0:
                    self.logger.info(f"No jobs found on page {page}, stopping")
                    break

                for idx, title_elem in enumerate(title_elements):
                    try:
                        # 滚动到元素可见区域，触发渲染
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", title_elem)
                        time.sleep(0.5)

                        # 提取职位标题
                        title = title_elem.text.strip()
                        if not title:
                            self.logger.warning(f"Empty title for job {idx + 1}")
                            continue

                        # 获取父级链接元素
                        try:
                            # 向上查找 <a> 标签
                            link_elem = title_elem.find_element(By.XPATH, './ancestor::a[@class="card-link"]')
                            job_url = link_elem.get_attribute('href')

                            if job_url and job_url.startswith('/'):
                                job_url = f"https://group.bnpparibas{job_url}"

                            # 检查是否为职位链接
                            if not job_url or '/job-offer/' not in job_url:
                                continue

                            # 提取地点（在同一个链接内）
                            try:
                                location_elem = link_elem.find_element(By.CSS_SELECTOR, '.offer-location')
                                location = location_elem.text.strip()
                            except:
                                location = "United States"

                            # 提取职位类型
                            try:
                                type_elem = link_elem.find_element(By.CSS_SELECTOR, '.offer-type')
                                job_type = type_elem.text.strip()
                            except:
                                job_type = ""

                            job = {
                                'company': self.company_name,
                                'title': title,
                                'location': location,
                                'description': job_type,
                                'post_date': None,
                                'deadline': None,
                                'source_website': self.source_url,
                                'job_url': job_url
                            }

                            all_jobs.append(job)
                            self.logger.info(f"Page {page}, Job {idx + 1}: {title[:50]}...")

                        except Exception as e:
                            self.logger.warning(f"Could not find parent link for job {idx + 1}: {e}")
                            continue

                    except Exception as e:
                        self.logger.warning(f"Error scraping job {idx + 1} on page {page}: {e}")
                        continue

                # 检查是否有下一页
                try:
                    next_button = self.driver.find_element(By.CSS_SELECTOR, '[aria-label*="next"]')
                    if next_button.is_enabled():
                        page += 1
                    else:
                        self.logger.info("Next button disabled, stopping")
                        break
                except:
                    self.logger.info("No next button found, stopping")
                    break

            self.logger.info(f"Completed scraping {len(all_jobs)} jobs from {page} pages")

        except Exception as e:
            self.logger.error(f"Error scraping BNP Paribas jobs: {e}")
            import traceback
            traceback.print_exc()

        return all_jobs
