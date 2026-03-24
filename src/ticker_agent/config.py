"""Central configuration loader — merges settings.yaml with .env overrides."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Resolve project root regardless of where the process is started
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_DEFAULT_CONFIG = _PROJECT_ROOT / "config" / "settings.yaml"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base* (override wins on conflicts)."""
    result = base.copy()
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


@lru_cache(maxsize=1)
def load_config(config_path: str | None = None) -> dict[str, Any]:
    """Load and return the merged configuration dict.

    Precedence (highest → lowest):
      1. Environment variables  (NEWS_API_KEY, OLLAMA_MODEL, …)
      2. ``config_path`` argument
      3. ``config/settings.yaml``
    """
    load_dotenv()

    path = Path(config_path) if config_path else _DEFAULT_CONFIG
    if not path.exists():
        logger.warning("Config file not found at %s — using defaults", path)
        cfg: dict[str, Any] = {}
    else:
        with open(path) as fh:
            cfg = yaml.safe_load(fh) or {}

    # Apply environment variable overrides
    env_overrides: dict[str, Any] = {}

    if key := os.getenv("NEWS_API_KEY"):
        env_overrides.setdefault("news", {})["api_key"] = key
    if url := os.getenv("OLLAMA_BASE_URL"):
        env_overrides.setdefault("llm", {})["base_url"] = url
    if model := os.getenv("OLLAMA_MODEL"):
        env_overrides.setdefault("llm", {})["model"] = model
    if db := os.getenv("DATABASE_URL"):
        env_overrides.setdefault("database", {})["url"] = db
    if level := os.getenv("LOG_LEVEL"):
        env_overrides["log_level"] = level

    return _deep_merge(cfg, env_overrides)


def get(key: str, default: Any = None) -> Any:
    """Dot-notation accessor: ``get('llm.model')`` → cfg['llm']['model']."""
    cfg = load_config()
    parts = key.split(".")
    node: Any = cfg
    for part in parts:
        if not isinstance(node, dict):
            return default
        node = node.get(part)
        if node is None:
            return default
    return node


def setup_logging() -> None:
    """Configure root logger based on config / environment."""
    level_name = get("log_level", "INFO")
    log_file = os.getenv("LOG_FILE", get("output.log_file", "logs/ticker_agent.log"))

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    log_path = _PROJECT_ROOT / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handlers.append(logging.FileHandler(log_path))

    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=handlers,
    )
