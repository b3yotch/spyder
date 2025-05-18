from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import json
import asyncio
import os
from agent.agent import Agent
from pydantic import BaseModel

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    response: str

app = FastAPI(title="Federal Registry RAG Agent API")

# Create directory for static files if it doesn't exist
os.makedirs("ui", exist_ok=True)

# Serve static files (UI)
app.mount("/static", StaticFiles(directory="ui"), name="static")

# Templates for rendering HTML
templates = Jinja2Templates(directory="ui")

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

manager = ConnectionManager()

@app.get("/", response_class=HTMLResponse)
async def get_root(request: Request):
    """Serve the index.html file"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time chat"""
    await manager.connect(websocket)
    
    # Initialize agent
    agent = Agent()
    await agent.setup()
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            try:
                user_query = json.loads(data)["query"]
            except (json.JSONDecodeError, KeyError):
                user_query = data  # Fallback to raw text if not proper JSON
            
            # Process with agent
            response = await agent.process_query(user_query)
            
            # Send response back to client
            await websocket.send_json({"response": response})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print("Client disconnected")
    except Exception as e:
        print(f"Error in WebSocket: {str(e)}")
    finally:
        # Clean up
        await agent.close()

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(chat_request: ChatRequest):
    """REST API endpoint for chat"""
    try:
        agent = Agent()
        await agent.setup()
        
        response = await agent.process_query(chat_request.query)
        
        await agent.close()
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)