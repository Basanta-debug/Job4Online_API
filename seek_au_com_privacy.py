import requests
from bs4 import BeautifulSoup
import time
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

# **🔹 MongoDB Setup**
def get_db():
    """Connect to MongoDB and return the database."""
    try:
       
        client = MongoClient(os.getenv("MONGO_URI"), serverSelectionTimeoutMS=5000)
        client.server_info()  # Test the connection
        db = client.joblistings  # Replace with your database name
        print("✅ Connected to MongoDB")
        return db
    except Exception as e:
        print("❌ Failed to connect to MongoDB:", e)
        return None

def get_existing_job_ids():
    """Fetch existing Job IDs from MongoDB to prevent duplicates."""
    db = get_db()
    if db is None:
        return set()
    
    collection = db.jobs  # Replace with your collection name
    try:
        existing_job_ids = set(doc["id"] for doc in collection.find({}, {"id": 1}))
        return existing_job_ids
    except Exception as e:
        print("⚠️ Error fetching existing job IDs:", e)
        return set()

def get_job_description(job_url):
    """Fetch job description from the job listing page."""
    if not job_url:
        return "No job URL provided"

    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(job_url, headers=headers)
    
    if response.status_code != 200:
        print(f"⚠️ Failed to fetch job description: {job_url}")
        return "Failed to retrieve description"
    
    soup = BeautifulSoup(response.text, 'html.parser')
    job_detail = soup.select_one('[data-automation="jobAdDetails"]')

    work_type = soup.select_one('[data-automation="job-detail-work-type"]')

    return {
        "job_detail": job_detail.text.strip() if job_detail else "No description available",
        "work_type": work_type.text.strip() if work_type else "No work type available"
    }

def get_job_listings(search_keyword):
    """Scrape job listings from Seek and return as a list."""
    base_url = f"https://www.seek.com.au/{search_keyword.replace(' ', '-')}-jobs"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    response = requests.get(base_url, headers=headers)
    if response.status_code != 200:
        print(f"⚠️ Failed to fetch {base_url}")
        return []
    
    soup = BeautifulSoup(response.text, 'html.parser')
    total_jobs_text = soup.select_one('[data-automation="totalJobsCount"]')
    total_jobs = int(total_jobs_text.text.replace(',', '')) if total_jobs_text else 0
    print(f"✅ Total jobs found: {total_jobs} for '{search_keyword}'")

    jobs = []
    total_pages = min((total_jobs // 22) + 1, 5)  # Limit to first 5 pages
    existing_job_ids = get_existing_job_ids()

    for page in range(1, total_pages + 1):
        print(f"🔄 Scraping page {page} of {total_pages} for '{search_keyword}'")
        page_url = f"{base_url}?page={page}" if page > 1 else base_url
        response = requests.get(page_url, headers=headers)
        
        if response.status_code != 200:
            print(f"⚠️ Failed to fetch {page_url}")
            continue
        
        soup = BeautifulSoup(response.text, 'html.parser')
        job_elements = soup.find_all('article')

        for job in job_elements:
            id = job.get('data-job-id', "").strip()  # Ensure it's a string
            if not id or id in existing_job_ids:  # Skip duplicates
                continue
            
            
            title = job.get('aria-label', "").strip()
            jobLocation = job.select_one('[data-automation="jobLocation"]')
            employer = job.select_one('a[data-automation="jobCompany"]')
            
            salary = job.select_one('[data-automation="jobSalary"]')
            date_posted = job.select_one('[data-automation="jobListingDate"]')
            job_link = job.select_one('a[data-automation="jobTitle"]')
            
            job_url = f"https://www.seek.com.au{job_link['href']}" if job_link else None
            job_detail = get_job_description(job_url) if job_url else "No job URL"
            
            job_description =  job_detail["job_detail"] 
            work_type = job_detail["work_type"] 

            job_data = {
                "id": id,
                "search_keyword": search_keyword,
                "title": title,
                "jobLocation": jobLocation.text.strip() if jobLocation else "",
                "employer": employer.text.strip() if employer else "",
                "work_type": work_type,
                "salary": salary.text.strip() if salary else "",
                "date_posted": date_posted.text.strip() if date_posted else "",
                "job_description": job_description,
                "job_url": job_url if job_url else "No URL"
            }
            jobs.append(job_data)
            
        time.sleep(1)  # Prevents blocking by Seek
        
    return jobs

def upload_to_mongodb(jobs):
    """Upload job listings to MongoDB without duplicates."""
    try:
        if not jobs:
            print("⚠️ No new jobs to upload.")
            return
        
        db = get_db()
        if db is None:
            return
        
        collection = db.jobs  # Replace with your collection name
        existing_job_ids = get_existing_job_ids()
        new_data = [job for job in jobs if job["id"] not in existing_job_ids]  # Avoid duplicates

        if new_data:
            print(f"✅ Uploading {len(new_data)} new job listings to MongoDB...")
            collection.insert_many(new_data)  # Insert new documents
            print(f"✅ Successfully uploaded {len(new_data)} new job listings.")
        else:
            print("⚠️ No new jobs to update.")
    
    except Exception as e:
        print("❌ Error uploading data to MongoDB:", e)

if __name__ == "__main__":
    search_keywords = [
        "Hospitality",
        "Customer Service",
 

    ]
    
    all_jobs = []
    for keyword in search_keywords:
        print(f"🔍 Searching for jobs: {keyword}")
        job_listings = get_job_listings(keyword)
        all_jobs.extend(job_listings)
        time.sleep(2)  # Prevent excessive requests
    
    # ✅ Upload to MongoDB
    upload_to_mongodb(all_jobs)
    
    print("🎉 Job listings scraping and uploading completed!")