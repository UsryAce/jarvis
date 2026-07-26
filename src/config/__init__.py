"""Configuration management."""
import io
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent


def _provider_cutover_complete(root: Path, provider: str = "nvidia") -> bool:
    """Read only non-secret cutover state before any legacy source is loaded."""

    configured_path = os.getenv("JARVIS_CONTROL_DB_PATH")
    database = Path(configured_path) if configured_path else root / "data" / "control.db"
    if not database.is_file():
        return False
    connection = None
    try:
        uri = database.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        row = connection.execute(
            "SELECT restart_required FROM provider_cutovers WHERE provider = ?",
            (provider,),
        ).fetchone()
        return row is not None
    except (OSError, sqlite3.DatabaseError):
        return False
    finally:
        if connection is not None:
            connection.close()


def _is_legacy_env_assignment(raw_line: bytes) -> bool:
    candidate = raw_line.lstrip()
    if candidate.startswith(b"export "):
        candidate = candidate[7:].lstrip()
    key, separator, _value = candidate.partition(b"=")
    return bool(separator) and key.strip() == b"NVIDIA_API_KEY"


def _load_dotenv_without_legacy_nvidia(path: Path) -> None:
    """Preserve dotenv behavior while excluding the legacy provider value."""

    if not path.is_file():
        return
    safe_lines: list[bytes] = []
    with path.open("rb") as stream:
        for raw_line in stream:
            if not _is_legacy_env_assignment(raw_line):
                safe_lines.append(raw_line)
    safe_stream = io.StringIO(b"".join(safe_lines).decode("utf-8-sig"))
    load_dotenv(stream=safe_stream, override=True)


def _yaml_without_legacy_nvidia(path: Path) -> Dict[str, Any]:
    """Parse YAML after presence-only removal of ``nvidia.api_key``."""

    if not path.is_file():
        return {}
    safe_lines: list[bytes] = []
    in_nvidia = False
    with path.open("rb") as stream:
        for raw_line in stream:
            stripped = raw_line.lstrip()
            if stripped and not stripped.startswith(b"#"):
                indentation = len(raw_line) - len(stripped)
                if indentation == 0:
                    in_nvidia = stripped.partition(b":")[0].strip() == b"nvidia"
                elif in_nvidia and stripped.partition(b":")[0].strip() == b"api_key":
                    continue
            safe_lines.append(raw_line)
    loaded = yaml.safe_load(b"".join(safe_lines).decode("utf-8-sig")) or {}
    return loaded if isinstance(loaded, dict) else {}


_NVIDIA_CUTOVER_COMPLETE = _provider_cutover_complete(project_root)
if _NVIDIA_CUTOVER_COMPLETE:
    _load_dotenv_without_legacy_nvidia(project_root / ".env")
    if "NVIDIA_API_KEY" in os.environ:
        del os.environ["NVIDIA_API_KEY"]
else:
    # Before deliberate migration, retain the legacy value only inside this
    # backend process so the CLI can import it without argv or shell exposure.
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
            if _NVIDIA_CUTOVER_COMPLETE:
                self._config = _yaml_without_legacy_nvidia(default_config)
            else:
                with open(default_config, "r", encoding="utf-8") as f:
                    self._config = yaml.safe_load(f) or {}

        # Load user config (overrides defaults)
        user_config = config_dir / "config.yaml"
        if user_config.exists():
            if _NVIDIA_CUTOVER_COMPLETE:
                user_data = _yaml_without_legacy_nvidia(user_config)
            else:
                with open(user_config, "r", encoding="utf-8") as f:
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
            "NVIDIA_API_BASE": "nvidia.api_base",
            "JARVIS_WAKE_WORD": "jarvis.wake_word",
            "JARVIS_LANGUAGE": "jarvis.language",
            "MEMORY_PATH": "memory.path",
            "MEMORY_TYPE": "memory.type",
            "LOG_LEVEL": "logging.level",
            "UI_HOST": "ui.host",
            "UI_PORT": "ui.port",
        }
        if not _NVIDIA_CUTOVER_COMPLETE:
            env_mappings["NVIDIA_API_KEY"] = "nvidia.api_key"

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
