from scrapers.base_scraper import BaseScraper
from selenium.webdriver.common.by import By
import time
import json
import html
import re


class UBSScraper(BaseScraper):
    """UBS 爬虫 - 筛选指定地区的实习职位"""

    def __init__(self):
        super().__init__(
            company_name='UBS',
            source_url='https://jobs.ubs.com/TGnewUI/Search/home/HomeWithPreLoad?partnerid=25008&siteid=5131&PageType=searchResults&SearchType=linkquery&LinkID=15700#keyWordSearch=&locationSearch=&City=Chicago_or_Hong%20Kong%20SAR_or_New%20York_or_San%20Francisco'
        )

    def scrape_jobs(self):
        """抓取 UBS 职位列表（从 JSON 数据中提取）"""
        all_jobs = []

        try:
            self.logger.info(f"Loading {self.source_url}")
            self.driver.get(self.source_url)

            # 等待页面加载完成
            time.sleep(30)

            # 查找隐藏的 JSON 数据
            self.logger.info("Extracting job data from preLoadJSON...")
            try:
                json_input = self.driver.find_element(By.ID, 'preLoadJSON')
                json_value = json_input.get_attribute('value')

                # 解码 HTML 实体
                decoded_json = html.unescape(json_value)

                # 解析 JSON
                data = json.loads(decoded_json)

                # 提取职位列表
                if 'searchResultsResponse' in data and 'Jobs' in data['searchResultsResponse']:
                    job_list = data['searchResultsResponse']['Jobs']['Job']
                    self.logger.info(f"Found {len(job_list)} jobs in JSON data")

                    for idx, job_data in enumerate(job_list):
                        try:
                            # 提取 Questions 字段
                            questions = job_data.get('Questions', [])
                            q_dict = {q['QuestionName']: q['Value'] for q in questions}

                            # 提取关键字段
                            req_id = q_dict.get('reqid', '')
                            title = q_dict.get('jobtitle', '')
                            location = q_dict.get('formtext23', '')  # Primary location
                            department = q_dict.get('formtext21', '')  # Department/function
                            description = q_dict.get('jobdescription', '')

                            # 清理 HTML 标签
                            description_clean = re.sub(r'<[^>]+>', ' ', description)
                            description_clean = re.sub(r'\s+', ' ', description_clean).strip()

                            # 构建职位 URL
                            job_url = f"https://jobs.ubs.com/TGnewUI/Search/home/HomeWithPreLoad?partnerid=25008&siteid=5131&PageType=JobDetails&jobid={req_id}"

                            job = {
                                'company': self.company_name,
                                'title': title,
                                'location': location,
                                'description': f"{department} - {description_clean[:200]}..." if description_clean else department,
                                'post_date': None,
                                'deadline': None,
                                'source_website': self.source_url,
                                'job_url': job_url
                            }

                            all_jobs.append(job)
                            self.logger.info(f"Job {idx + 1}: {title[:50]}...")

                        except Exception as e:
                            self.logger.warning(f"Error processing job {idx + 1}: {e}")
                            continue

                else:
                    self.logger.warning("No jobs found in JSON data")

            except Exception as e:
                self.logger.error(f"Failed to extract JSON data: {e}")

            self.logger.info(f"Completed scraping {len(all_jobs)} jobs")

        except Exception as e:
            self.logger.error(f"Error scraping UBS jobs: {e}")
            import traceback
            traceback.print_exc()

        return all_jobs
