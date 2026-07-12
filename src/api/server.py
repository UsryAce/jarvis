"""FastAPI server for Jarvis web interface."""
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.core.jarvis import Jarvis
from src.config import config


# Global Jarvis instance - will be initialized in lifespan
jarvis: Jarvis = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan."""
    global jarvis
    jarvis = Jarvis()
    await jarvis.initialize()
    yield
    await jarvis.shutdown()


app = FastAPI(
    title="JARVIS API",
    description="AI Assistant API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.get("security.allowed_origins", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
try:
    app.mount("/static", StaticFiles(directory="web/static"), name="static")
except:
    pass


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None
    stream: bool = False
    use_memory: bool = True
    use_skills: bool = True


class ChatResponse(BaseModel):
    response: str
    model: str


class SkillRequest(BaseModel):
    skill: str
    params: dict = {}


class RememberRequest(BaseModel):
    content: str
    metadata: dict = {}


class ExecuteSkillRequest(BaseModel):
    params: dict = {}


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve web UI."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>JARVIS</title>
        <style>
            body { font-family: system-ui; max-width: 800px; margin: 0 auto; padding: 20px; }
            .chat { border: 1px solid #ddd; height: 400px; overflow-y: auto; padding: 10px; margin-bottom: 10px; }
            .msg { margin: 10px 0; padding: 10px; border-radius: 10px; }
            .user { background: #007bff; color: white; text-align: right; }
            .assistant { background: #f0f0f0; }
            input { width: 70%; padding: 10px; }
            button { padding: 10px 20px; }
        </style>
    </head>
    <body>
        <h1>🤖 JARVIS</h1>
        <div id="chat" class="chat"></div>
        <input id="input" placeholder="Ask JARVIS..." onkeypress="if(event.key==='Enter') send()">
        <button onclick="send()">Send</button>
        <script>
            async function send() {
                const input = document.getElementById('input');
                const msg = input.value.trim();
                if (!msg) return;
                addMessage(msg, 'user');
                input.value = '';

                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg})
                });
                const data = await res.json();
                addMessage(data.response, 'assistant');
            }
            function addMessage(text, type) {
                const chat = document.getElementById('chat');
                const div = document.createElement('div');
                div.className = 'msg ' + type;
                div.textContent = (type === 'user' ? 'You: ' : 'JARVIS: ') + text;
                chat.appendChild(div);
                chat.scrollTop = chat.scrollHeight;
            }
        </script>
    </body>
    </html>
    """


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
async def execute_skill(skill_name: str, request: ExecuteSkillRequest):
    """Execute a skill."""
    try:
        result = await jarvis.execute_skill(skill_name, request.params)
        return {"result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/memory/remember")
async def remember(request: RememberRequest):
    """Store a memory."""
    memory_id = await jarvis.remember(request.content, request.metadata)
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


def create_app() -> FastAPI:
    """Create the FastAPI app."""
    return app