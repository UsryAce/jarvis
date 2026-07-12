# 🤖 JARVIS - Local AI Assistant

> Your personal AI assistant powered by NVIDIA's cutting-edge models from [build.nvidia.com](https://build.nvidia.com/models)

JARVIS is a fully local, privacy-focused AI assistant that integrates with NVIDIA's model catalog including Nemotron, Llama 3.1, GLM, Phi, Mistral, and many more. It features a modular skill system, vector memory, voice interface, and a beautiful web UI.

## ✨ Features

- **🧠 Multiple NVIDIA Models**: Access 20+ models including Nemotron 3 Ultra, Llama 3.1 405B, GLM-4.5, Phi-3.5, Mistral, and more
- **🔧 Modular Skills**: System control, file operations, web search, code execution, calculator, weather, memory management
- **💾 Vector Memory**: Persistent memory using ChromaDB with NVIDIA embeddings
- **🎤 Voice Interface**: Speech-to-text and text-to-speech using NVIDIA Canary/FastPitch
- **🌐 Web UI**: Modern chat interface with real-time streaming
- **🔒 Privacy First**: Runs locally, your data never leaves your machine
- **📦 Extensible**: Easy to add new skills and models

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- NVIDIA API key from [build.nvidia.com](https://build.nvidia.com)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/jarvis.git
cd jarvis

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy config and add your API key
cp .env.example .env
# Edit .env and add your NVIDIA_API_KEY
```

### Get Your NVIDIA API Key

1. Go to [build.nvidia.com](https://build.nvidia.com)
2. Sign in or create an account
3. Navigate to **API Keys** and create a new key
4. Add it to your `.env` file:
   ```bash
   NVIDIA_API_KEY=nvapi-your-key-here
   ```

### Run JARVIS

**CLI Mode:**
```bash
python main.py chat
```

**Web Server:**
```bash
python main.py serve --host localhost --port 8080
```

**Single Query:**
```bash
python main.py ask "What is the capital of France?"
```

**System Check:**
```bash
python main.py doctor
```

## 📖 Usage

### Chat Commands

| Command | Description |
|---------|-------------|
| `help` | Show help |
| `status` | Show system status |
| `skills` | List available skills |
| `clear` | Clear screen |
| `exit` / `quit` | Exit JARVIS |

### Natural Language Examples

```
"Calculate 15 * 23 + sqrt(144)"
"Show me CPU and memory usage"
"Search for latest AI news"
"Run python code to sort a list"
"Remember my birthday is March 15"
"What did I say about my birthday?"
"Read file ~/.bashrc"
"List files in ~/Documents"
```

### Available Skills

| Skill | Triggers | Description |
|-------|----------|-------------|
| `system` | cpu, memory, disk, processes | System monitoring |
| `files` | read, write, list, find, copy, move | File operations |
| `web_search` | search, google, find | Web search via Google/DuckDuckGo |
| `code` | run, execute, python, javascript | Code execution |
| `memory` | remember, recall, forget | Persistent memory |
| `calculator` | calculate, math, = | Mathematical operations |
| `weather` | weather, temperature, forecast | Weather information |

## 🛠️ Configuration

Edit `config/config.yaml` or use environment variables:

```yaml
nvidia:
  api_key: ""  # Or set NVIDIA_API_KEY env var
  models:
    chat:
      - id: "nvidia/llama-3.1-nemotron-70b-instruct"
        name: "Nemotron 3 Ultra"

jarvis:
  wake_word: "jarvis"
  language: "en"

memory:
  type: "chromadb"
  path: "./data/memory"

voice:
  tts:
    engine: "nvidia"  # nvidia, edge, system
  stt:
    engine: "nvidia"

ui:
  host: "localhost"
  port: 8080
```

## 📦 Available NVIDIA Models

### Chat Models
- **Nemotron 3 Ultra** (`nvidia/llama-3.1-nemotron-70b-instruct`) - Flagship reasoning
- **Llama 3.1 405B** (`meta/llama-3.1-405b-instruct`) - Largest open model
- **Llama 3.1 70B** (`meta/llama-3.1-70b-instruct`) - Balanced performance
- **GLM-4.5 Air** (`z.ai/glm-4.5-air`) - Efficient Chinese/English
- **Phi-3.5 Mini** (`microsoft/phi-3.5-mini-instruct`) - Compact, fast
- **Mistral Large** (`mistralai/mistral-large-instruct`) - Strong reasoning
- **DeepSeek Coder** (`deepseek-ai/deepseek-coder-v2-lite-instruct`) - Code specialist

### Embedding Models
- **NV-Embed-QA-E5-v5** (`nvidia/nv-embedqa-e5-v5`) - SOTA QA embeddings
- **BGE-M3** (`baai/bge-m3`) - Multilingual, multi-granularity

### Reranking
- **NV-Rerank-QA-Mistral-4B** (`nvidia/nv-rerank-qa-mistral-4b-v3`) - QA optimized

### Vision
- **Phi-3.5 Vision** (`microsoft/phi-3.5-vision-instruct`) - Multimodal
- **Cosmos 1.0 Diffusion** (`nvidia/cosmos-1.0-diffusion-7b-text2world`) - World model

### Audio
- **Canary 1B** (`nvidia/canary-1b`) - Multilingual ASR
- **FastPitch HiFi-GAN** (`nvidia/fastpitch-hifigan`) - TTS

## 🏗️ Project Structure

```
jarvis/
├── config/              # Configuration files
│   ├── default.yaml     # Default configuration
│   └── config.yaml      # User configuration (gitignored)
├── src/
│   ├── cli/             # Command-line interface
│   ├── core/            # Core JARVIS orchestrator
│   ├── clients/         # API clients (NVIDIA, etc.)
│   ├── skills/          # Skill implementations
│   ├── memory/          # Vector memory system
│   ├── voice/           # Voice interface (TTS/STT)
│   ├── api/             # FastAPI web server
│   ├── ui/              # Web UI templates
│   ├── models/          # Model registry
│   └── config/          # Configuration loader
├── data/                # Data directory (gitignored)
│   ├── memory/          # ChromaDB persistence
│   └── logs/            # Log files
├── tests/               # Unit tests
├── main.py              # Entry point
├── setup.py             # Package setup
├── requirements.txt     # Dependencies
└── .env.example         # Environment template
```

## 🔧 Adding Custom Skills

Create a new skill in `src/skills/your_skill.py`:

```python
from src.skills.registry import Skill

class YourSkill(Skill):
    name = "your_skill"
    description = "Description of your skill"
    triggers = ["trigger", "keywords"]

    async def execute(self, params: dict, context: dict = None):
        # Your skill logic here
        return "Result"

# Register in src/skills/__init__.py
from .your_skill import YourSkill
```

Then add to `config/config.yaml`:
```yaml
skills:
  enabled:
    - "your_skill"
```

## 🌐 Web API

When running the server, these endpoints are available:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/api/chat` | POST | Chat with JARVIS |
| `/api/status` | GET | System status |
| `/api/skills` | GET | List skills |
| `/api/skills/{name}` | POST | Execute skill |
| `/api/memory/remember` | POST | Store memory |
| `/api/memory/recall` | GET | Search memories |
| `/ws` | WS | Real-time streaming |

## 🧪 Testing

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## 🙏 Acknowledgments

- [NVIDIA](https://build.nvidia.com) for the amazing model catalog
- [ChromaDB](https://www.trychroma.com) for vector storage
- [FastAPI](https://fastapi.tiangolo.com) for the web framework
- [Rich](https://rich.readthedocs.io) for beautiful CLI

---

<p align="center">Made with ❤️ for the AI community</p>
<p align="center"><b>JARVIS</b> - "Just A Rather Very Intelligent System"</p>