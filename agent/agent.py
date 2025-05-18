import ollama
import json
import datetime
import asyncio
from database.db_manager import DatabaseManager

class Agent:
    def __init__(self, model="qwen3:0.6b"):
        self.client = ollama.Client()
        self.model = model
        self.db_manager = None
        
    async def setup(self):
        """Setup database connection"""
        self.db_manager = DatabaseManager()
        await self.db_manager.connect()
    
    async def query_database(self, query_params):
        """Tool to query the database"""
        try:
            # Validate and process date parameters
            if "start_date" in query_params and query_params["start_date"]:
                try:
                    datetime.datetime.strptime(query_params["start_date"], "%Y-%m-%d")
                except ValueError:
                    return {"error": f"Invalid start_date format: {query_params['start_date']}. Use YYYY-MM-DD."}
            
            if "end_date" in query_params and query_params["end_date"]:
                try:
                    datetime.datetime.strptime(query_params["end_date"], "%Y-%m-%d")
                except ValueError:
                    return {"error": f"Invalid end_date format: {query_params['end_date']}. Use YYYY-MM-DD."}
            
            # Execute the query
            results = await self.db_manager.query_documents(query_params)

            # Defensive check: query_documents should always return a list.
            # If it returns None, this is an unexpected state.
            if results is None:
                print(f"CRITICAL: db_manager.query_documents returned None. Query Params: {query_params}")
                results = [] # Treat as empty list to prevent TypeError and allow graceful handling
            
            processed_results = []
            # Now, results is guaranteed to be a list (possibly empty).
            for doc in results:
                # Truncate full_text for brevity in results
                if "full_text" in doc and doc["full_text"] and len(doc["full_text"]) > 1000:
                    doc["full_text"] = doc["full_text"][:1000] + "... [truncated]"
                processed_results.append(doc)
            
            return processed_results
        except Exception as e:
            # Log the full exception for debugging
            print(f"Exception in query_database tool: {type(e).__name__} - {str(e)}")
            # Provide a more generic error to the LLM for tool execution failure
            return {"error": f"An internal error occurred while querying the database: {str(e)}"}
    
    async def get_document_summary(self, document_number):
        """Tool to get a detailed summary of a specific document"""
        try:
            query_params = {"document_number": document_number, "limit": 1}
            results = await self.db_manager.query_documents(query_params)
            
            if not results:
                return {"error": f"Document with number {document_number} not found"}
            
            document = results[0]
            
            # Generate a summary of the document
            prompt = f"""You are a helpful assistant that summarizes federal registry documents clearly and concisely.
            
Please provide a concise summary of the following document:

Title: {document.get('title', 'N/A')}
Abstract: {document.get('abstract', 'N/A')}
Publication Date: {document.get('publication_date', 'N/A')}
Document Type: {document.get('document_type', 'N/A')}
Agencies: {', '.join(document.get('agency_names', []))}
Effective Date: {document.get('effective_date', 'N/A')}
Is Significant: {'Yes' if document.get('significant', 0) == 1 else 'No'}
Full Text: {document.get('full_text', 'N/A')[:5000]}"""
            
            # Run in executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.client.generate(model=self.model, prompt=prompt)
            )
            
            summary = response['response']
            
            return {
                "document_number": document.get("document_number"),
                "title": document.get("title"),
                "publication_date": document.get("publication_date"),
                "document_type": document.get("document_type"),
                "agencies": document.get("agency_names", []),
                "summary": summary
            }
        except Exception as e:
            return {"error": f"Error generating document summary: {str(e)}"}
    
    async def process_query(self, user_query):
        """Process user query and generate response using the agent"""
        try:
            # Format system prompt and tools as JSON
            system_prompt = """
            You are a helpful assistant with access to a database of federal registry documents.
            You can use tools to search the database and provide informative answers to user queries.
            Always provide accurate information based on the search results.
            Do not make up information not found in the search results.
            
            If the user asks for recent documents, executive orders, or rules, use the query_database tool.
            If the user asks for details about a specific document, use the get_document_summary tool.

            When a user asks for documents for a specific month and year (e.g., "March 2025"), you MUST calculate the correct start_date (the first day of that month) AND the correct end_date (the last day of that month).
            For example:
            - "documents for March 2025" should use start_date: "2025-03-01" and end_date: "2025-03-31".
            - "documents for February 2024" should use start_date: "2024-02-01" and end_date: "2024-02-29" (remember leap years).
            
            If a tool call results in an error (e.g., 'An internal error occurred'), inform the user that there was a technical difficulty and you couldn't retrieve the information, rather than stating no documents were found.

            You should format your responses in a readable way, using markdown formatting if appropriate.
            """
            
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "query_database",
                        "description": "Search for documents in the federal registry database",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "start_date": {
                                    "type": "string",
                                    "description": "Start date for the search (YYYY-MM-DD)"
                                },
                                "end_date": {
                                    "type": "string",
                                    "description": "End date for the search (YYYY-MM-DD)"
                                },
                                "document_type": {
                                    "type": "string",
                                    "description": "Type of document to search for (e.g., 'RULE', 'NOTICE', 'PRESIDENTIAL_DOCUMENT')"
                                },
                                "keyword": {
                                    "type": "string",
                                    "description": "Keyword to search for in the document title, abstract, or full text"
                                },
                                "agency": {
                                    "type": "string",
                                    "description": "Agency name to filter documents by"
                                },
                                "limit": {
                                    "type": "integer",
                                    "description": "Maximum number of results to return (default: 10)"
                                }
                            },
                            "required": []
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_document_summary",
                        "description": "Get a detailed summary of a specific document",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "document_number": {
                                    "type": "string",
                                    "description": "The document number to summarize"
                                }
                            },
                            "required": ["document_number"]
                        }
                    }
                }
            ]
            
            # Convert the tools to a string format that can be included in the prompt
            tools_str = json.dumps(tools, indent=2)
            
            # Build the complete prompt with system instructions, tools, and user query
            complete_prompt = f"""
            {system_prompt}
            
            Available tools:
            {tools_str}
            
            User query: {user_query}
            
            First, decide if you need to use a tool to answer the query.
            If you need to use a tool, respond in the following JSON format, ensuring all necessary parameters (like start_date AND end_date for monthly queries) are provided:
            
            ```json
            {{
              "tool": "tool_name",
              "parameters": {{
                "param1": "value1",
                "param2": "value2"
              }}
            }}
            ```
            
            Where tool_name is one of the available tools, and parameters are the required parameters for that tool.
            """
            
            # Run in executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            initial_response = await loop.run_in_executor(
                None, 
                lambda: self.client.generate(model=self.model, prompt=complete_prompt)
            )
            
            response_text = initial_response['response']
            
            # Try to parse the response as a tool call
            try:
                # Extract JSON if it's wrapped in markdown code blocks
                if "```json" in response_text and "```" in response_text:
                    json_part = response_text.split("```json")[1].split("```")[0].strip()
                    tool_call = json.loads(json_part)
                # Or try to parse the entire response as JSON
                else:
                    tool_call = json.loads(response_text)
                
                if "tool" in tool_call and "parameters" in tool_call:
                    tool_name = tool_call["tool"]
                    tool_params = tool_call["parameters"]
                    
                    # Execute the appropriate function
                    if tool_name == "query_database":
                        tool_response = await self.query_database(tool_params)
                    elif tool_name == "get_document_summary":
                        tool_response = await self.get_document_summary(tool_params.get("document_number"))
                    else:
                        tool_response = {"error": f"Unknown function: {tool_name}"}
                    
                    # Format the final prompt with the tool response
                    final_prompt = f"""
                    {system_prompt}
                    
                    User query: {user_query}
                    
                    You used the tool '{tool_name}' with parameters: {json.dumps(tool_params)}
                    
                    Tool response: {json.dumps(tool_response, default=str)}
                    
                    Please provide a final response to the user query based on the tool results.
                    Format the response in markdown for better readability. Ensure your response accurately reflects the query parameters used and the data returned. 
                    If the tool_response contains an 'error' key, acknowledge that a technical difficulty occurred. 
                    If no documents are found for the specified period (and there was no error), state that clearly.
                    """
                    
                    # Get the final response
                    final_response = await loop.run_in_executor(
                        None, 
                        lambda: self.client.generate(model=self.model, prompt=final_prompt)
                    )
                    
                    return final_response['response']
                else:
                    # Model didn't properly format a tool call, use its direct response
                    return response_text
            except json.JSONDecodeError:
                # If response isn't JSON, just return it directly
                return response_text
                
        except Exception as e:
            # Handle any errors during processing
            error_message = f"Error processing query: {str(e)}"
            print(error_message)
            return "I'm sorry, I encountered an error while processing your query. Please try again."
    
    async def close(self):
        """Close database connection"""
        if self.db_manager:
            await self.db_manager.close()