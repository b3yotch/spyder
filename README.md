# Federal Register RAG Agent with SQLite

A User-Facing Chat-Style Retrieval Augmented Generation (RAG) Agentic System. Users can ask queries to a local LLM (via Ollama), which then uses tools to retrieve up-to-date information from a local SQLite database populated with Federal Register data.

## Core Functionality

*   **Chat Interface**: Users interact with an LLM agent through a basic web UI.
*   **Agentic LLM**: The LLM (e.g., Qwen3 0.6b via Ollama) uses predefined tools (functions) to answer queries.
*   **Data Pipeline**: An automated pipeline downloads data daily (or on demand) from the Federal Register API, processes it, and stores it in a local SQLite database.
*   **SQLite Database**: Stores Federal Register documents, queried using raw SQL.
*   **API/WebSockets**: A FastAPI backend provides the interface between the UI and the LLM agent, primarily using WebSockets for chat.
*   **Asynchronous Operations**: Key components like the API and database interactions are designed to be asynchronous and non-blocking.

## Project Structure

```
/
├── agent/                  # LLM agent logic and tool definitions
│   └── agent.py
├── api/                    # FastAPI application for UI and agent communication
│   └── main.py
├── data_pipeline/          # Scripts for downloading and processing data
│   ├── downloader.py
│   └── processor.py
│   └── __init__.py         # Main pipeline execution logic
├── database/               # Database management (SQLite)
│   └── db_manager.py
├── ui/                     # Basic HTML/CSS/JS for the chat interface
│   └── index.html
├── data/                   # Data storage (not committed to git)
│   ├── raw/                # Raw JSON data downloaded from API
│   └── processed/          # Processed data markers, logs, etc.
│       └── last_processed_date.json # Tracks last pipeline run for incremental updates
├── federal_register.db     # SQLite database file (not committed to git)
├── main.py                 # Main entry point for the application (runs pipeline & starts server)
├── requirements.txt        # Python package dependencies
└── README.md               # This file
```

## Concepts & Technologies Used

1.  **Asynchronous Programming (Python `asyncio`)**: For non-blocking I/O operations, especially in the API and data pipeline.
2.  **SQLite3 & Raw SQL**: For local data storage. Queries are written in raw SQL, avoiding ORMs.
3.  **FastAPI**: For creating the basic API and WebSocket interface for the chat.
4.  **Agentic LLM Inference (Ollama)**:
    *   Uses a local LLM (e.g., `qwen3:0.6b`) running via Ollama.
    *   The LLM is prompted to use defined tools/functions based on user queries.
    *   The system parses the LLM's tool call requests (JSON), executes the corresponding Python functions, and returns results to the LLM for summarization.
5.  **Data Pipeline**: Automated process to download data from the [Federal Register API](https://www.federalregister.gov/developers/documentation/api/v1), clean it, and load it into the SQLite database. Supports incremental updates.
6.  **Basic Web UI**: Simple HTML, CSS, and JavaScript for a chat input box and result display.

## Prerequisites

*   Python 3.9+
*   Ollama installed and running ([Ollama Website](https://ollama.ai/)).
    *   A model pulled, e.g., `ollama pull qwen3:0.6b` (or your preferred small model).

## Setup & Installation

1.  **Clone the Repository (if applicable)**
    ```bash
    # git clone <repository-url>
    # cd <repository-name>
    ```

2.  **Create a Virtual Environment (Recommended)**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Initial Data Pipeline Run**
    This will create the `federal_register.db` SQLite database, set up tables, and populate it with initial data (e.g., from a defined period in 2025 or a recent period like the last 30 days, depending on current `main.py` configuration). By default, subsequent runs are incremental.
    ```bash
    python main.py --pipeline-only
    ```
    *   To force a full refresh for the initial run or subsequent runs (ignoring `last_processed_date.json`):
        ```bash
        python main.py --pipeline-only --full-refresh
        ```

## Running the Application

1.  **Ensure Ollama is Running**:
    Start your Ollama application/service if it's not already active.

2.  **Start the RAG Agent System**:
    This command first runs an incremental data pipeline update and then starts the FastAPI web server.
    ```bash
    python main.py
    ```
    *   The server will typically run on `http://localhost:8000` or `http://0.0.0.0:8000`.
    *   If you only want to start the server without running the pipeline (e.g., if data is already up-to-date):
        ```bash
        # Ensure pipeline has been run at least once before
        python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload 
        ```

3.  **Access the Chat Interface**:
    Open your web browser and navigate to `http://localhost:8000`.

## How it Works (Simplified Flow)

1.  **Data Pipeline (Daily/On-Demand)**:
    *   `downloader.py` fetches new/updated document data from the Federal Register API.
    *   `processor.py` cleans and prepares this data.
    *   `db_manager.py` (via `processor.py`) stores the documents and agency information into the `federal_register.db` SQLite database.
    *   The pipeline tracks the `last_processed_date` to perform incremental updates.

2.  **User Interaction**:
    *   User types a query into the web UI (`ui/index.html`).
    *   The UI sends the query via WebSocket to the FastAPI backend (`api/main.py`).
    *   The API routes the query to the `Agent` (`agent/agent.py`).

3.  **Agent Processing**:
    *   The `Agent` prepares a prompt for the local LLM (Ollama), including the user query and descriptions of available tools (e.g., `query_database`, `get_document_summary`).
    *   The LLM decides if a tool is needed. If so, it responds with a JSON object specifying the tool name and parameters.
    *   The `Agent` parses this JSON, executes the specified tool function (e.g., `query_database` which queries SQLite via `db_manager.py`).
    *   The tool's output (e.g., database results) is sent back to the LLM in a new prompt.
    *   The LLM summarizes the tool's output and generates a final natural language response to the user's original query.
    *   This response is sent back through the API to the UI and displayed to the user.

## Key Conditions Met

*   **No Visible Tool Calls**: Tool execution details are handled server-side and are not directly exposed to the end-user in the chat.
*   **Daily Updating Data**: The pipeline is designed for daily updates . Incremental updates ensure only new data is fetched.
*   **No LLM Code Execution**: The LLM only suggests tool calls; it does not execute arbitrary code.
*   **Agent Uses Local DB**: The agent queries the local SQLite database, not the live Federal Register API directly for user queries.
*   **Async/Non-Blocking**: The FastAPI interface and underlying database/API calls in the agent and pipeline are asynchronous.

## Data Source

*   **Federal Register API**: [https://www.federalregister.gov/developers/documentation/api/v1](https://www.federalregister.gov/developers/documentation/api/v1)
    *   The system is configured to fetch data (e.g., for specific months in 2025 or a recent period) to demonstrate functionality.

## Important Notes

*   **Demo Scope**: This is a demonstration prototype. Features like robust error handling across all edge cases, extensive logging, user authentication, and chat history management are simplified .
*   **LLM Performance**: The quality and speed of responses depend on the local LLM used with Ollama .
*   **SQLite File**: The `federal_register.db` file will be created in the project root.

## License

MIT

## Acknowledgements

- [Federal Register API](https://www.federalregister.gov/developers/documentation/api/v1)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Ollama](https://ollama.ai/)
![2025-05-18_12-08-41-072](https://github.com/user-attachments/assets/264a1663-51c5-46bb-ab6c-e2c483b345fa)


