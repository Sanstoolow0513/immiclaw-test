"""Load and parse providers.yaml (bundled, env, or explicit path)."""

from __future__ import annotations

import os
from importlib.resources import files
from pathlib import Path

import yaml

from .models import ProvidersFile


def load_providers(path: Path | None = None) -> ProvidersFile:
    if path is not None:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return ProvidersFile.model_validate(raw)

    env = os.environ.get("PROVIDERS_YAML", "").strip()
    if env:
        ep = Path(env)
        if not ep.is_file():
            msg = f"PROVIDERS_YAML is not a file: {ep}"
            raise FileNotFoundError(msg)
        raw = yaml.safe_load(ep.read_text(encoding="utf-8"))
        return ProvidersFile.model_validate(raw)

    txt = (
        files("immiclaw_test.llm_proxy.data").joinpath("providers.yaml").read_text(encoding="utf-8")
    )
    raw = yaml.safe_load(txt)
    return ProvidersFile.model_validate(raw)


def effective_proxy_host(explicit: str | None, cfg: ProvidersFile | None = None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    env = os.environ.get("PROXY_HOST", "").strip()
    if env:
        return env
    c = cfg or load_providers()
    return c.proxy_host_default
