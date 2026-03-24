from __future__ import annotations

import time
from typing import Any

from .agent_context import (
    build_system_prompt,
    build_tool_result_message,
    build_turn_messages,
)
from .llm_backends import LLMBackend, ToolCall
from .models import Scenario, Settings, StepRecord, TestReport, TestResult
from .observer import format_state_for_llm, get_page_state
from .tool_models import (
    AssertTextInput,
    AssertVisibleInput,
    CheckInput,
    ClickInput,
    FillInput,
    GetPageInfoInput,
    GoBackInput,
    HoverInput,
    IsVisibleInput,
    NavigateInput,
    PressInput,
    ReadTextInput,
    ReloadInput,
    RememberInput,
    ReportResultInput,
    ScrollInput,
    TypeInput,
    WaitForLoadStateInput,
    WaitForSelectorInput,
    WaitForTimeoutInput,
    get_all_tool_schemas,
    register_tool,
)
from .tool_runtime import SessionMemory, ToolRuntime


def _ensure_default_tools_registered() -> None:
    register_tool("navigate", NavigateInput)
    register_tool("reload_page", ReloadInput)
    register_tool("go_back", GoBackInput)
    register_tool("click", ClickInput)
    register_tool("fill", FillInput)
    register_tool("type_text", TypeInput)
    register_tool("press", PressInput)
    register_tool("hover", HoverInput)
    register_tool("check", CheckInput)
    register_tool("scroll", ScrollInput)
    register_tool("wait_for", WaitForSelectorInput)
    register_tool("wait_for_load_state", WaitForLoadStateInput)
    register_tool("wait_for_timeout", WaitForTimeoutInput)
    register_tool("read_text", ReadTextInput)
    register_tool("get_page_info", GetPageInfoInput)
    register_tool("is_visible", IsVisibleInput)
    register_tool("assert_visible", AssertVisibleInput)
    register_tool("assert_text", AssertTextInput)
    register_tool("remember", RememberInput)
    register_tool("report_result", ReportResultInput)


def _assistant_tool_message(
    content: str | None, tool_calls: list[ToolCall]
) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": content or "",
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": tool_call.arguments,
                },
            }
            for tool_call in tool_calls
        ],
    }


def _build_report(
    scenario: Scenario,
    result: TestResult,
    reason: str,
    step_count: int,
    steps: list[StepRecord],
    start_time: float,
) -> TestReport:
    return TestReport(
        scenario_name=scenario.name,
        result=result,
        reason=reason,
        total_steps=step_count,
        elapsed_seconds=round(time.time() - start_time, 2),
        steps=steps,
        screenshots=[],
    )


async def run_scenario_with_tools(
    scenario: Scenario,
    page: Any,
    backend: LLMBackend,
    settings: Settings,
) -> TestReport:
    del settings

    _ensure_default_tools_registered()

    memory = SessionMemory()
    runtime = ToolRuntime(page, memory)
    tools = get_all_tool_schemas()

    system_prompt = build_system_prompt(scenario)
    transcript: list[dict[str, Any]] = []
    steps: list[StepRecord] = []
    start_time = time.time()

    for step_num in range(1, scenario.max_steps + 1):
        page_state = await get_page_state(page)
        observation = format_state_for_llm(page_state)

        messages = build_turn_messages(system_prompt, observation, memory, transcript)
        turn = await backend.next_turn(messages, tools)

        if turn.is_terminal:
            return _build_report(
                scenario=scenario,
                result=TestResult.FAIL,
                reason="Agent stopped without reporting result",
                step_count=step_num,
                steps=steps,
                start_time=start_time,
            )

        tool_calls = turn.tool_calls or []
        if tool_calls:
            transcript.append(_assistant_tool_message(turn.content, tool_calls))

        for tool_call in tool_calls:
            result = await runtime.execute(tool_call.name, tool_call.parse_arguments())

            steps.append(
                StepRecord(
                    step_number=step_num,
                    thinking=turn.content or "",
                    code=f"Tool: {tool_call.name}",
                    output=str(result.data) if result.ok else "",
                    error=result.error,
                    success=result.ok,
                    page_url=page.url,
                )
            )

            transcript.append(build_tool_result_message(tool_call.id, result))

            if result.data.get("is_final"):
                final = memory.final_result or {}
                passed = bool(final.get("passed", False))
                reason = str(final.get("reason", ""))
                return _build_report(
                    scenario=scenario,
                    result=TestResult.PASS if passed else TestResult.FAIL,
                    reason=reason,
                    step_count=step_num,
                    steps=steps,
                    start_time=start_time,
                )

        if memory.failure_streak >= 3:
            return _build_report(
                scenario=scenario,
                result=TestResult.FAIL,
                reason="Too many consecutive failures",
                step_count=step_num,
                steps=steps,
                start_time=start_time,
            )

    return _build_report(
        scenario=scenario,
        result=TestResult.TIMEOUT,
        reason="Reached max steps",
        step_count=scenario.max_steps,
        steps=steps,
        start_time=start_time,
    )
