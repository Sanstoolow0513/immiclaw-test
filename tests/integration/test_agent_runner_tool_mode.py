from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from immiclaw_test.llm_backends import AssistantTurn, FakeBackend, ToolCall
from immiclaw_test.models import Task, TaskSubtask, TestResult as RunResult


def _make_task(*, max_steps: int = 5) -> Task:
    return Task(
        name="Tool mode task",
        description="Verify tool-calling runner",
        start_url="http://test.example.com",
        goal="Execute tools and report final result",
        done_when=["An assertion"],
        subtasks=[TaskSubtask(name="complete", goal="Complete the task", done_when=["An assertion"])],
        max_steps=max_steps,
        timeout_seconds=120,
        test_data={},
    )


def _make_page() -> MagicMock:
    page = MagicMock()
    locator = MagicMock()
    locator.click = AsyncMock(return_value=None)

    page.goto = AsyncMock(return_value=None)
    page.screenshot = AsyncMock(return_value=b"fake-screenshot")
    page.locator = MagicMock(return_value=locator)
    page.url = "http://test.example.com"
    page.title = AsyncMock(return_value="Test Page")
    page.accessibility = MagicMock()
    page.accessibility.snapshot = AsyncMock(
        return_value={"role": "document", "name": "Test Page", "children": []}
    )
    return page


