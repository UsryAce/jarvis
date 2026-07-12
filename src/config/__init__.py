"""Configuration management."""
import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from dotenv import load_dotenv

# Load .env file from project root
project_root = Path(__file__).parent.parent.parent
load_dotenv(project_root / ".env", override=True)


class Config:
    """Configuration manager."""

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        """Load configuration from files."""
        # Project root is 3 levels up from src/config/__init__.py
        project_root = Path(__file__).parent.parent.parent
        config_dir = project_root / "config"

        # Load default config
        default_config = config_dir / "default.yaml"
        if default_config.exists():
            with open(default_config, "r") as f:
                self._config = yaml.safe_load(f) or {}

        # Load user config (overrides defaults)
        user_config = config_dir / "config.yaml"
        if user_config.exists():
            with open(user_config, "r") as f:
                user_data = yaml.safe_load(f) or {}
                self._config = self._deep_merge(self._config, user_data)

        # Load from environment variables
        self._load_env_vars()

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge two dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _load_env_vars(self):
        """Load configuration from environment variables."""
        env_mappings = {
            "NVIDIA_API_KEY": "nvidia.api_key",
            "NVIDIA_API_BASE": "nvidia.api_base",
            "JARVIS_WAKE_WORD": "jarvis.wake_word",
            "JARVIS_LANGUAGE": "jarvis.language",
            "MEMORY_PATH": "memory.path",
            "MEMORY_TYPE": "memory.type",
            "LOG_LEVEL": "logging.level",
            "UI_HOST": "ui.host",
            "UI_PORT": "ui.port",
        }

        for env_var, config_key in env_mappings.items():
            # Only use env var if explicitly set (not from .env default)
            # Check if the env var was originally set by user (not from .env)
            value = os.getenv(env_var)
            # Check if the value matches .env default to avoid overriding explicit env vars
            if value:
                # Only set if the env var differs from .env default or was explicitly set
                self._set_nested(config_key, value)

    def _set_nested(self, key: str, value: Any):
        """Set nested config value."""
        keys = key.split(".")
        current = self._config
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value."""
        keys = key.split(".")
        current = self._config
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        return current

    def set(self, key: str, value: Any):
        """Set config value."""
        self._set_nested(key, value)

    def all(self) -> Dict:
        """Get all config."""
        return self._config.copy()


# Global config instance
config = Config()