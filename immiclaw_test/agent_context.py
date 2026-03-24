from __future__ import annotations

import json
from typing import Any

from .models import Scenario
from .tool_models import ToolResult
from .tool_runtime import SessionMemory

SYSTEM_PROMPT_TEMPLATE = """You are an expert web testing agent that uses tools to validate UI behavior.

Goal:
{goal}

Assertions to verify:
{assertions}

Test data:
{test_data}

Rules:
- Use available tools to navigate, interact, and verify page state.
- Prefer deterministic selectors and direct evidence from tool outputs.
- When assertions are fully verified, call report_result with passed=true.
- If assertions cannot be satisfied, call report_result with passed=false and explain why.
"""


def build_system_prompt(scenario: Scenario) -> str:
    assertions_text = "\n".join(f"- {assertion}" for assertion in scenario.assertions)
    test_data_text = (
        json.dumps(scenario.test_data, ensure_ascii=False, indent=2)
        if scenario.test_data
        else "{}"
    )
    return SYSTEM_PROMPT_TEMPLATE.format(
        goal=scenario.goal,
        assertions=assertions_text,
        test_data=test_data_text,
    )


def build_turn_messages(
    system_prompt: str,
    observation: str,
    memory: SessionMemory,
    transcript: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Current page state:\n{observation}"},
    ]

    if memory.values:
        messages.append(
            {
                "role": "user",
                "content": f"Remembered values: {json.dumps(memory.values)}",
            }
        )

    messages.extend(transcript[-10:])
    return messages


def build_tool_result_message(tool_call_id: str, result: ToolResult) -> dict[str, str]:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(result.model_dump()),
    }
