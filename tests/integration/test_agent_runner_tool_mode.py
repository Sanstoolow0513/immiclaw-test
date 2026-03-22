from __future__ import annotations

import json
from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from immiclaw_test.llm_backends import AssistantTurn, FakeBackend, ToolCall
from immiclaw_test.models import Scenario, TestResult


def _make_scenario(*, max_steps: int = 5) -> Scenario:
    return Scenario(
        name="Tool mode scenario",
        description="Verify tool-calling runner",
        target_url="http://test.example.com",
        goal="Execute tools and report final result",
        assertions=["An assertion"],
        max_steps=max_steps,
        timeout_seconds=120,
        test_data={},
    )


def _make_page() -> MagicMock:
    page = MagicMock()
    locator = MagicMock()
    locator.click = AsyncMock(return_value=None)

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


async def test_run_scenario_with_tools_click_then_report_pass(sample_settings) -> None:
    from immiclaw_test.agent_runner import run_scenario_with_tools

    scenario = _make_scenario()
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

    report = await run_scenario_with_tools(
        scenario=scenario,
        page=page,
        backend=backend,
        settings=sample_settings,
    )

    assert report.result == TestResult.PASS
    assert report.reason == "Submit button click succeeded"
    assert report.total_steps == 2
    assert len(report.steps) == 2
    assert report.steps[0].code == "Tool: click"
    page.locator.return_value.click.assert_awaited_once()


async def test_run_scenario_with_tools_report_fail_with_evidence(
    sample_settings,
) -> None:
    from immiclaw_test.agent_runner import run_scenario_with_tools

    scenario = _make_scenario(max_steps=2)
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
                            "evidence_points": [
                                "assert_visible failed for #dashboard-header"
                            ],
                        }
                    ),
                )
            ],
            finish_reason="tool_calls",
        )
    )

    report = await run_scenario_with_tools(
        scenario=scenario,
        page=page,
        backend=backend,
        settings=sample_settings,
    )

    assert report.result == TestResult.FAIL
    assert report.reason == "Expected dashboard header not visible"
    assert report.total_steps == 1
    assert len(report.steps) == 1
    assert report.steps[0].code == "Tool: report_result"


async def test_run_scenario_with_tools_memory_persists_across_steps(
    sample_settings,
) -> None:
    from immiclaw_test.agent_runner import run_scenario_with_tools

    scenario = _make_scenario()
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
                    arguments=json.dumps(
                        {"passed": True, "reason": "Memory was available"}
                    ),
                )
            ],
            finish_reason="tool_calls",
        )
    )

    report = await run_scenario_with_tools(
        scenario=scenario,
        page=page,
        backend=backend,
        settings=sample_settings,
    )

    assert report.result == TestResult.PASS
    assert len(backend.seen_messages) >= 2
    second_turn_messages = backend.seen_messages[1]
    assert any(
        message.get("role") == "user"
        and "Remembered values:" in message.get("content", "")
        and '"status": "ready"' in message.get("content", "")
        for message in second_turn_messages
    )
