import cloudscraper
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin, quote
from datetime import datetime, timedelta
import random
import re
import concurrent.futures
from pymongo import MongoClient
from enum import Enum

class WorkType(str, Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    CASUAL = "CASUAL"
    INTERNSHIP = "INTERNSHIP"
    FREELANCE = "FREELANCE"
    OTHER = "OTHER"

VALID_WORK_TYPES = {wt.value for wt in WorkType}

class JoraScraper:
    def __init__(self):
        self.jobs = []
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
        ]
        self.session = cloudscraper.create_scraper()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)
        self.total_jobs_scraped = 0
        self.mongo_uri = "mongodb+srv://basanta:Psn3yao4AsSofOKI@cluster1.0cq62.mongodb.net/?retryWrites=true&w=majority&appName=Cluster1"
        self.db_name = "joblistings"
        self.collection_name = "jobs"
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client[self.db_name]
        self.collection = self.db[self.collection_name]

    def normalize_work_type(self, work_type):
        if not work_type:
            return None
        normalized = work_type.upper().strip().replace(" ", "_")
        for wt in WorkType:
            if wt.value in normalized or normalized in wt.value:
                return wt.value
        if "FULL" in normalized or "PERMANENT" in normalized:
            return WorkType.FULL_TIME.value
        elif "PART" in normalized:
            return WorkType.PART_TIME.value
        elif "CONTRACT" in normalized or "FIXED_TERM" in normalized:
            return WorkType.CONTRACT.value
        elif "CASUAL" in normalized:
            return WorkType.CASUAL.value
        elif "INTERN" in normalized:
            return WorkType.INTERNSHIP.value
        elif "FREELANCE" in normalized or "SELF_EMPLOYED" in normalized:
            return WorkType.FREELANCE.value
        return None

    def get_random_headers(self):
        return {
            "User-Agent": random.choice(self.user_agents),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Connection": "keep-alive"
        }

    def print_status(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def parse_salary_text(self, salary_text):
        if not salary_text or "not specified" in salary_text.lower():
            return None, None, None
        salary_text = salary_text.lower().replace(",", "").replace("$", "")
        payable_duration = None
        if "per hour" in salary_text or "an hour" in salary_text:
            payable_duration = "hourly"
        elif "per day" in salary_text or "a day" in salary_text:
            payable_duration = "daily"
        elif "per week" in salary_text or "a week" in salary_text:
            payable_duration = "weekly"
        elif "per month" in salary_text or "a month" in salary_text:
            payable_duration = "monthly"
        elif "per year" in salary_text or "a year" in salary_text or "annual" in salary_text:
            payable_duration = "yearly"
        numbers = re.findall(r'\d+(?:\.\d+)?', salary_text)
        if not numbers:
            return None, None, payable_duration
        if len(numbers) == 1:
            min_salary = max_salary = float(numbers[0])
        else:
            min_salary = float(numbers[0])
            max_salary = float(numbers[1])
        return min_salary, max_salary, payable_duration

    def parse_posted_date(self, text):
        text = text.lower()
        now = datetime.now()
        if 'hour' in text or 'hr' in text:
            num = int(re.search(r'\d+', text).group())
            return (now - timedelta(hours=num)).strftime('%Y-%m-%d')
        elif 'day' in text:
            num = int(re.search(r'\d+', text).group())
            return (now - timedelta(days=num)).strftime('%Y-%m-%d')
        elif 'week' in text:
            num = int(re.search(r'\d+', text).group())
            return (now - timedelta(weeks=num)).strftime('%Y-%m-%d')
        elif 'month' in text:
            num = int(re.search(r'\d+', text).group())
            return (now - timedelta(days=num*30)).strftime('%Y-%m-%d')
        return now.strftime('%Y-%m-%d')

    def get_job_description(self, job_url):
        try:
            response = self.session.get(job_url, headers=self.get_random_headers(), timeout=10)
            if response.status_code != 200:
                return self.default_job_details()

            soup = BeautifulSoup(response.text, 'html.parser')

            employer = "Employer not specified"
            employer_elements = soup.select('span.company, div.company-name, a.company, span.employer-name')
            if employer_elements:
                employer = employer_elements[0].get_text(strip=True)

            salary = None
            work_type = None
            badges = soup.find_all('div', class_='badge -default-badge')
            for badge in badges:
                content = badge.find('div', class_='content')
                if not content:
                    continue
                text = content.get_text(strip=True)
                if '$' in text:
                    salary = text
                elif any(word in text.lower() for word in ["full", "part", "contract", "casual", "temporary", "permanent"]):
                    work_type = text

            work_type = self.normalize_work_type(work_type)
            min_salary, max_salary, payable_duration = self.parse_salary_text(salary)

            date_posted = datetime.now().strftime('%Y-%m-%d')
            date_elements = soup.select('time.date, span.date-posted, div.posted-date')
            if date_elements:
                date_text = date_elements[0].get_text(strip=True)
                date_posted = self.parse_posted_date(date_text)

            description = "No description available"
            summary = "Summary not available"
            description_elements = soup.select('div#job-description-container, div.description, div.job-details')
            if description_elements:
                html_block = description_elements[0]
                description = html_block.decode_contents().strip()
                text_only = html_block.get_text().strip()
                summary = text_only.split('.')[0].strip() + '.' if '.' in text_only else text_only[:200] + '...'

            apply_link = None
            apply_button = soup.select_one('a[data-automation="job-detail-apply-button"]')
            if apply_button and apply_button.has_attr('href'):
                apply_link = apply_button['href']
            else:
                fallback_links = soup.find_all('a', string=re.compile(r'apply', re.I))
                for link in fallback_links:
                    if link and link.has_attr('href'):
                        apply_link = link['href']
                        break

            final_url = urljoin("https://au.jora.com", apply_link) if apply_link else job_url
            try:
                r = self.session.get(final_url, headers=self.get_random_headers(), allow_redirects=True, timeout=10)
                if r.status_code == 200:
                    final_url = r.url
            except Exception as e:
                self.print_status(f"Error resolving final apply URL: {e}")

            return {
                "job_detail": description,
                "summary": summary,
                "work_type": work_type,
                "salary": salary if salary else "Salary not specified",
                "employer": employer,
                "date_posted": date_posted,
                "apply_url": final_url,
                "min_salary": min_salary,
                "max_salary": max_salary,
                "payable_duration": payable_duration
            }

        except Exception as e:
            self.print_status(f"Error getting job details: {str(e)}")
            return self.default_job_details()

    def default_job_details(self):
        return {
            "job_detail": "No description available",
            "summary": "Summary not available",
            "work_type": None,
            "salary": "Salary not specified",
            "employer": "Employer not specified",
            "date_posted": datetime.now().strftime('%Y-%m-%d'),
            "apply_url": "",
            "min_salary": None,
            "max_salary": None,
            "payable_duration": None
        }

    def process_job_listing(self, job, search_keyword, location):
        try:
            title_element = job.select_one('h3.job-title, a.job-title, h2.title, a.job-link, div.job-title')
            if not title_element:
                return None
            title = title_element.get_text(strip=True)
            job_url = title_element.get('href')
            if not job_url:
                return None
            job_url = urljoin('https://au.jora.com', job_url)
            job_id = f"{hash(job_url)}"
            job_detail = self.get_job_description(job_url)
            job_data = {
                "id": job_id,
                "search_keyword": search_keyword,
                "title": title,
                "jobLocation": location,
                "employer": job_detail["employer"],
                "work_type": job_detail["work_type"],
                "salary": job_detail["salary"],
                "min_salary": job_detail.get("min_salary"),
                "max_salary": job_detail.get("max_salary"),
                "payable_duration": job_detail.get("payable_duration"),
                "date_posted": job_detail["date_posted"],
                "job_summary": job_detail["summary"],
                "job_description_html": job_detail["job_detail"],
                "job_url": job_url,
                "apply_url": job_detail["apply_url"],
                "source": "Jora Australia"
            }
            self.total_jobs_scraped += 1
            return job_data
        except Exception as e:
            self.print_status(f"Error processing job: {str(e)}")
            return None

    def scrape_page(self, url, search_keyword, location, page_num):
        try:
            self.print_status(f"Scraping page {page_num} for '{search_keyword}' in {location}")
            response = self.session.get(url, headers=self.get_random_headers(), timeout=10)
            if response.status_code != 200:
                self.print_status(f"Failed to fetch page {page_num} (Status {response.status_code})")
                return False
            soup = BeautifulSoup(response.text, 'html.parser')
            if soup.select_one('div.no-results, div.empty-state, div.no-jobs-found'):
                self.print_status("No more jobs found")
                return False
            job_elements = soup.select('div.result, div.job-card, article.job-result, div.job-item, div.job')
            if not job_elements:
                self.print_status("No job listings found on page")
                return False
            futures = []
            for job in job_elements:
                futures.append(self.executor.submit(self.process_job_listing, job, search_keyword, location))
            page_jobs = 0
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    self.jobs.append(result)
                    page_jobs += 1
            self.print_status(f"Found {page_jobs} jobs on page {page_num}")
            return True
        except Exception as e:
            self.print_status(f"Error scraping page: {str(e)}")
            return False

    def scrape_jobs(self, search_keyword, location="Australia", max_pages=5):
        encoded_keyword = quote(search_keyword)
        encoded_location = quote(location)
        base_url = f"https://au.jora.com/j?q={encoded_keyword}&l={encoded_location}"
        page = 1
        self.print_status(f"\nStarting scrape for '{search_keyword}' in {location}")
        while page <= max_pages:
            url = f"{base_url}&p={page}"
            if not self.scrape_page(url, search_keyword, location, page):
                break
            page += 1
            time.sleep(random.uniform(1, 2))
        self.print_status(f"Completed scrape for '{search_keyword}' in {location}")

    def save_to_mongo(self):
        if not self.jobs:
            self.print_status("No jobs to save")
            return
        try:
            valid_jobs = [
                job for job in self.jobs
                if all(value is not None and value != "" for value in job.values())
                and job.get("work_type") in VALID_WORK_TYPES
            ]
            if not valid_jobs:
                self.print_status("No valid jobs to insert (some had null or empty fields or invalid work_type)")
                return
            self.collection.insert_many(valid_jobs)
            self.print_status(f"Successfully inserted {len(valid_jobs)} jobs into MongoDB collection.")
        except Exception as e:
            self.print_status(f"Failed to insert into MongoDB: {str(e)}")

    def __del__(self):
        self.executor.shutdown(wait=False)
        self.session.close()

if __name__ == "__main__":
    scraper = JoraScraper()
    search_keywords = ["Hotel General Manager",
    "Front Desk Agent",
    "Front Desk Associate",
    "Night Auditor",
    "Catering Sales Manager",
    "Bartender","IT Support Specialist",
    "Network & Systems Administrator",
    "Security Systems Administrator (Remote)",
    "IT Field Support Engineer",
    "Junior Linux Admin",
    "IT Specialist"]
    locations = ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Canberra", "Gold Coast", "Hobart", "Darwin"]

    start_time = time.time()
    for keyword in search_keywords:
        for location in locations:
            scraper.scrape_jobs(keyword, location, max_pages=4)
            time.sleep(random.uniform(1, 2))
    scraper.save_to_mongo()
    elapsed_time = time.time() - start_time
    scraper.print_status(f"\nTotal scraping time: {elapsed_time:.2f} seconds")
