import aiosqlite
import json
from datetime import datetime
import os

class DatabaseManager:
    def __init__(self, db_path='federal_register.db'):
        self.db_path = db_path
        self.conn = None

    async def connect(self):
        """Create a connection to SQLite database"""
        # Ensure directory exists for database file if db_path contains a directory
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        self.conn = await aiosqlite.connect(self.db_path)
        # Enable foreign keys
        await self.conn.execute("PRAGMA foreign_keys = ON")
        # Convert results to dict
        self.conn.row_factory = aiosqlite.Row
        print(f"Connected to SQLite database at {self.db_path}")
        
        # Create tables if they don't exist
        await self.setup_tables()

    async def setup_tables(self):
        """Create necessary tables if they don't exist"""
        # Documents table
        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_number TEXT UNIQUE,
            title TEXT NOT NULL,
            document_type TEXT,
            publication_date TEXT,
            effective_date TEXT,
            abstract TEXT,
            html_url TEXT,
            significant INTEGER DEFAULT 0,
            full_text TEXT,
            fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Agencies table
        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS agencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            acronym TEXT
        )
        """)
        
        # Document-agency relationship table
        await self.conn.execute("""
        CREATE TABLE IF NOT EXISTS document_agencies (
            document_id INTEGER,
            agency_id INTEGER,
            PRIMARY KEY (document_id, agency_id),
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (agency_id) REFERENCES agencies(id) ON DELETE CASCADE
        )
        """)
        
        # Create indices for faster searches
        await self.conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_publication_date ON documents (publication_date)
        """)
        
        await self.conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_number ON documents (document_number)
        """)
        
        await self.conn.commit()

    async def get_or_create_agency(self, agency_name, agency_acronym=''):
        """Get an existing agency or create it if it doesn't exist"""
        if not agency_name:
            return None
            
        # Try to find existing agency
        async with self.conn.execute(
            "SELECT id FROM agencies WHERE name = ?", 
            (agency_name,)
        ) as cursor:
            agency_result = await cursor.fetchone()
            
            if agency_result:
                return agency_result['id']
        
        # If we get here, the agency doesn't exist, so create it
        try:
            await self.conn.execute(
                "INSERT INTO agencies (name, acronym) VALUES (?, ?)",
                (agency_name, agency_acronym)
            )
            await self.conn.commit()
            
            # Get the newly created agency ID
            async with self.conn.execute(
                "SELECT id FROM agencies WHERE name = ?",
                (agency_name,)
            ) as cursor:
                agency_result = await cursor.fetchone()
                return agency_result['id'] if agency_result else None
                
        except Exception as e:
            print(f"Error creating agency '{agency_name}': {e}")
            # If we got an error (likely integrity constraint), try to fetch again
            async with self.conn.execute(
                "SELECT id FROM agencies WHERE name = ?", 
                (agency_name,)
            ) as cursor:
                agency_result = await cursor.fetchone()
                return agency_result['id'] if agency_result else None

    async def store_document(self, doc, full_text=""):
        """Store a document in the database"""
        if 'document_number' not in doc:
            print(f"Warning: Document missing document_number field: {doc.get('title', 'UNKNOWN')}")
            return
            
        # First check if document already exists
        async with self.conn.execute(
            "SELECT id FROM documents WHERE document_number = ?", 
            (doc['document_number'],)
        ) as cursor:
            existing = await cursor.fetchone()
            if existing:
                # Document exists, update it
                await self.conn.execute("""
                UPDATE documents SET 
                title = ?,
                document_type = ?,
                publication_date = ?,
                effective_date = ?,
                abstract = ?,
                html_url = ?,
                significant = ?,
                full_text = ?,
                fetched_at = ?
                WHERE document_number = ?
                """, (
                    doc['title'],
                    doc.get('document_type', doc.get('type')),
                    doc.get('publication_date'),
                    doc.get('effective_date', doc.get('effective_on')),
                    doc.get('abstract', ''),
                    doc.get('html_url', ''),
                    1 if doc.get('significant') else 0,
                    full_text,
                    datetime.now().isoformat(),
                    doc['document_number']
                ))
                document_id = existing['id']
            else:
                # Insert new document
                await self.conn.execute("""
                INSERT INTO documents (
                    document_number, title, document_type, publication_date, 
                    effective_date, abstract, html_url, significant, full_text, fetched_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    doc['document_number'],
                    doc['title'],
                    doc.get('document_type', doc.get('type')),
                    doc.get('publication_date'),
                    doc.get('effective_date', doc.get('effective_on')),
                    doc.get('abstract', ''),
                    doc.get('html_url', ''),
                    1 if doc.get('significant') else 0,
                    full_text,
                    datetime.now().isoformat()
                ))
                
                # Get the document ID
                async with self.conn.execute(
                    "SELECT last_insert_rowid() as id"
                ) as cursor:
                    result = await cursor.fetchone()
                    document_id = result['id']
        
        # Process agencies
        agencies = doc.get('agencies', [])
        if not isinstance(agencies, list):
            agencies = []
        
        # Handle both direct agency names and agency objects
        for agency in agencies:
            # Agency might be a dict or string depending on the API response format
            if isinstance(agency, dict):
                agency_name = agency.get('name', '')
                agency_acronym = agency.get('acronym', '')
            else:
                agency_name = str(agency) if agency else ''
                agency_acronym = ''
            
            if not agency_name:
                continue
                
            # Get or create the agency
            agency_id = await self.get_or_create_agency(agency_name, agency_acronym)
            if not agency_id:
                continue
            
            # Link document to agency (ignore if already exists due to PRIMARY KEY constraint)
            try:
                await self.conn.execute(
                    "INSERT OR IGNORE INTO document_agencies (document_id, agency_id) VALUES (?, ?)",
                    (document_id, agency_id)
                )
            except Exception as e:
                print(f"Error linking document to agency: {e}")
        
        await self.conn.commit()
    
    async def query_documents(self, query_params):
        """Query documents based on parameters"""
        # Base query with JOIN to get agency information
        base_query = """
        SELECT d.*, GROUP_CONCAT(a.name) as agency_names
        FROM documents d
        LEFT JOIN document_agencies da ON d.id = da.document_id
        LEFT JOIN agencies a ON da.agency_id = a.id
        WHERE 1=1
        """
        params = []
        
        # Add filters based on query_params
        if "id" in query_params:
            base_query += " AND d.id = ?"
            params.append(query_params["id"])
            
        if "document_number" in query_params:
            base_query += " AND d.document_number = ?"
            params.append(query_params["document_number"])
            
        if "start_date" in query_params:
            base_query += " AND d.publication_date >= ?"
            params.append(query_params["start_date"])
        
        if "end_date" in query_params:
            base_query += " AND d.publication_date <= ?"
            params.append(query_params["end_date"])
        
        if "document_type" in query_params and query_params["document_type"]:
            base_query += " AND LOWER(d.document_type) = LOWER(?)"
            params.append(query_params["document_type"])
        
        if "keyword" in query_params and query_params["keyword"]:
            base_query += " AND (LOWER(d.title) LIKE LOWER(?) OR LOWER(d.abstract) LIKE LOWER(?) OR LOWER(d.full_text) LIKE LOWER(?))"
            keyword = f"%{query_params['keyword']}%"
            params.extend([keyword, keyword, keyword])
            
        if "agency" in query_params and query_params["agency"]:
            base_query += " AND LOWER(a.name) LIKE LOWER(?)"
            params.append(f"%{query_params['agency']}%")
        
        # Group by document to consolidate agencies
        base_query += " GROUP BY d.id"
        
        # Add order and limit
        order_by = query_params.get("order_by", "publication_date")
        order_dir = query_params.get("order_dir", "DESC")
        base_query += f" ORDER BY d.{order_by} {order_dir}"
        
        limit = query_params.get("limit", 10)
        base_query += f" LIMIT {limit}"
        
        async with self.conn.execute(base_query, params) as cursor:
            rows = await cursor.fetchall()
            
            # Convert rows to dictionaries
            results = []
            for row in rows:
                doc = dict(row)
                # Parse agency names
                if doc.get('agency_names'):
                    doc['agency_names'] = doc['agency_names'].split(',')
                else:
                    doc['agency_names'] = []
                results.append(doc)
            
            return results

    async def close(self):
        """Close the database connection"""
        if self.conn:
            await self.conn.close()
            print("Database connection closed")