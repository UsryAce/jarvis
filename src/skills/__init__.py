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
]