class RecordingFakeBackend(FakeBackend):
    def __init__(self) -> None:
        super().__init__()
        self.seen_messages: list[list[dict[str, Any]]] = []

    async def next_turn(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AssistantTurn:
        del tools, kwargs
        self.seen_messages.append(deepcopy(messages))
        return await super().next_turn(messages, tools=[])


async def test_run_task_with_tools_click_then_report_pass(sample_settings) -> None:
    from immiclaw_test.agent import run_task

    task = _make_task()
    page = _make_page()
    backend = FakeBackend()
    backend.add_response(
        AssistantTurn(
            content="Click submit",
            tool_calls=[
                ToolCall(
                    id="call_1",
                    name="click",
                    arguments=json.dumps(
                        {
                            "locator": {"kind": "css", "value": "#submit"},
                        }
                    ),
                )
            ],
            finish_reason="tool_calls",
        )
    )
    backend.add_response(
        AssistantTurn(
            content="Done",
            tool_calls=[
                ToolCall(
                    id="call_2",
                    name="report_result",
                    arguments=json.dumps(
                        {
                            "passed": True,
                            "reason": "Submit button click succeeded",
                            "evidence_points": ["Click tool returned ok"],
                        }
                    ),
                )
            ],
            finish_reason="tool_calls",
        )
    )

    report = await run_task(
        task=task,
        page=page,
        backend=backend,
        settings=sample_settings,
    )

    assert report.result == RunResult.PASS
    assert report.reason == "Submit button click succeeded"
    assert report.total_steps == 2
    assert len(report.steps) == 2
    assert report.steps[0].code == "Tool: click"
    page.goto.assert_awaited_once_with(
        "http://test.example.com",
        wait_until="domcontentloaded",
        timeout=15000,
    )
    page.locator.return_value.click.assert_awaited_once()


async def test_run_task_with_tools_report_fail_with_evidence(
    sample_settings,
) -> None:
    from immiclaw_test.agent import run_task

    task = _make_task(max_steps=2)
    page = _make_page()
    backend = FakeBackend()
    backend.add_response(
        AssistantTurn(
            content="Assertion failed",
            tool_calls=[
                ToolCall(
                    id="call_fail",
                    name="report_result",
                    arguments=json.dumps(
                        {
                            "passed": False,
                            "reason": "Expected dashboard header not visible",
                            "evidence_points": ["assert_visible failed for #dashboard-header"],
                        }
                    ),
                )
            ],
            finish_reason="tool_calls",
        )
    )

    report = await run_task(
        task=task,
        page=page,
        backend=backend,
        settings=sample_settings,
    )

    assert report.result == RunResult.FAIL
    assert report.reason == "Expected dashboard header not visible"
    assert report.total_steps == 1
    assert len(report.steps) == 1
    assert report.steps[0].code == "Tool: report_result"


async def test_run_task_captures_failure_screenshot(sample_settings, tmp_path: Path) -> None:
    from immiclaw_test.agent import run_task

    task = _make_task(max_steps=2)
    page = _make_page()
    backend = FakeBackend()
    backend.add_response(
        AssistantTurn(
            content="Assertion failed",
            tool_calls=[
                ToolCall(
                    id="call_fail",
                    name="report_result",
                    arguments=json.dumps(
                        {
                            "passed": False,
                            "reason": "Expected dashboard header not visible",
                            "screenshot_on_fail": True,
                        }
                    ),
                )
            ],
            finish_reason="tool_calls",
        )
    )

    report = await run_task(
        task=task,
        page=page,
        backend=backend,
        settings=sample_settings,
        output_dir=tmp_path,
    )

    assert report.result == RunResult.FAIL
    assert len(report.screenshots) == 1
    assert report.screenshots[0].startswith(str(tmp_path / "screenshots"))
    page.screenshot.assert_awaited_once()


async def test_run_task_stops_on_wall_clock_timeout(monkeypatch, sample_settings) -> None:
    from immiclaw_test import agent
    from immiclaw_test.agent import run_task

    task = _make_task(max_steps=5)
    task.timeout_seconds = 1
    page = _make_page()
    backend = FakeBackend()

    calls = iter([100.0, 100.0, 100.0, 101.1, 101.1])
    monkeypatch.setattr(agent.time, "time", lambda: next(calls))

    report = await run_task(
        task=task,
        page=page,
        backend=backend,
        settings=sample_settings,
    )

    assert report.result == RunResult.TIMEOUT
    assert report.reason == "Task exceeded timeout of 1s"
    assert report.total_steps == 0


async def test_run_task_with_tools_memory_persists_across_steps(
    sample_settings,
) -> None:
    from immiclaw_test.agent import run_task

    task = _make_task()
    page = _make_page()
    backend = RecordingFakeBackend()
    backend.add_response(
        AssistantTurn(
            content="Remember a value",
            tool_calls=[
                ToolCall(
                    id="call_remember",
                    name="remember",
                    arguments=json.dumps({"name": "status", "value": "ready"}),
                )
            ],
            finish_reason="tool_calls",
        )
    )
    backend.add_response(
        AssistantTurn(
            content="Now finish",
            tool_calls=[
                ToolCall(
                    id="call_report",
                    name="report_result",
                    arguments=json.dumps({"passed": True, "reason": "Memory was available"}),
                )
            ],
            finish_reason="tool_calls",
        )
    )

    report = await run_task(
        task=task,
        page=page,
        backend=backend,
        settings=sample_settings,
    )

    assert report.result == RunResult.PASS
    assert len(backend.seen_messages) >= 2
    second_turn_messages = backend.seen_messages[1]
    assert any(
        message.get("role") == "user"
        and "Remembered values:" in message.get("content", "")
        and '"status": "ready"' in message.get("content", "")
        for message in second_turn_messages
    )


async def test_run_task_tracks_completed_subtasks(sample_settings) -> None:
    from immiclaw_test.agent import run_task

    task = _make_task()
    page = _make_page()
    backend = RecordingFakeBackend()
    backend.add_response(
        AssistantTurn(
            content="Subtask complete",
            tool_calls=[
                ToolCall(
                    id="call_subtask",
                    name="mark_subtask_done",
                    arguments=json.dumps({"name": "complete", "reason": "Reached target state"}),
                )
            ],
            finish_reason="tool_calls",
        )
    )
    backend.add_response(
        AssistantTurn(
            content="Now finish",
            tool_calls=[
                ToolCall(
                    id="call_report",
                    name="report_result",
                    arguments=json.dumps({"passed": True, "reason": "Task complete"}),
                )
            ],
            finish_reason="tool_calls",
        )
    )

    report = await run_task(
        task=task,
        page=page,
        backend=backend,
        settings=sample_settings,
    )

    assert report.result == RunResult.PASS
    assert report.completed_subtasks == ["complete"]
    second_turn_messages = backend.seen_messages[1]
    assert any(
        message.get("role") == "user"
        and "Completed subtasks:" in message.get("content", "")
        and '"complete": "Reached target state"' in message.get("content", "")
        for message in second_turn_messages
    )
