"""Config loading and response parsing for llm_proxy."""

from __future__ import annotations

from pathlib import Path

import pytest

from immiclaw_test.llm_proxy.config_loader import load_providers
from immiclaw_test.llm_proxy.runner import (
    parse_gemini_models,
    parse_openai_style_model_ids,
    pick_gemini_model,
)


def test_load_providers_minimal(tmp_path: Path) -> None:
    p = tmp_path / "p.yaml"
    p.write_text(
        """
proxy_host_default: "127.0.0.1"
anthropic_version: "2023-06-01"
providers:
  - port: 9999
    name: test
    target_host: "https://example.com"
    api_family: openai
    env_key: TEST_KEY
    list_path: "/v1/models"
    chat_path: "/v1/chat/completions"
    auth_style: bearer
""",
        encoding="utf-8",
    )
    cfg = load_providers(p)
    assert cfg.proxy_host_default == "127.0.0.1"
    assert len(cfg.providers) == 1
    assert cfg.providers[0].port == 9999


def test_parse_openai_style_model_ids() -> None:
    data = {"data": [{"id": "a"}, {"id": "b"}]}
    assert parse_openai_style_model_ids(data) == ["a", "b"]


def test_parse_gemini_models_and_pick() -> None:
    data = {
        "models": [
            {
                "name": "models/embedding-only",
                "supportedGenerationMethods": ["embedContent"],
            },
            {
                "name": "models/gemini-flash",
                "supportedGenerationMethods": ["generateContent"],
            },
        ]
    }
    parsed = parse_gemini_models(data)
    assert pick_gemini_model(parsed) == "models/gemini-flash"


def test_load_providers_env_missing_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PROVIDERS_YAML", str(tmp_path / "nope.yaml"))
    with pytest.raises(FileNotFoundError):
        load_providers()
