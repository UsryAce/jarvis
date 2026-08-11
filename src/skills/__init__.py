"""Skills package."""
from src.skills.registry import Skill, SkillRegistry, skill
from src.skills.system import SystemSkill
from src.skills.files import FilesSkill
from src.skills.web_search import WebSearchSkill
from src.skills.code import CodeSkill
from src.skills.memory import MemorySkill
from src.skills.calculator import CalculatorSkill
from src.skills.weather import WeatherSkill
from src.skills.trading import TradingSkill
from src.skills.business import BusinessSkill
from src.skills.education import EducationSkill
from src.skills.design import DesignSkill
from src.skills.email import EmailSkill
from src.skills.calendar import CalendarSkill
from src.skills.news import NewsSkill
from src.skills.note import NoteSkill
from src.skills.translation import TranslationSkill
from src.skills.reminder import ReminderSkill
from src.skills.search import SearchSkill
from src.skills.time_date import TimeDateSkill
from src.skills.knowledge import KnowledgeSkill
from src.skills.productivity import ProductivitySkill
from src.skills.nvidia_catalog import NvidiaSkill, NvidiaSkillsCatalog

__all__ = [
    "Skill",
    "SkillRegistry",
    "skill",
    "SystemSkill",
    "FilesSkill",
    "WebSearchSkill",
    "CodeSkill",
    "MemorySkill",
    "CalculatorSkill",
    "WeatherSkill",
    "TradingSkill",
    "BusinessSkill",
    "EducationSkill",
    "DesignSkill",
    "EmailSkill",
    "CalendarSkill",
    "NewsSkill",
    "NoteSkill",
    "TranslationSkill",
    "ReminderSkill",
    "SearchSkill",
    "TimeDateSkill",
    "KnowledgeSkill",
    "ProductivitySkill",
    "NvidiaSkill",
    "NvidiaSkillsCatalog",
]
