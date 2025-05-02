from fastapi import FastAPI, HTTPException, Depends, Query
from pymongo import MongoClient
from typing import List, Optional
from pydantic import BaseModel
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# FastAPI app
app = FastAPI(title="Job40nline API", description="API serving job listings scraped from Jora", version="1.0")

# MongoDB Connection
mongo_uri = os.getenv("MONGO_URI")
api_key_env = os.getenv("API_KEY")

try:
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    print("MongoDB connection successful.")
except Exception as e:
    print("MongoDB connection failed:", e)
    raise e

class JobListing(BaseModel):
    id: str
    search_keyword: str
    title: str
    jobLocation: str
    employer: str
    work_type: str
    salary: str
    min_salary: Optional[float]
    max_salary: Optional[float]
    payable_duration: Optional[str]
    date_posted: str
    job_summary: str
    job_description_html: str
    job_url: str
    apply_url: str
    source: str

def verify_api_key(api_key: str = Query(...)):
    if api_key != api_key_env:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key

def get_collection(api_key: str):
    """
    Optionally use API key to select a different database/collection dynamically.
    Here I append api_key to the collection name to create unique collections per key.
    """
    db_name = f"job_scraper"  # could also be `f"job_scraper_{api_key}"` if you want db per api key
    collection_name = f"jorajobs_{api_key}"  # unique collection per API key
    db = client[db_name]
    return db[collection_name]

@app.get("/", tags=["Health Check"])
async def root():
    return {"message": "Welcome to the Job Listings API! Use /jobs?api_key=YOUR_KEY to fetch jobs."}

@app.get("/jobs", response_model=List[JobListing], tags=["Job Listings"])
async def get_jobs(api_key: str = Depends(verify_api_key)):
    collection = get_collection(api_key)
    jobs = list(collection.find({}, {"_id": 0}))
    return jobs

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
