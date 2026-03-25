from __future__ import annotations

from pathlib import Path
import re
import time
from typing import Any

from .agent_context import (
    build_system_prompt,
    build_tool_result_message,
    build_turn_messages,
)
from .llm_backends import LLMBackend, ToolCall
from .models import Settings, Skill, StepRecord, Task, TaskReport, TestResult
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
    MarkSubtaskDoneInput,
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
    get_tool_schemas,
    register_tool,
)
from .tool_runtime import SessionMemory, ToolRuntime


def task_dir_slug(name: str) -> str:
    """Filesystem-safe single path segment for a task name."""
    text = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip())
    text = re.sub(r"-{2,}", "-", text).strip("-_")
    return text or "unknown"


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
    register_tool("mark_subtask_done", MarkSubtaskDoneInput)
    register_tool("report_result", ReportResultInput)


def _assistant_tool_message(content: str | None, tool_calls: list[ToolCall]) -> dict[str, Any]:
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
    task: Task,
    result: TestResult,
    reason: str,
    step_count: int,
    steps: list[StepRecord],
    completed_subtasks: list[str],
    start_time: float,
    screenshots: list[str] | None = None,
) -> TaskReport:
    return TaskReport(
        task_name=task.name,
        result=result,
        reason=reason,
        total_steps=step_count,
        elapsed_seconds=round(time.time() - start_time, 2),
        steps=steps,
        completed_subtasks=completed_subtasks,
        screenshots=screenshots or [],
    )


def _resolve_allowed_tools(skills: list[Skill]) -> list[str] | None:
    declared = [tool for skill in skills for tool in skill.allowed_tools]
    if not declared:
        return None

    allowed = set(declared)
    allowed.update(
        {
            "get_page_info",
            "read_text",
            "is_visible",
            "assert_visible",
            "assert_text",
            "remember",
            "mark_subtask_done",
            "report_result",
            "wait_for",
            "wait_for_load_state",
            "wait_for_timeout",
            "reload_page",
        }
    )
    return sorted(allowed)


def _task_timed_out(start_time: float, timeout_seconds: int) -> bool:
    return (time.time() - start_time) >= timeout_seconds


async def _capture_failure_screenshot(
    page: Any,
    *,
    output_dir: Path | None,
    task: Task,
    step_count: int,
) -> list[str]:
    if output_dir is None:
        return []

    screenshots_dir = output_dir / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    file_path = screenshots_dir / f"{task_dir_slug(task.name)}-step-{step_count or 0}.png"
    await page.screenshot(path=str(file_path), full_page=True)
    return [str(file_path)]


async def _finalize_report(
    *,
    task: Task,
    page: Any,
    settings: Settings,
    result: TestResult,
    reason: str,
    step_count: int,
    steps: list[StepRecord],
    completed_subtasks: list[str],
    start_time: float,
    output_dir: Path | None,
    final_result: dict[str, Any] | None = None,
) -> TaskReport:
    screenshots: list[str] = []
    should_capture = settings.agent.screenshot_on_failure and result in {
        TestResult.FAIL,
        TestResult.TIMEOUT,
        TestResult.ERROR,
    }
    if final_result is not None and final_result.get("passed") is False:
        should_capture = should_capture and bool(final_result.get("screenshot_on_fail", True))

    if should_capture:
        try:
            screenshots = await _capture_failure_screenshot(
                page,
                output_dir=output_dir,
                task=task,
                step_count=step_count,
            )
        except Exception:
            screenshots = []

    return _build_report(
        task=task,
        result=result,
        reason=reason,
        step_count=step_count,
        steps=steps,
        completed_subtasks=completed_subtasks,
        start_time=start_time,
        screenshots=screenshots,
    )


