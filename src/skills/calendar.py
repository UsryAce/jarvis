"""Calendar skill for Jarvis - manage events and schedules."""
import json
import logging
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.skills.registry import Skill

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CALENDAR_DB = DATA_DIR / "calendar.json"


class CalendarSkill(Skill):
    name = "calendar"
    description = "Manage events, create/read/update/delete schedules"
    triggers = ["calendar", "schedule", "event", "meeting", "appointment"]

    def __init__(self, jarvis=None):
        super().__init__(jarvis)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not CALENDAR_DB.exists():
            CALENDAR_DB.write_text("[]", encoding="utf-8")

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        text = context.get("text", "").lower() if context else ""
        action = params.get("action", self._detect_action(text))

        if action == "create_event":
            title = params.get("title", self._extract_title(text))
            day = params.get("day", self._extract_date(text))
            time_str = params.get("time", "")
            duration = params.get("duration", 60)
            return await self._create_event(title, day, time_str, duration)
        elif action in ("list", "list_events"):
            day = params.get("day", "")
            return await self._list_events(day)
        elif action == "today":
            return await self._list_events(datetime.now().strftime("%Y-%m-%d"))
        elif action == "week":
            return await self._list_week()
        elif action in ("delete", "remove"):
            event_id = params.get("event_id", "")
            return await self._delete_event(event_id)
        else:
            return self._help()

    def _detect_action(self, text: str) -> str:
        if any(w in text for w in ["add", "create", "new", "set"]):
            return "create_event"
        if any(w in text for w in ["list", "show", "what", "upcoming"]):
            return "list"
        if "today" in text:
            return "today"
        if "week" in text:
            return "week"
        return "list"

    def _extract_title(self, text: str) -> str:
        for t in ["meeting", "appointment", "event", "schedule"]:
            idx = text.find(t)
            if idx >= 0:
                return text[idx:].strip()
        return text.strip()

    def _extract_date(self, text: str) -> str:
        now = datetime.now()
        if "today" in text:
            return now.strftime("%Y-%m-%d")
        if "tomorrow" in text:
            return (now + timedelta(days=1)).strftime("%Y-%m-%d")
        return now.strftime("%Y-%m-%d")

    def _load_events(self) -> List[Dict]:
        try:
            return json.loads(CALENDAR_DB.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_events(self, events: List[Dict]):
        CALENDAR_DB.write_text(json.dumps(events, indent=2), encoding="utf-8")

    async def _create_event(self, title: str, day: str, time_str: str, duration: int) -> str:
        if not title:
            return "What event should I create? Example: schedule meeting tomorrow at 3pm"

        events = self._load_events()
        event = {
            "id": f"evt_{len(events) + 1}_{int(datetime.now().timestamp())}",
            "title": title,
            "day": day,
            "time": time_str or "12:00",
            "duration_minutes": duration,
            "created": datetime.now().isoformat(),
        }
        events.append(event)
        self._save_events(events)
        return f"Event created: {title} on {day} at {event['time']}"

    async def _list_events(self, day: str = "") -> str:
        events = self._load_events()
        if not events:
            return "No events scheduled."

        if day:
            filtered = [e for e in events if e.get("day") == day]
            label = day
        else:
            filtered = sorted(events, key=lambda e: e.get("day", ""))
            label = "upcoming"

        if not filtered:
            return f"No events for {label}."

        lines = [f"Events for {label}:"]
        for e in filtered[:20]:
            lines.append(f"  - {e['title']} on {e['day']} at {e.get('time', '12:00')}")
        return "\n".join(lines)

    async def _list_week(self) -> str:
        now = datetime.now()
        start = now - timedelta(days=now.weekday())
        days = [start + timedelta(days=i) for i in range(7)]
        results = []
        for d in days:
            day_str = d.strftime("%Y-%m-%d")
            day_events = await self._list_events(day_str)
            if "No events" not in day_events:
                results.append(day_events)
        return "\n\n".join(results) if results else "No events this week."

    async def _delete_event(self, event_id: str) -> str:
        events = self._load_events()
        filtered = [e for e in events if e.get("id") != event_id]
        if len(filtered) == len(events):
            return f"Event not found: {event_id}"
        self._save_events(filtered)
        return f"Event {event_id} deleted."

    def _help(self) -> str:
        return (
            "Calendar commands:\n"
            "  - schedule meeting tomorrow at 3pm\n"
            "  - what events today\n"
            "  - show this week\n"
            "  - add event Birthday on 2025-12-25"
        )
