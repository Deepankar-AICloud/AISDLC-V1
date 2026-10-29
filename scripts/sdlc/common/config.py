"""Configuration loading and shared paths for the Agentic SDLC platform.

All config is YAML under ``config/``. This module centralizes loading so the
rest of the platform never hardcodes paths or model names.
"""
from __future__ import annotations

import functools
import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "PyYAML is required. Install with: pip install pyyaml"
    ) from exc

# Repo root = three levels up from this file: scripts/sdlc/common/config.py
REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"
REPORTS_DIR = REPO_ROOT / "reports"
DOCS_DIR = REPO_ROOT / "docs"
STATE_DIR = REPO_ROOT / ".sdlc"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@functools.lru_cache(maxsize=None)
def load_config(name: str) -> dict[str, Any]:
    """Load a named config file from ``config/`` (without extension).

    Example: ``load_config("models")`` loads ``config/models.yml``.
    """
    return _load_yaml(CONFIG_DIR / f"{name}.yml")


def agents_config() -> dict[str, Any]:
    return load_config("agents")


def models_config() -> dict[str, Any]:
    return load_config("models")


def quality_gates_config() -> dict[str, Any]:
    return load_config("quality-gates")


def pricing_config() -> dict[str, Any]:
    return load_config("pricing")


def environments_config() -> dict[str, Any]:
    return load_config("environments")


def run_reports_dir(run_id: str) -> Path:
    """Return (and create) the reports directory for a run."""
    d = REPORTS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)
