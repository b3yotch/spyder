from .downloader import download_data_for_date_range
from .processor import process_raw_data
import asyncio
import datetime
import os
import json

async def get_last_processed_date():
    """Get the most recent date that was already processed"""
    tracking_file = "data/processed/last_processed_date.json"
    
    # Default to 30 days ago if no tracking file exists
    default_date = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    
    if not os.path.exists(tracking_file):
        return default_date
        
    try:
        with open(tracking_file, 'r') as f:
            data = json.load(f)
            return data.get('last_date', default_date)
    except (json.JSONDecodeError, FileNotFoundError):
        return default_date

async def save_last_processed_date(date_str):
    """Save the most recent date that was processed"""
    tracking_file = "data/processed/last_processed_date.json"
    os.makedirs(os.path.dirname(tracking_file), exist_ok=True)
    
    with open(tracking_file, 'w') as f:
        json.dump({'last_date': date_str}, f)

async def run_pipeline(days_back=7, start_date=None, end_date=None, incremental=True):
    """Run the complete data pipeline - download and process
    
    Args:
        days_back (int): Number of days to look back if start_date/end_date not provided
        start_date (datetime.date, optional): Specific start date
        end_date (datetime.date, optional): Specific end date
        incremental (bool): If True, only fetch documents since the last run
    """
    # Ensure data directories exist
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/processed", exist_ok=True)
    
    # Calculate date range
    today = datetime.date.today()
    # Safety check - ensure we're not using future dates
    if today.year > 2025:
        today = today.replace(year=2025)
        
    if end_date is None:
        end_date = today
    
    # For incremental updates, get the last processed date
    if incremental and start_date is None:
        start_date_str = await get_last_processed_date()
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
        print(f"Performing incremental update from {start_date} to {end_date}")
    elif start_date is None:
        start_date = today - datetime.timedelta(days=days_back)
    
    # Format dates for API
    start_str = start_date.strftime("%Y-%m-%d") if isinstance(start_date, datetime.date) else start_date
    end_str = end_date.strftime("%Y-%m-%d") if isinstance(end_date, datetime.date) else end_date
    
    # Step 1: Download data
    print(f"Downloading data from {start_str} to {end_str}...")
    raw_file = await download_data_for_date_range(start_str, end_str)
    
    # Step 2: Process data
    print(f"Processing data from {raw_file}...")
    await process_raw_data(raw_file)
    
    # Update the last processed date to today's date
    await save_last_processed_date(end_str)
    
    print("Pipeline completed successfully!")
