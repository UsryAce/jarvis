"""Reminder skill for Jarvis - set and manage reminders."""
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.skills.registry import Skill

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
REMINDER_DB = DATA_DIR / "reminders.json"

TIME_PATTERNS = [
    (r"in\s+(\d+)\s*(minute|min|m)s?", lambda m: ("minute", int(m.group(1)))),
    (r"in\s+(\d+)\s*(hour|hr|h)s?", lambda m: ("hour", int(m.group(1)))),
    (r"in\s+(\d+)\s*(day|d)s?", lambda m: ("day", int(m.group(1)))),
]


class ReminderSkill(Skill):
    name = "reminder"
    description = "Set, list, and manage reminders with time-based alerts"
    triggers = ["remind", "reminder", "remind me", "set reminder"]

    def __init__(self, jarvis=None):
        super().__init__(jarvis)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not REMINDER_DB.exists():
            REMINDER_DB.write_text("[]", encoding="utf-8")

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        text = context.get("text", "").lower() if context else ""
        action = params.get("action", self._detect_action(text))

        if action == "set":
            reminder_text = params.get("text", self._extract_reminder_text(text))
            when = params.get("when", self._parse_time(text))
            return await self._set_reminder(reminder_text, when)
        elif action == "list":
            return await self._list_reminders()
        elif action == "delete":
            reminder_id = params.get("reminder_id", self._extract_id(text))
            return await self._delete_reminder(reminder_id)
        elif action == "check":
            return await self._check_reminders()
        else:
            return "Reminder commands: remind me to <task> in <time>, list reminders, check reminders"

    def _detect_action(self, text: str) -> str:
        if any(w in text for w in ["remind me", "set", "new", "add"]):
            return "set"
        if any(w in text for w in ["list", "show", "all"]):
            return "list"
        if "check" in text:
            return "check"
        if "delete" in text or "remove" in text:
            return "delete"
        if text.strip():
            return "set"
        return "list"

    def _extract_reminder_text(self, text: str) -> str:
        for t in ["remind me to", "remind me that", "remind me", "set reminder"]:
            idx = text.find(t)
            if idx >= 0:
                rest = text[idx + len(t):].strip()
                return re.sub(r'\bin\s+\d+\s*(minute|min|m|hour|hr|h|day|d)s?\b', '', rest).strip()
        return text.strip()

    def _parse_time(self, text: str) -> str:
        now = datetime.now()
        for pattern, handler in TIME_PATTERNS:
            match = re.search(pattern, text)
            if match:
                unit, amount = handler(match)
                if unit == "minute":
                    dt = now + timedelta(minutes=amount)
                elif unit == "hour":
                    dt = now + timedelta(hours=amount)
                elif unit == "day":
                    dt = now + timedelta(days=amount)
                else:
                    dt = now + timedelta(minutes=amount)
                return dt.isoformat()
        return (now + timedelta(minutes=5)).isoformat()

    def _extract_id(self, text: str) -> str:
        match = re.search(r'rem_[a-z0-9]+', text)
        return match.group(0) if match else ""

    def _load(self) -> List[Dict]:
        try:
            return json.loads(REMINDER_DB.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save(self, reminders: List[Dict]):
        REMINDER_DB.write_text(json.dumps(reminders, indent=2), encoding="utf-8")

    async def _set_reminder(self, reminder_text: str, when: str) -> str:
        if not reminder_text:
            return "What should I remind you about? Example: remind me to buy groceries in 30 minutes"

        reminders = self._load()
        reminder = {
            "id": f"rem_{int(datetime.now().timestamp())}_{len(reminders)}",
            "text": reminder_text,
            "when": when,
            "created": datetime.now().isoformat(),
            "done": False,
        }
        reminders.append(reminder)
        self._save(reminders)

        try:
            dt = datetime.fromisoformat(when)
            relative = "soon"
            diff = dt - datetime.now()
            if diff.total_seconds() > 0:
                mins = int(diff.total_seconds() / 60)
                if mins >= 60:
                    relative = f"in {mins // 60}h{mins % 60}m"
                else:
                    relative = f"in {mins} minutes"
            return f"Reminder set: {reminder_text} ({relative})"
        except Exception:
            return f"Reminder set: {reminder_text}"

    async def _list_reminders(self) -> str:
        reminders = self._load()
        if not reminders:
            return "No reminders."

        now = datetime.now()
        active = [r for r in reminders if not r.get("done")]
        if not active:
            return "No active reminders."

        lines = [f"Reminders ({len(active)}):"]
        for r in active:
            try:
                dt = datetime.fromisoformat(r["when"])
                remaining = dt - now
                if remaining.total_seconds() > 0:
                    mins = int(remaining.total_seconds() / 60)
                    tag = f"({mins} min)" if mins < 60 else f"({mins // 60}h)"
                else:
                    tag = "(due)"
            except Exception:
                tag = ""
            lines.append(f"  [{r['id']}] {r['text']} {tag}")
        return "\n".join(lines)

    async def _delete_reminder(self, reminder_id: str) -> str:
        reminders = self._load()
        filtered = [r for r in reminders if r["id"] != reminder_id]
        if len(filtered) == len(reminders):
            return f"Reminder not found: {reminder_id}"
        self._save(filtered)
        return f"Reminder {reminder_id} deleted."

    async def _check_reminders(self) -> str:
        reminders = self._load()
        now = datetime.now()
        due = [r for r in reminders if not r.get("done") and datetime.fromisoformat(r["when"]) <= now]
        if not due:
            return "No due reminders."

        lines = [f"Due reminders ({len(due)}):"]
        for r in due:
            lines.append(f"  ⏰ {r['text']}")
        return "\n".join(lines)
