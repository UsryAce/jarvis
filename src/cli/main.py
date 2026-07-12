"""Main CLI for JARVIS."""
import asyncio
import sys
import os
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import config
from src.core.jarvis import Jarvis

console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="JARVIS")
def cli():
    """JARVIS - Your Local AI Assistant powered by NVIDIA models."""
    pass


@cli.command()
@click.option("--host", default=None, help="Host to bind to")
@click.option("--port", default=None, type=int, help="Port to bind to")
def serve(host, port):
    """Start the JARVIS web server."""
    console.print(Panel.fit(
        "🤖 [bold cyan]JARVIS Web Server[/bold cyan]\n"
        "Starting server...",
        border_style="cyan"
    ))

    # Import here to avoid circular imports
    import uvicorn

    # Use 0.0.0.0 in production/Docker to bind to all interfaces
    default_host = "0.0.0.0" if os.getenv("DOCKER_CONTAINER") else "localhost"
    default_port = int(config.get("ui.port", 8080))
    uvicorn.run(
        "src.ui.app:app",
        host=host or config.get("ui.host", default_host),
        port=port or default_port,
        reload=not os.getenv("DOCKER_CONTAINER"),
    )


@cli.command()
def chat():
    """Start interactive chat with JARVIS."""
    console.print(Panel.fit(
        "[JARVIS] [bold cyan]JARVIS Interactive Chat[/bold cyan]\n"
        "Type 'exit' or 'quit' to leave\n"
        "Type 'help' for commands",
        border_style="cyan"
    ))

    asyncio.run(_run_chat())


async def _run_chat():
    """Run the chat loop."""
    jarvis = Jarvis()
    await jarvis.initialize()

    console.print("[green]JARVIS is ready![/green]")

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]")

            if user_input.lower() in ("exit", "quit", "bye"):
                console.print("[yellow]Goodbye![/yellow]")
                break

            if user_input.lower() in ("help", "?"):
                _show_help()
                continue

            if user_input.lower() == "status":
                status = jarvis.get_status()
                console.print(f"[green]Status: {status}[/green]")
                continue

            if user_input.lower().startswith("model "):
                model = user_input[6:].strip()
                console.print(f"[yellow]Model switching not yet implemented[/yellow]")
                continue

            console.print("[dim]JARVIS is thinking...[/dim]")
            response = await jarvis.chat(user_input)
            console.print(f"[bold green]JARVIS[/bold green]: {response}")

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")

    await jarvis.shutdown()


def _show_help():
    """Show help message."""
    console.print(Panel("""
[bold]Available Commands:[/bold]
  [cyan]help[/cyan] / [cyan]?[/cyan]     - Show this help
  [cyan]exit[/cyan] / [cyan]quit[/cyan]   - Exit chat
  [cyan]status[/cyan]       - Show system status
  [cyan]model <name>[/cyan] - Switch model (not implemented)

[bold]Example Queries:[/bold]
  "What's the weather in New York?"
  "Search for Python asyncio tutorial"
  "Run python code: print('hello')"
  "Remember that my API key is xyz"
  "What did I ask you to remember?"
  "Calculate 15 * 23 + 45"
  "Show me system info"
  "List files in current directory"
""", title="Help", border_style="green"))


@cli.command()
@click.argument("message")
def ask(message):
    """Ask JARVIS a single question."""
    asyncio.run(_ask_once(message))


async def _ask_once(message: str):
    """Ask a single question."""
    jarvis = Jarvis()
    await jarvis.initialize()

    response = await jarvis.chat(message)
    console.print(f"[bold green]JARVIS[/bold green]: {response}")

    await jarvis.shutdown()


@cli.command()
def models():
    """List available NVIDIA models."""
    from src.models.nvidia_models import get_models_by_type, ModelType

    console.print(Panel.fit("[bold]Available NVIDIA Models[/bold]", border_style="cyan"))

    for model_type in ModelType:
        models = get_models_by_type(model_type)
        if models:
            console.print(f"\n[bold]{model_type.value.upper()}[/bold]")
            for model in models:
                console.print(f"  • [cyan]{model.id}[/cyan] - {model.name}")
                console.print(f"    {model.description}")
                console.print(f"    Context: {model.context_window:,} | Output: {model.max_output}")


@cli.command()
@click.option("--api-key", prompt=True, hide_input=True, help="NVIDIA API Key")
def configure(api_key):
    """Configure JARVIS with API key."""
    env_file = Path(".env")
    content = f"NVIDIA_API_KEY={api_key}\n"

    if env_file.exists():
        existing = env_file.read_text()
        if "NVIDIA_API_KEY" in existing:
            # Replace existing
            import re
            content = re.sub(r"NVIDIA_API_KEY=.*", f"NVIDIA_API_KEY={api_key}", existing)
        else:
            content = existing + "\n" + content

    env_file.write_text(content)
    console.print("[green]Configuration saved to .env[/green]")


@cli.command()
def test():
    """Test NVIDIA API connection."""
    asyncio.run(_test_api())


async def _test_api():
    """Test API connection."""
    from src.clients.nvidia_client import NVIDIAClient

    console.print("[dim]Testing NVIDIA API...[/dim]")

    try:
        async with NVIDIAClient() as client:
            response = await client.chat_completion(
                messages=[{"role": "user", "content": "Hello, respond with 'OK'"}],
                max_tokens=10,
            )
            content = response["choices"][0]["message"]["content"]
            console.print(f"[green]✓ API Connected[/green] - Response: {content}")
    except Exception as e:
        console.print(f"[red]✗ API Error: {e}[/red]")
        console.print("[yellow]Make sure NVIDIA_API_KEY is set in .env[/yellow]")


@cli.command()
def init():
    """Initialize JARVIS project structure."""
    dirs = [
        "data/memory",
        "data/cache",
        "logs",
        "config",
    ]

    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        console.print(f"[green]Created {d}[/green]")

    # Create .env from example
    env_example = Path(".env.example")
    env_file = Path(".env")

    if env_example.exists() and not env_file.exists():
        import shutil
        shutil.copy(env_example, env_file)
        console.print("[yellow]Created .env from .env.example - please add your API keys[/yellow]")

    console.print("[bold green]JARVIS initialized![/bold green]")
    console.print("Next steps:")
    console.print("  1. Add your NVIDIA_API_KEY to .env")
    console.print("  2. Run: python main.py test")
    console.print("  3. Run: python main.py chat")


if __name__ == "__main__":
    cli()