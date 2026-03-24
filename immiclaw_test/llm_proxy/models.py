"""Pydantic models for provider configuration."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProviderEntry(BaseModel):
    port: int
    name: str
    target_host: str
    api_family: Literal["openai", "anthropic", "gemini"]
    env_key: str
    list_path: str
    auth_style: Literal["bearer", "query_key", "x_goog_api_key"] = "bearer"
    chat_path: str | None = Field(default="/v1/chat/completions")
    messages_path: str | None = Field(default="/v1/messages")
    probe_model: str | None = None


class ProvidersFile(BaseModel):
    proxy_host_default: str = "103.127.243.93"
    anthropic_version: str = "2023-06-01"
    providers: list[ProviderEntry]
