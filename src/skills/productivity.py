"""Productivity skill for Jarvis - pomodoro timer, todo, focus mode."""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.skills.registry import Skill

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
TODO_DB = DATA_DIR / "todos.json"
POMODORO_DEFAULT_MINUTES = 25


class ProductivitySkill(Skill):
    name = "productivity"
    description = "Pomodoro timer, todo list management, and focus mode"
    triggers = ["pomodoro", "focus", "todo", "task", "productivity"]

    def __init__(self, jarvis=None):
        super().__init__(jarvis)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not TODO_DB.exists():
            TODO_DB.write_text("[]", encoding="utf-8")

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        text = context.get("text", "").lower() if context else ""
        action = params.get("action", self._detect_action(text))

        if action == "pomodoro":
            minutes = params.get("minutes", self._extract_minutes(text))
            return await self._start_pomodoro(minutes)
        elif action == "todo_add":
            task = params.get("task", self._extract_task(text))
            return await self._add_todo(task)
        elif action == "todo_list":
            return await self._list_todos()
        elif action == "todo_done":
            todo_id = params.get("todo_id", self._extract_id(text))
            return await self._complete_todo(todo_id)
        elif action == "todo_delete":
            todo_id = params.get("todo_id", self._extract_id(text))
            return await self._delete_todo(todo_id)
        elif action == "focus":
            return self._focus_mode()
        else:
            return self._help()

    def _detect_action(self, text: str) -> str:
        if "pomodoro" in text:
            return "pomodoro"
        if any(w in text for w in ["focus", "concentrate"]):
            return "focus"
        if any(w in text for w in ["todo", "task", "add", "create"]):
            if any(w in text for w in ["list", "show", "all"]):
                return "todo_list"
            return "todo_add"
        if "done" in text or "complete" in text:
            return "todo_done"
        if "delete" in text or "remove" in text:
            return "todo_delete"
        if text.strip():
            return "todo_add"
        return "todo_list"

    def _extract_minutes(self, text: str) -> int:
        import re
        match = re.search(r'(\d+)\s*(minute|min|m)', text)
        return int(match.group(1)) if match else POMODORO_DEFAULT_MINUTES

    def _extract_task(self, text: str) -> str:
        for t in ["add todo", "add task", "todo", "task"]:
            idx = text.find(t)
            if idx >= 0:
                return text[idx + len(t):].strip()
        return text.strip()

    def _extract_id(self, text: str) -> str:
        import re
        match = re.search(r'todo_[a-z0-9]+', text)
        return match.group(0) if match else ""

    def _load_todos(self) -> List[Dict]:
        try:
            return json.loads(TODO_DB.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_todos(self, todos: List[Dict]):
        TODO_DB.write_text(json.dumps(todos, indent=2), encoding="utf-8")

    async def _start_pomodoro(self, minutes: int) -> str:
        if minutes < 1:
            return "Pomodoro duration must be at least 1 minute."
        end_time = datetime.now() + timedelta(minutes=minutes)
        return (
            f"🍅 Pomodoro timer started for {minutes} minutes "
            f"(ends at {end_time.strftime('%I:%M %p')}). "
            f"Focus until the timer rings!"
        )

    async def _add_todo(self, task: str) -> str:
        if not task:
            return "What task should I add? Example: add todo finish report"

        todos = self._load_todos()
        todo = {
            "id": f"todo_{int(datetime.now().timestamp())}_{len(todos)}",
            "task": task,
            "done": False,
            "created": datetime.now().isoformat(),
        }
        todos.append(todo)
        self._save_todos(todos)
        return f"Task added: {task}"

    async def _list_todos(self) -> str:
        todos = self._load_todos()
        if not todos:
            return "No tasks. Add one with: add todo <task>"

        pending = [t for t in todos if not t.get("done")]
        done = [t for t in todos if t.get("done")]

        lines = []
        if pending:
            lines.append(f"Tasks to do ({len(pending)}):")
            for t in pending[:20]:
                lines.append(f"  [ ] [{t['id']}] {t['task']}")
        if done:
            lines.append(f"\nCompleted ({len(done)}):")
            for t in done[:10]:
                lines.append(f"  [✓] {t['task']}")
        return "\n".join(lines) if lines else "No tasks yet."

    async def _complete_todo(self, todo_id: str) -> str:
        todos = self._load_todos()
        for t in todos:
            if t["id"] == todo_id:
                t["done"] = True
                t["completed"] = datetime.now().isoformat()
                self._save_todos(todos)
                return f"Task completed: {t['task']}"
        return f"Task not found: {todo_id}"

    async def _delete_todo(self, todo_id: str) -> str:
        todos = self._load_todos()
        filtered = [t for t in todos if t["id"] != todo_id]
        if len(filtered) == len(todos):
            return f"Task not found: {todo_id}"
        self._save_todos(filtered)
        return f"Task deleted."

    def _focus_mode(self) -> str:
        return (
            "Focus mode tips:\n"
            "  1. Start a pomodoro: pomodoro 25\n"
            "  2. Check your todos: list todos\n"
            "  3. Close distracting apps\n"
            "  4. Use a website blocker\n"
            "  5. Take 5-min breaks between pomodoros"
        )

    def _help(self) -> str:
        return (
            "Productivity commands:\n"
            "  - pomodoro <minutes> - start focus timer\n"
            "  - add todo <task> - add a task\n"
            "  - list todos - show all tasks\n"
            "  - done <id> - mark task complete\n"
            "  - focus - focus mode tips"
        )
