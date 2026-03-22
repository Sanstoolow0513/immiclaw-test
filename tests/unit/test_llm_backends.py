from __future__ import annotations

import json
from types import SimpleNamespace

from immiclaw_test.models import LLMConfig


def test_tool_call_parse_arguments_returns_dict() -> None:
    from immiclaw_test.llm_backends import ToolCall

    call = ToolCall(id="call_1", name="report_result", arguments='{"passed": true}')

    assert call.parse_arguments() == {"passed": True}


def test_assistant_turn_is_terminal_when_stop_and_no_tools() -> None:
    from immiclaw_test.llm_backends import AssistantTurn

    turn = AssistantTurn(content="done", tool_calls=None, finish_reason="stop")

    assert turn.is_terminal is True
    assert turn.has_tool_calls is False


def test_assistant_turn_is_not_terminal_when_tool_calls_present() -> None:
    from immiclaw_test.llm_backends import AssistantTurn, ToolCall

    turn = AssistantTurn(
        content=None,
        tool_calls=[ToolCall(id="call_2", name="click", arguments="{}")],
        finish_reason="tool_calls",
    )

    assert turn.is_terminal is False
    assert turn.has_tool_calls is True


async def test_fake_backend_returns_queued_responses() -> None:
    from immiclaw_test.llm_backends import AssistantTurn, FakeBackend

    backend = FakeBackend()
    first = AssistantTurn(content="first", tool_calls=None, finish_reason="stop")
    second = AssistantTurn(content="second", tool_calls=None, finish_reason="stop")

    backend.add_response(first)
    backend.add_response(second)

    first_result = await backend.next_turn(messages=[], tools=[])
    second_result = await backend.next_turn(messages=[], tools=[])

    assert first_result is first
    assert second_result is second


async def test_fake_backend_raises_when_no_responses_queued() -> None:
    from immiclaw_test.llm_backends import FakeBackend

    backend = FakeBackend()

    try:
        await backend.next_turn(messages=[], tools=[])
    except RuntimeError as error:
        assert "No fake responses configured" in str(error)
    else:
        raise AssertionError("Expected RuntimeError for empty fake backend queue")


async def test_openai_chat_backend_maps_tool_calls_and_finish_reason() -> None:
    from immiclaw_test.llm_backends import OpenAIChatBackend

    config = LLMConfig(model="gpt-4o", api_key="test-key", temperature=0.3)
    backend = OpenAIChatBackend(config)

    fake_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="tool_calls",
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            id="call_123",
                            function=SimpleNamespace(
                                name="report_result",
                                arguments=json.dumps({"passed": True, "reason": "ok"}),
                            ),
                        )
                    ],
                ),
            )
        ]
    )

    class _Completions:
        async def create(self, **kwargs):
            assert kwargs["model"] == "gpt-4o"
            assert kwargs["tools"] == [
                {"type": "function", "function": {"name": "report_result"}}
            ]
            assert kwargs["tool_choice"] == "auto"
            assert kwargs["temperature"] == 0.3
            return fake_response

    backend._client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))

    turn = await backend.next_turn(
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "report_result"}}],
    )

    assert turn.content is None
    assert turn.finish_reason == "tool_calls"
    assert turn.raw is fake_response
    assert turn.tool_calls is not None
    assert len(turn.tool_calls) == 1
    assert turn.tool_calls[0].id == "call_123"
    assert turn.tool_calls[0].name == "report_result"
    assert turn.tool_calls[0].parse_arguments() == {"passed": True, "reason": "ok"}


async def test_openai_chat_backend_sends_none_tools_when_empty() -> None:
    from immiclaw_test.llm_backends import OpenAIChatBackend

    config = LLMConfig(model="gpt-4o", api_key="test-key")
    backend = OpenAIChatBackend(config)

    fake_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                message=SimpleNamespace(content="hello", tool_calls=None),
            )
        ]
    )

    class _Completions:
        async def create(self, **kwargs):
            assert kwargs["tools"] is None
            assert kwargs["tool_choice"] == "required"
            return fake_response

    backend._client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))

    turn = await backend.next_turn(
        messages=[{"role": "user", "content": "hi"}],
        tools=[],
        tool_choice="required",
    )

    assert turn.content == "hello"
    assert turn.tool_calls is None
    assert turn.finish_reason == "stop"
