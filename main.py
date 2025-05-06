from fastapi import FastAPI, HTTPException, Depends
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import os
from dotenv import load_dotenv
from typing import List, Optional
from pydantic import BaseModel
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
API_KEY = os.getenv("API_KEY")

logger.info("Loading environment variables...")
logger.info(f"MONGO_URI: {MONGO_URI}")
logger.info(f"API_KEY: {API_KEY}")

# MongoDB Connection
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    logger.info("MongoDB connection successful.")
    db = client["joblistings"]
    collection = db["jobs"]
except Exception as e:
    logger.error("MongoDB connection failed: %s", e)
    raise e

# FastAPI app
app = FastAPI(
    title="Job Listings API",
    description="API with API Key Authentication",
    version="1.0"
)

class JobListing(BaseModel):
    id: str
    search_keyword: str
    title: str
    jobLocation: str
    employer: Optional[str]
    work_type: Optional[str]
    salary: Optional[str]
    min_salary: Optional[str]
    max_salary: Optional[str]
    payable_duration: Optional[str]
    date_posted: Optional[str]
    job_summary: Optional[str]
    job_description_html: Optional[str]
    job_url: Optional[str]
    apply_url: Optional[str]
    source: Optional[str]

def verify_api_key(api_key: str):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key

@app.get("/", tags=["Health Check"])
async def root():
    return {"message": "Welcome to the Job Listings API! Please use an API Key to access job listings."}

@app.get("/jobs", response_model=List[JobListing], tags=["Job Listings"])
async def get_jobs(api_key: str = Depends(verify_api_key)):
    try:
        jobs = list(collection.find({}, {"_id": 0}))
        logger.info(f"Retrieved {len(jobs)} job(s) from MongoDB.")
        return jobs
    except PyMongoError as e:
        logger.error("Database query error: %s", e)
        raise HTTPException(status_code=500, detail="Database query failed.")
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
