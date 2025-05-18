# Federal Registry RAG Agent

A chat-based Retrieval Augmented Generation (RAG) system that allows users to query Federal Registry documents using natural language. The system includes a data pipeline that updates daily from the Federal Register API.

## Features

- **Daily Data Updates**: Automatically fetches the latest documents from the Federal Register API
- **Asynchronous Backend**: Built with FastAPI and uses async Python for optimal performance
- **MySQL Database**: Stores document data for efficient retrieval
- **Agent-based LLM**: Uses function calling to query the database and generate responses
- **Clean UI**: Simple chat interface for interacting with the agent

## Prerequisites

- Python 3.9+
- MySQL Server
- Ollama (for running local LLMs) or OpenAI API key

## Setup

### 1. Create a MySQL Database

```sql
CREATE DATABASE rag_agent;
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Database Connection

Edit the `database/db_manager.py` file and update the database connection settings:

```python
def __init__(self, host='localhost', user='your_username', password='your_password', db='rag_agent'):
    # ...
```

### 4. Install and Start Ollama (Optional for Local LLM)

Follow the instructions at [Ollama.ai](https://ollama.ai/) to install Ollama.

Pull the qwen2.5 model:

```bash
ollama pull qwen2.5:7b
```

### 5. Run Initial Data Pipeline

```bash
python main.py --pipeline-only --days 30
```

This will download Federal Register documents from the past 30 days and store them in the database.

### 6. Start the Server

```bash
python main.py --port 8000
```

## Usage

1. Open your browser and navigate to `http://localhost:8000`
2. Start chatting with the agent by asking questions about Federal Register documents
3. The agent will use its tools to search the database and provide answers

## Example Queries

- "What executive orders were published in the last month?"
- "Find documents related to climate change"
- "What new rules were published by EPA this year?"

## Updating Data

The data pipeline will run automatically when the server starts. By default, it uses incremental updates to only download new documents since the last update, which is much faster and more efficient.

To manually update the data with incremental updates (only fetch new documents):
```bash
python main.py --pipeline-only
```

To force a full refresh of all data (useful if your database is corrupted or you want to start from scratch):
```bash
python main.py --pipeline-only --full-refresh
```

You can also specify the number of days to look back for a full refresh:
```bash
python main.py --pipeline-only --full-refresh --days 60
```

## Project Structure

- `main.py`: Main entry point for the application
- `data_pipeline/`: Data pipeline components
  - `downloader.py`: Downloads data from the Federal Register API
  - `processor.py`: Processes and stores data in the database
- `database/`: Database components
  - `db_manager.py`: Handles database connections and queries
- `agent/`: Agent components
  - `agent.py`: Implements the LLM agent with tool calling
- `api/`: API components
  - `main.py`: FastAPI server and WebSocket endpoints
- `ui/`: User interface
  - `index.html`: HTML/CSS/JS for the chat interface

## License

MIT

## Acknowledgements

- [Federal Register API](https://www.federalregister.gov/developers/documentation/api/v1)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Ollama](https://ollama.ai/)
- [OpenAI](https://openai.com/) 