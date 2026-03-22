from __future__ import annotations

import json

from immiclaw_test.agent_context import (
    build_system_prompt,
    build_tool_result_message,
    build_turn_messages,
)
from immiclaw_test.models import Scenario
from immiclaw_test.tool_models import ToolResult
from immiclaw_test.tool_runtime import SessionMemory


def _make_scenario() -> Scenario:
    return Scenario(
        name="login-check",
        description="Verify successful login flow",
        target_url="{base_url}/login",
        goal="Log in as a valid user and confirm dashboard renders",
        assertions=[
            "Email field is visible",
            "Password field is visible",
            "Dashboard heading appears after submit",
        ],
        test_data={"email": "user@example.com", "password": "pw123"},
    )


def test_build_system_prompt_includes_goal_assertions_and_test_data() -> None:
    scenario = _make_scenario()

    prompt = build_system_prompt(scenario)

    assert scenario.goal in prompt
    assert "- Email field is visible" in prompt
    assert "- Dashboard heading appears after submit" in prompt
    assert '"email": "user@example.com"' in prompt
    assert '"password": "pw123"' in prompt


def test_build_turn_messages_includes_memory_and_last_10_transcript_messages() -> None:
    memory = SessionMemory(values={"header": "Dashboard", "attempt": 2})
    transcript = [
        {"role": "assistant", "content": f"assistant-{i}"}
        if i % 2 == 0
        else {"role": "tool", "tool_call_id": str(i), "content": f"tool-{i}"}
        for i in range(12)
    ]

    messages = build_turn_messages(
        system_prompt="SYSTEM",
        observation="URL: /dashboard",
        memory=memory,
        transcript=transcript,
    )

    assert messages[0] == {"role": "system", "content": "SYSTEM"}
    assert messages[1] == {
        "role": "user",
        "content": "Current page state:\nURL: /dashboard",
    }
    assert messages[2]["role"] == "user"
    assert messages[2]["content"].startswith("Remembered values: ")
    assert json.loads(messages[2]["content"].removeprefix("Remembered values: ")) == {
        "header": "Dashboard",
        "attempt": 2,
    }

    assert messages[3:] == transcript[-10:]


def test_build_turn_messages_skips_memory_when_no_values() -> None:
    messages = build_turn_messages(
        system_prompt="SYSTEM",
        observation="URL: /page",
        memory=SessionMemory(values={}),
        transcript=[],
    )

    assert messages == [
        {"role": "system", "content": "SYSTEM"},
        {"role": "user", "content": "Current page state:\nURL: /page"},
    ]


def test_build_tool_result_message_returns_tool_role_payload() -> None:
    result = ToolResult(ok=False, error="Missing element", retryable=True, hint="wait")

    message = build_tool_result_message("call-123", result)

    assert message["role"] == "tool"
    assert message["tool_call_id"] == "call-123"
    assert json.loads(message["content"]) == result.model_dump()
