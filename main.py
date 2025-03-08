from fastapi import FastAPI, HTTPException, Depends
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from typing import List
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="Job Listings API", description="API with API Key Authentication", version="1.0")

# MongoDB Connection
client = MongoClient(os.getenv("MONGO_URI"))
db = client.joblistings
collection = db.jobs  # Replace with your collection name

# API Key stored in .env
API_KEY = os.getenv("API_KEY")

# Pydantic model for validation
class JobListing(BaseModel):
    id: str
    search_keyword: str
    title: str
    jobLocation: str
    employer: str
    work_type: str
    salary: str
    date_posted: str
    job_description: str
    job_url: str

# Dependency to check API key
def verify_api_key(api_key: str):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key

@app.get("/", tags=["Health Check"])
async def root():
    return {"message": "Welcome to the Job Listings API! Please use an API Key to access job listings."}

@app.get("/jobs", response_model=List[JobListing], tags=["Job Listings"])
async def get_jobs(api_key: str = Depends(verify_api_key)):
    """Fetch all job listings from MongoDB (API Key Required)"""
    jobs = list(collection.find({}, {"_id": 0}))  # Exclude MongoDB '_id'
    return jobs
