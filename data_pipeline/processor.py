import json
import os
import asyncio
import aiohttp
from datetime import datetime
from database.db_manager import DatabaseManager

async def process_document(doc, db_manager):
    """Process a single document and store it in the database"""
    # Try to fetch full text if available
    full_text = ""
    if "full_text_xml_url" in doc:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(doc["full_text_xml_url"]) as response:
                    if response.status == 200:
                        full_text = await response.text()
        except Exception as e:
            print(f"Error fetching full text: {e}")
    
    # Store in database
    await db_manager.store_document(doc, full_text)

async def process_raw_data(filename):
    """Process raw data from downloaded file and store in database"""
    # Connect to database
    db_manager = DatabaseManager()
    await db_manager.connect()
    
    try:
        # Load raw data
        with open(filename, 'r') as f:
            documents = json.load(f)
        
        # Process each document
        tasks = []
        for doc in documents:
            tasks.append(process_document(doc, db_manager))
        
        # Run tasks concurrently
        await asyncio.gather(*tasks)
        
        print(f"Processed {len(documents)} documents")
    finally:
        # Close database connection
        await db_manager.close()

async def main():
    """Main processing function"""
    # Create directory for processed data
    os.makedirs("data/processed", exist_ok=True)
    
    # Get most recent raw data file
    raw_dir = "data/raw"
    if not os.path.exists(raw_dir):
        print("No raw data directory found")
        return
    
    files = [f for f in os.listdir(raw_dir) if f.endswith(".json")]
    if not files:
        print("No raw data files found")
        return
    
    latest_file = max(files, key=lambda x: os.path.getctime(os.path.join(raw_dir, x)))
    raw_file_path = os.path.join(raw_dir, latest_file)
    
    # Process the raw data
    await process_raw_data(raw_file_path)
    
    # Mark as processed by creating an empty file
    processed_marker = os.path.join("data/processed", latest_file.replace(".json", ".processed"))
    with open(processed_marker, "w") as f:
        f.write(datetime.now().isoformat())

if __name__ == "__main__":
    asyncio.run(main())
