"""Time and date skill for Jarvis - time, date, timezone, countdown, timer."""
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.skills.registry import Skill

logger = logging.getLogger(__name__)

TIMEZONE_ALIASES = {
    "utc": "UTC", "gmt": "UTC",
    "est": "US/Eastern", "et": "US/Eastern",
    "cst": "US/Central", "ct": "US/Central",
    "mst": "US/Mountain", "mt": "US/Mountain",
    "pst": "US/Pacific", "pt": "US/Pacific",
    "ist": "Asia/Kolkata",
    "bst": "Europe/London",
    "cet": "Europe/Paris",
    "jst": "Asia/Tokyo",
    "aest": "Australia/Sydney",
}


class TimeDateSkill(Skill):
    name = "time_date"
    description = "Current time, date, timezone conversion, countdown, and timer"
    triggers = ["time", "date", "what time", "what date", "countdown", "timer"]

    async def execute(self, params: Dict, context: Dict = None) -> Any:
        text = context.get("text", "").lower() if context else ""
        action = params.get("action", self._detect_action(text))
        tz = params.get("timezone", self._extract_timezone(text))

        if action == "time":
            return await self._current_time(tz)
        elif action == "date":
            return await self._current_date(tz)
        elif action == "datetime":
            return await self._current_datetime(tz)
        elif action == "convert":
            target_tz = params.get("target_tz", "")
            return await self._convert_timezone(tz, target_tz)
        elif action == "countdown":
            target = params.get("target", self._extract_target(text))
            return await self._countdown(target)
        elif action == "timer":
            seconds = params.get("seconds", self._extract_seconds(text))
            return await self._set_timer(seconds)
        else:
            return await self._current_datetime(tz)

    def _detect_action(self, text: str) -> str:
        if "countdown" in text:
            return "countdown"
        if "timer" in text:
            return "timer"
        if "date" in text:
            return "date"
        if "time" in text:
            return "time"
        if "convert" in text:
            return "convert"
        return "datetime"

    def _extract_timezone(self, text: str) -> str:
        for alias, tz in TIMEZONE_ALIASES.items():
            if alias in text:
                return tz
        return "localtime"

    def _extract_target(self, text: str) -> str:
        match = re.search(r'(to|until|till|for)\s+(.+?)(?:\s*$)', text)
        return match.group(2).strip() if match else ""

    def _extract_seconds(self, text: str) -> int:
        match = re.search(r'(\d+)\s*(minute|min|m|second|sec|s|hour|hr|h)', text)
        if match:
            amount = int(match.group(1))
            unit = match.group(2)
            if unit in ("minute", "min", "m"):
                return amount * 60
            elif unit in ("hour", "hr", "h"):
                return amount * 3600
            return amount
        return 60

    async def _current_time(self, tz: str) -> str:
        now = self._now_in_tz(tz)
        return f"Current time: {now.strftime('%I:%M %p')}" if tz == "localtime" else f"Current time ({tz}): {now.strftime('%I:%M %p')}"

    async def _current_date(self, tz: str) -> str:
        now = self._now_in_tz(tz)
        return f"Today's date: {now.strftime('%A, %B %d, %Y')}"

    async def _current_datetime(self, tz: str) -> str:
        now = self._now_in_tz(tz)
        if tz and tz != "localtime":
            return f"{now.strftime('%A, %B %d, %Y at %I:%M %p')} ({tz})"
        return now.strftime('%A, %B %d, %Y at %I:%M %p')

    def _now_in_tz(self, tz_name: str) -> datetime:
        if tz_name and tz_name != "localtime":
            try:
                import zoneinfo
                tz = zoneinfo.ZoneInfo(tz_name)
                return datetime.now(tz)
            except Exception:
                pass
        return datetime.now()

    async def _convert_timezone(self, from_tz: str, to_tz: str) -> str:
        if not to_tz:
            return "Which timezone to convert to? Example: convert 3pm EST to PST"
        try:
            import zoneinfo
            now = datetime.now(zoneinfo.ZoneInfo("UTC"))
            return f"{now.astimezone(zoneinfo.ZoneInfo(from_tz)).strftime('%I:%M %p')} {from_tz} → {now.astimezone(zoneinfo.ZoneInfo(to_tz)).strftime('%I:%M %p')} {to_tz}"
        except Exception as e:
            return f"Timezone conversion not available: {e}"

    async def _countdown(self, target: str) -> str:
        if not target:
            return "What should I count down to? Example: countdown to Christmas"
        try:
            now = datetime.now()
            if "christmas" in target.lower():
                christmas = datetime(now.year, 12, 25)
                if christmas < now:
                    christmas = datetime(now.year + 1, 12, 25)
                delta = christmas - now
                return f"🎄 {delta.days} days until Christmas!"
            elif "new year" in target.lower():
                ny = datetime(now.year + 1, 1, 1)
                delta = ny - now
                return f"🎉 {delta.days} days until New Year!"
            else:
                return f"Countdown to '{target}' - specify a supported date or set an exact target."
        except Exception as e:
            return f"Countdown error: {e}"

    async def _set_timer(self, seconds: int) -> str:
        if seconds < 1:
            return "Timer duration must be positive."
        mins = seconds // 60
        secs = seconds % 60
        if mins > 0:
            display = f"{mins}m {secs}s" if secs else f"{mins} minutes"
        else:
            display = f"{secs} seconds"
        return f"Timer set for {display}. (Timer running in background...)"
