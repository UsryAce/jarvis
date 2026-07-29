"""Note skill for Jarvis - create, read, list, and search notes."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.skills.registry import Skill

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
NOTES_DB = DATA_DIR / "notes.json"


class NoteSkill(Skill):
    name = "note"
    description = "Create, read, list, and search personal notes"
    triggers = ["note", "notes", "remember this", "take note"]

    def __init__(self, jarvis=None):
        super().__init__(jarvis)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not NOTES_DB.exists():
            NOTES_DB.write_text("[]", encoding="utf-8")

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        text = context.get("text", "").lower() if context else ""
        action = params.get("action", self._detect_action(text))

        if action == "create":
            content = params.get("content", self._extract_content(text))
            title = params.get("title", self._extract_title(text, content))
            return await self._create_note(title, content)
        elif action == "list":
            return await self._list_notes()
        elif action == "search":
            query = params.get("query", self._extract_query(text))
            return await self._search_notes(query)
        elif action == "read":
            note_id = params.get("note_id", "")
            return await self._read_note(note_id)
        elif action == "delete":
            note_id = params.get("note_id", "")
            return await self._delete_note(note_id)
        else:
            return "Note commands: take note <content>, list notes, search notes <query>, read note <id>"

    def _detect_action(self, text: str) -> str:
        if any(w in text for w in ["remember this", "take note", "save", "new"]):
            return "create"
        if any(w in text for w in ["search", "find"]):
            return "search"
        if any(w in text for w in ["list", "all"]):
            return "list"
        if "read" in text:
            return "read"
        if "delete" in text:
            return "delete"
        if text.strip():
            return "create"
        return "list"

    def _extract_content(self, text: str) -> str:
        for t in ["remember this", "take note", "note", "save"]:
            idx = text.find(t)
            if idx >= 0:
                return text[idx + len(t):].strip(" :")
        return text.strip()

    def _extract_title(self, text: str, content: str) -> str:
        if content:
            words = content.split()[:6]
            return " ".join(words)
        return f"Note {datetime.now().strftime('%H:%M')}"

    def _extract_query(self, text: str) -> str:
        for t in ["search", "find"]:
            idx = text.find(t)
            if idx >= 0:
                return text[idx + len(t):].strip()
        return text.strip()

    def _load_notes(self) -> List[Dict]:
        try:
            return json.loads(NOTES_DB.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_notes(self, notes: List[Dict]):
        NOTES_DB.write_text(json.dumps(notes, indent=2), encoding="utf-8")

    async def _create_note(self, title: str, content: str) -> str:
        if not content:
            return "What should I note down?"
        notes = self._load_notes()
        note = {
            "id": f"note_{len(notes) + 1}_{int(datetime.now().timestamp())}",
            "title": title or "Untitled",
            "content": content,
            "created": datetime.now().isoformat(),
        }
        notes.insert(0, note)
        self._save_notes(notes)
        display = content[:100] + "..." if len(content) > 100 else content
        return f"Note saved: {display}"

    async def _list_notes(self) -> str:
        notes = self._load_notes()
        if not notes:
            return "No notes yet."
        lines = [f"Notes ({len(notes)}):"]
        for n in notes[:25]:
            title = n.get("title", "Untitled")
            created = n.get("created", "")[:10]
            lines.append(f"  [{n['id']}] {title} ({created})")
        return "\n".join(lines)

    async def _search_notes(self, query: str) -> str:
        if not query:
            return await self._list_notes()
        notes = self._load_notes()
        q = query.lower()
        matches = [n for n in notes if q in n.get("content", "").lower() or q in n.get("title", "").lower()]
        if not matches:
            return f"No notes matching '{query}'."
        lines = [f"Found {len(matches)} notes:"]
        for n in matches[:10]:
            preview = n.get("content", "")[:80]
            lines.append(f"  [{n['id']}] {preview}")
        return "\n".join(lines)

    async def _read_note(self, note_id: str) -> str:
        notes = self._load_notes()
        for n in notes:
            if n["id"] == note_id:
                title = n.get("title", "Untitled")
                content = n.get("content", "")
                created = n.get("created", "")
                return f"**{title}** ({created})\n\n{content}"
        return f"Note not found: {note_id}"

    async def _delete_note(self, note_id: str) -> str:
        notes = self._load_notes()
        filtered = [n for n in notes if n["id"] != note_id]
        if len(filtered) == len(notes):
            return f"Note not found: {note_id}"
        self._save_notes(filtered)
        return f"Note {note_id} deleted."
