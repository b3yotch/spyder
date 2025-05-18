import aiohttp
import asyncio
import datetime
import json
import os
from tqdm import tqdm

async def fetch_federal_registry_data(start_date, end_date, page=1, per_page=100):
    """Fetch data from Federal Registry API asynchronously with pagination"""
    # The basic endpoint URL matching the documentation
    url = "https://www.federalregister.gov/api/v1/documents.json"
    
    # Set up parameters according to the API documentation
    params = {
        "fields[]": [
            "abstract", 
            "document_number", 
            "type", 
            "publication_date", 
            "title",
            "agencies", 
            "html_url", 
            "full_text_xml_url",
            "effective_on",
            "significant"
        ],
        "per_page": per_page,
        "page": page,
        "order": "newest",
        "conditions[publication_date][gte]": start_date,
        "conditions[publication_date][lte]": end_date
    }
    
    # Add a small delay to avoid rate limiting
    await asyncio.sleep(0.2)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get("results", [])
                    count = data.get("count", 0)
                    total_pages = data.get("total_pages", 1)
                    
                    if page == 1 or page % 10 == 0:
                        print(f"Page {page}/{total_pages}: Retrieved {len(results)} documents")
                    
                    return {
                        "results": results,
                        "total_pages": total_pages,
                        "count": count
                    }
                else:
                    error_text = await response.text()
                    print(f"Error fetching page {page}: {response.status}")
                    print(f"Error response: {error_text}")
                    # If we hit a rate limit, wait and try again
                    if response.status == 429:
                        print(f"Rate limited. Waiting 5 seconds before retrying page {page}...")
                        await asyncio.sleep(5)
                        return await fetch_federal_registry_data(start_date, end_date, page, per_page)
                    return {"results": [], "total_pages": 0, "count": 0}
    except Exception as e:
        print(f"Exception during API fetch for page {page}: {e}")
        # Wait and retry on connection errors
        if "Connection" in str(e):
            print(f"Connection error. Waiting 3 seconds before retrying page {page}...")
            await asyncio.sleep(3)
            return await fetch_federal_registry_data(start_date, end_date, page, per_page)
        return {"results": [], "total_pages": 0, "count": 0}

async def fetch_all_pages(start_date, end_date):
    """Fetch all pages of results from the API"""
    # Use a larger per_page value to reduce the number of API calls needed
    per_page = 100  # Maximum allowed by the API
    
    # Get the first page to determine total pages
    first_page = await fetch_federal_registry_data(start_date, end_date, page=1, per_page=per_page)
    all_results = first_page.get("results", [])
    total_pages = first_page.get("total_pages", 1)
    total_count = first_page.get("count", 0)
    
    print(f"Found {total_count} documents across {total_pages} pages")
    
    if total_pages > 1:
        print(f"Fetching all remaining pages of results (this may take a while)...")
        
        # Process in batches to avoid overwhelming the API
        all_remaining_pages = list(range(2, total_pages + 1))
        
        # Create batches of 5 pages each
        batch_size = 5
        
        # Set up progress bar
        progress = tqdm(total=len(all_remaining_pages), desc="Downloading pages")
        
        for i in range(0, len(all_remaining_pages), batch_size):
            batch_pages = all_remaining_pages[i:i+batch_size]
            batch_tasks = [fetch_federal_registry_data(start_date, end_date, page=page, per_page=per_page) for page in batch_pages]
            
            # Process this batch
            batch_results = await asyncio.gather(*batch_tasks)
            
            # Update progress bar
            progress.update(len(batch_pages))
            
            # Process results from this batch
            batch_doc_count = 0
            for result in batch_results:
                docs = result.get("results", [])
                all_results.extend(docs)
                batch_doc_count += len(docs)
            
            print(f"Batch complete: Added {batch_doc_count} documents. Total so far: {len(all_results)}/{total_count}")
        
        progress.close()
    
    print(f"Download complete: Retrieved {len(all_results)} documents")
    return all_results

async def download_data_for_date_range(start_date, end_date):
    """Download data for a specified date range"""
    # Create directory for raw data
    os.makedirs("data/raw", exist_ok=True)
    
    # Fetch all documents
    documents = await fetch_all_pages(start_date, end_date)
    
    # Generate filename based on date range
    filename = f"data/raw/federal_registry_{start_date}_to_{end_date}.json"
    
    # Save raw data
    with open(filename, "w") as f:
        json.dump(documents, f)
    
    print(f"Downloaded {len(documents)} documents for {start_date} to {end_date}")
    return filename

def get_date_range_for_current_year():
    """Get date range from Jan 1, 2025 until yesterday"""
    # Create a date in 2025 with same month and day as the system date
    current_system_date = datetime.date.today()
    
    # Pretend we're in 2025
    current_date = datetime.date(2025, current_system_date.month, current_system_date.day)
    
    # Get yesterday's date (in 2025)
    yesterday = current_date - datetime.timedelta(days=1)
    
    # Start from beginning of 2025
    start_date = datetime.date(2025, 1, 1)
    
    return start_date.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d")

async def main():
    """Main function to download data"""
    # Use a fixed date range that we know has data (2025)
    start_date = "2025-01-01"
    end_date = "2025-12-31"
    
    print(f"Downloading Federal Register documents from {start_date} to {end_date}")
    
    # Download the data
    await download_data_for_date_range(start_date, end_date)

if __name__ == "__main__":
    asyncio.run(main())