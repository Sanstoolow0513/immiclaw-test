"""Configuration loading - merges settings.yaml, .env, and CLI overrides."""

from __future__ import annotations

import os
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

from .models import Settings, Scenario


def load_settings(config_dir: Path | None = None) -> Settings:
    """Load settings from YAML, then override with environment variables."""
    if config_dir is None:
        config_dir = Path(__file__).resolve().parent.parent / "config"

    load_dotenv()

    settings_path = config_dir / "settings.yaml"
    data: dict = {}
    if settings_path.exists():
        with open(settings_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    settings = Settings(**data)

    if api_key := os.getenv("LLM_API_KEY"):
        settings.llm.api_key = api_key
    if model := os.getenv("LLM_MODEL"):
        settings.llm.model = model
    if base_url := os.getenv("LLM_BASE_URL"):
        settings.llm.base_url = base_url
    if site_url := os.getenv("BASE_URL"):
        settings.base_url = site_url

    return settings


def load_scenario(scenario_path: str | Path) -> Scenario:
    """Load a test scenario from a YAML file.

    Replaces {timestamp} in all string values within test_data.
    """
    with open(scenario_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    timestamp = str(int(time.time()))
    if "test_data" in data and isinstance(data["test_data"], dict):
        data["test_data"] = _replace_templates(data["test_data"], {"timestamp": timestamp})

    return Scenario(**data)


def _replace_templates(obj: object, variables: dict[str, str]) -> object:
    """Recursively replace {key} placeholders in strings within dicts/lists."""
    if isinstance(obj, str):
        for key, value in variables.items():
            obj = obj.replace(f"{{{key}}}", value)
        return obj
    if isinstance(obj, dict):
        return {k: _replace_templates(v, variables) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_templates(item, variables) for item in obj]
    return obj