async def run_task(
    task: Task,
    page: Any,
    backend: LLMBackend,
    settings: Settings,
    *,
    skills: list[Skill] | None = None,
    skills_prompt: str = "",
    output_dir: Path | None = None,
) -> TaskReport:
    _ensure_default_tools_registered()

    memory = SessionMemory()
    runtime = ToolRuntime(page, memory)
    active_skills = skills or []
    tools = get_tool_schemas(_resolve_allowed_tools(active_skills))

    system_prompt = build_system_prompt(task, skills_prompt=skills_prompt)
    transcript: list[dict[str, Any]] = []
    steps: list[StepRecord] = []
    start_time = time.time()
    target_url = task.start_url.format(base_url=settings.base_url)

    if _task_timed_out(start_time, task.timeout_seconds):
        return await _finalize_report(
            task=task,
            page=page,
            settings=settings,
            result=TestResult.TIMEOUT,
            reason=f"Task exceeded timeout of {task.timeout_seconds}s",
            step_count=0,
            steps=steps,
            completed_subtasks=_completed_subtasks(task, memory),
            start_time=start_time,
            output_dir=output_dir,
        )

    remaining_ms = max(int((task.timeout_seconds - (time.time() - start_time)) * 1000), 1)
    await page.goto(target_url, wait_until="domcontentloaded", timeout=min(15000, remaining_ms))

    for step_num in range(1, task.max_steps + 1):
        if _task_timed_out(start_time, task.timeout_seconds):
            return await _finalize_report(
                task=task,
                page=page,
                settings=settings,
                result=TestResult.TIMEOUT,
                reason=f"Task exceeded timeout of {task.timeout_seconds}s",
                step_count=step_num - 1,
                steps=steps,
                completed_subtasks=_completed_subtasks(task, memory),
                start_time=start_time,
                output_dir=output_dir,
            )

        page_state = await get_page_state(page)
        observation = format_state_for_llm(page_state)

        messages = build_turn_messages(system_prompt, observation, memory, transcript)
        turn = await backend.next_turn(messages, tools)

        if turn.is_terminal:
            return await _finalize_report(
                task=task,
                page=page,
                settings=settings,
                result=TestResult.FAIL,
                reason="Agent stopped without reporting result",
                step_count=step_num,
                steps=steps,
                completed_subtasks=_completed_subtasks(task, memory),
                start_time=start_time,
                output_dir=output_dir,
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
                return await _finalize_report(
                    task=task,
                    page=page,
                    settings=settings,
                    result=TestResult.PASS if passed else TestResult.FAIL,
                    reason=reason,
                    step_count=step_num,
                    steps=steps,
                    completed_subtasks=_completed_subtasks(task, memory),
                    start_time=start_time,
                    output_dir=output_dir,
                    final_result=final,
                )

            if _task_timed_out(start_time, task.timeout_seconds):
                return await _finalize_report(
                    task=task,
                    page=page,
                    settings=settings,
                    result=TestResult.TIMEOUT,
                    reason=f"Task exceeded timeout of {task.timeout_seconds}s",
                    step_count=step_num,
                    steps=steps,
                    completed_subtasks=_completed_subtasks(task, memory),
                    start_time=start_time,
                    output_dir=output_dir,
                )

        if memory.failure_streak >= 3:
            return await _finalize_report(
                task=task,
                page=page,
                settings=settings,
                result=TestResult.FAIL,
                reason="Too many consecutive failures",
                step_count=step_num,
                steps=steps,
                completed_subtasks=_completed_subtasks(task, memory),
                start_time=start_time,
                output_dir=output_dir,
            )

    return await _finalize_report(
        task=task,
        page=page,
        settings=settings,
        result=TestResult.TIMEOUT,
        reason="Reached max steps",
        step_count=task.max_steps,
        steps=steps,
        completed_subtasks=_completed_subtasks(task, memory),
        start_time=start_time,
        output_dir=output_dir,
    )


def _completed_subtasks(task: Task, memory: SessionMemory) -> list[str]:
    ordered = [subtask.name for subtask in task.subtasks if subtask.name in memory.completed_subtasks]
    extras = [name for name in memory.completed_subtasks if name not in ordered]
    return ordered + extras
