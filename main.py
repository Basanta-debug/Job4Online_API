from fastapi import FastAPI, HTTPException, Depends
from pymongo import MongoClient
import os
from dotenv import load_dotenv
from typing import List
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Debug prints
print("Loading environment variables...")
print("MONGO_URI:", os.getenv("MONGO_URI"))
print("API_KEY:", os.getenv("API_KEY"))

# MongoDB Connection
try:
    client = MongoClient(os.getenv("MONGO_URI"), serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    print("MongoDB connection successful.")
    db = client.joblistings
    collection = db.jobs
except Exception as e:
    print("MongoDB connection failed:", e)
    raise e

# FastAPI app
app = FastAPI(title="Job Listings API", description="API with API Key Authentication", version="1.0")

API_KEY = os.getenv("API_KEY")

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

def verify_api_key(api_key: str):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key

@app.get("/", tags=["Health Check"])
async def root():
    return {"message": "Welcome to the Job Listings API! Please use an API Key to access job listings."}

@app.get("/jobs", response_model=List[JobListing], tags=["Job Listings"])
async def get_jobs(api_key: str = Depends(verify_api_key)):
    jobs = list(collection.find({}, {"_id": 0}))
    return jobs

# Run the app if executing directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
