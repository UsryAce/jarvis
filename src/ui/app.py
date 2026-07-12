"""FastAPI Web UI for JARVIS."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.api.server import app, jarvis
from src.config import config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - just yield since jarvis is initialized in server lifespan."""
    yield


# Use the app from server module
# The jarvis instance is initialized in server module lifespan


# Templates
templates = Jinja2Templates(directory="src/ui/templates")

# Static files
static_dir = Path("src/ui/static")
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class ChatRequest(BaseModel):
    message: str
    model: str = None
    stream: bool = False
    use_memory: bool = True
    use_skills: bool = True


class ChatResponse(BaseModel):
    response: str
    model: str


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve web UI."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with Jarvis."""
    response = await jarvis.chat(
        request.message,
        model=request.model,
        use_memory=request.use_memory,
        use_skills=request.use_skills,
    )
    return ChatResponse(response=response, model=request.model or "default")


@app.get("/api/status")
async def status():
    """Get system status."""
    return jarvis.get_status()


@app.get("/api/skills")
async def skills():
    """List available skills."""
    return {"skills": jarvis.get_available_skills()}


@app.post("/api/skills/{skill_name}")
async def execute_skill(skill_name: str, params: dict = {}):
    """Execute a skill."""
    try:
        result = await jarvis.execute_skill(skill_name, params)
        return {"result": result}
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/memory/remember")
async def remember(content: str, metadata: dict = {}):
    """Store a memory."""
    memory_id = await jarvis.remember(content, metadata)
    return {"id": memory_id}


@app.get("/api/memory/recall")
async def recall(query: str, limit: int = 5):
    """Search memories."""
    memories = await jarvis.recall(query, limit)
    return {"memories": memories}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time chat."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            response = await jarvis.chat(data)
            await websocket.send_text(response)
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    import os

    # Use 0.0.0.0 in production/Docker to bind to all interfaces
    default_host = "0.0.0.0" if os.getenv("DOCKER_CONTAINER") else "localhost"
    uvicorn.run(
        "src.ui.app:app",
        host=config.get("ui.host", default_host),
        port=config.get("ui.port", 8080),
        reload=not os.getenv("DOCKER_CONTAINER"),
    )