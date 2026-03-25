from __future__ import annotations

import json
from typing import Any

from .models import Task
from .tool_models import ToolResult
from .tool_runtime import SessionMemory

SYSTEM_PROMPT_TEMPLATE = """You are an expert web task agent that uses tools to complete browser tasks safely and deterministically.

Goal:
{goal}

Task completion criteria:
{done_when}

Subtasks:
{subtasks}

Test data:
{test_data}

Skills:
{skills}

Preset:
{preset}

Rules:
- Use available tools to navigate, interact, and verify page state.
- Prefer deterministic selectors and direct evidence from tool outputs.
- Work through pending subtasks one by one and call mark_subtask_done when a subtask is complete.
- Only call report_result with passed=true when the overall task completion criteria are satisfied.
- If the task cannot be completed, call report_result with passed=false and explain why.
"""


def build_system_prompt(task: Task, skills_prompt: str = "") -> str:
    done_when_text = "\n".join(f"- {item}" for item in task.done_when) or "- (none provided)"
    subtask_lines = []
    for subtask in task.subtasks:
        checks = ", ".join(subtask.done_when) if subtask.done_when else "No explicit checks"
        optional = " [optional]" if subtask.optional else ""
        subtask_lines.append(f"- {subtask.name}{optional}: {subtask.goal} | done when: {checks}")
    subtasks_text = "\n".join(subtask_lines) or "- (no subtasks)"
    test_data_text = (
        json.dumps(task.test_data, ensure_ascii=False, indent=2) if task.test_data else "{}"
    )
    skills_text = skills_prompt.strip() if skills_prompt.strip() else "(none)"
    return SYSTEM_PROMPT_TEMPLATE.format(
        goal=task.goal,
        done_when=done_when_text,
        subtasks=subtasks_text,
        test_data=test_data_text,
        skills=skills_text,
        preset=task.preset.strip() if task.preset.strip() else "(none)",
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

    if memory.completed_subtasks:
        messages.append(
            {
                "role": "user",
                "content": (
                    "Completed subtasks: "
                    f"{json.dumps(memory.completed_subtasks, ensure_ascii=False)}"
                ),
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
