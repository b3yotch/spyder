import asyncio
import uvicorn
import argparse
import os
import datetime
from data_pipeline import run_pipeline
from database.db_manager import DatabaseManager

async def setup_database():
    """Set up database tables if they don't exist"""
    db = DatabaseManager()
    await db.connect()
    await db.close()

async def run_targeted_pipeline(incremental=True):
    """Run the data pipeline for specific date ranges: April 2025 and May 2025 (up to today)."""
    os.makedirs("data", exist_ok=True)
    today = datetime.date.today().replace(year=2025)
    today_in_2025=today-datetime.timedelta(days=1)

    # --- April 2025 --- 
    april_start_date = datetime.date(2025, 4, 1)
    april_end_date = datetime.date(2025, 4, 30)
    print(f"Fetching Federal Register data for April 2025: {april_start_date} to {april_end_date}")
    await run_pipeline(start_date=april_start_date, end_date=april_end_date, incremental=incremental)
    print("--- April 2025 data processing complete ---")

    # --- May 2025 (up to today's date in 2025) --- 
    may_start_date = datetime.date(2025, 5, 1)
    # Ensure end_date for May does not exceed today_in_2025 or go before may_start_date
    may_end_date = min(today_in_2025, datetime.date(2025, 5, 31)) # Cap at May 31st
    if may_end_date < may_start_date:
        may_end_date = may_start_date # Ensure end_date is not before start_date for May
    
    print(f"Fetching Federal Register data for May 2025: {may_start_date} to {may_end_date}")
    await run_pipeline(start_date=may_start_date, end_date=may_end_date, incremental=incremental)
    print("--- May 2025 data processing complete ---")

    print("Targeted data pipeline runs completed.")

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Federal Registry RAG Agent")
    parser.add_argument("--pipeline-only", action="store_true", help="Run only the data pipeline")
    # --days argument is no longer used directly for pipeline runs but kept for potential other uses or future changes.
    parser.add_argument("--days", type=int, default=30, help="Number of days to fetch data for (used by general pipeline if not overridden)")
    parser.add_argument("--port", type=int, default=8000, help="Port for the web server")
    parser.add_argument("--full-refresh", action="store_true", help="Force full refresh for the targeted pipeline runs instead of incremental update")
    args = parser.parse_args()
    
    # Setup database
    print("Setting up database...")
    await setup_database()
    
    # Run targeted data pipeline for April and May 2025
    print(f"Running {'full refresh' if args.full_refresh else 'incremental'} targeted data pipeline for April & May 2025...")
    await run_targeted_pipeline(incremental=not args.full_refresh)
    
    if args.pipeline_only:
        print("Pipeline completed. Exiting as requested.")
        return
    
    # Start API server
    print(f"Starting API server on port {args.port}...")
    uvicorn.run("api.main:app", host="0.0.0.0", port=args.port, reload=True)

if __name__ == "__main__":
    asyncio.run(main())