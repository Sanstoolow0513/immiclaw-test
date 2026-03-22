from __future__ import annotations

import json
from importlib import import_module
from dataclasses import dataclass
from typing import Any, Protocol

from .models import LLMConfig


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str

    def parse_arguments(self) -> dict[str, Any]:
        return json.loads(self.arguments)


@dataclass
class AssistantTurn:
    content: str | None
    tool_calls: list[ToolCall] | None
    finish_reason: str
    raw: Any = None

    @property
    def is_terminal(self) -> bool:
        return self.finish_reason in ("stop", "length") and not self.tool_calls

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


class LLMBackend(Protocol):
    async def next_turn(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AssistantTurn: ...


class OpenAIChatBackend:
    def __init__(self, config: LLMConfig):
        openai_module = import_module("openai")
        async_openai = getattr(openai_module, "AsyncOpenAI")

        self._client = async_openai(
            api_key=config.api_key,
            base_url=config.base_url,
        )
        self._model = config.model
        self._temperature = config.temperature

    async def next_turn(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AssistantTurn:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=tools if tools else None,
            tool_choice=kwargs.get("tool_choice", "auto"),
            temperature=self._temperature,
        )

        message = response.choices[0].message
        tool_calls: list[ToolCall] | None = None

        if message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=tool_call.function.arguments,
                )
                for tool_call in message.tool_calls
            ]

        return AssistantTurn(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason,
            raw=response,
        )


class FakeBackend:
    def __init__(self) -> None:
        self._responses: list[AssistantTurn] = []

    def add_response(self, response: AssistantTurn) -> None:
        self._responses.append(response)

    async def next_turn(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AssistantTurn:
        if not self._responses:
            raise RuntimeError("No fake responses configured")
        return self._responses.pop(0)


def create_backend(config: LLMConfig) -> LLMBackend:
    return OpenAIChatBackend(config)
