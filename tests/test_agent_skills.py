from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from immiclaw_test.llm_backends import AssistantTurn, ToolCall
from immiclaw_test.models import Skill, Task, TaskSubtask, TestResult as RunResult


def _make_page() -> MagicMock:
    page = MagicMock()
    page.goto = AsyncMock(return_value=None)
    page.url = "http://test.example.com/login"
    page.title = AsyncMock(return_value="Login")
    page.accessibility = MagicMock()
    page.accessibility.snapshot = AsyncMock(
        return_value={"role": "document", "name": "Login", "children": []}
    )
    return page


class RecordingBackend:
    def __init__(self, response: AssistantTurn) -> None:
        self.response = response
        self.seen_tools = None
        self.seen_messages = None

    async def next_turn(self, messages, tools, **kwargs):
        self.seen_messages = messages
        self.seen_tools = tools
        return self.response


@pytest.mark.asyncio
async def test_run_task_limits_tools_from_skill(sample_settings) -> None:
    from immiclaw_test.agent import run_task

    task = Task(
        name="login",
        description="login",
        start_url="http://test.example.com/login",
        goal="login",
        done_when=["ok"],
        subtasks=[TaskSubtask(name="login", goal="login", done_when=["ok"])],
        skills=["login"],
    )
    backend = RecordingBackend(
        AssistantTurn(
            content="done",
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="report_result",
                    arguments=json.dumps({"passed": True, "reason": "ok"}),
                )
            ],
            finish_reason="tool_calls",
        )
    )
    skills = [
        Skill(
            name="login",
            type="operation",
            description="Login",
            prompt="Use login flow",
            allowed_tools=["click", "fill"],
        )
    ]

    report = await run_task(
        task=task,
        page=_make_page(),
        backend=backend,
        settings=sample_settings,
        skills=skills,
        skills_prompt="### 操作级\nUse login flow",
    )

    assert report.result == RunResult.PASS
    tool_names = [tool["function"]["name"] for tool in backend.seen_tools]
    assert "click" in tool_names
    assert "fill" in tool_names
    assert "report_result" in tool_names
    assert "navigate" not in tool_names
    assert any(
        "### 操作级" in message["content"]
        for message in backend.seen_messages
        if message["role"] == "system"
    )
