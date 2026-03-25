from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from . import playwright_tools
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
    ToolResult,
    TypeInput,
    WaitForLoadStateInput,
    WaitForSelectorInput,
    WaitForTimeoutInput,
)

ToolHandler = Callable[[Any, Any, "SessionMemory"], Awaitable[ToolResult]]


@dataclass
class SessionMemory:
    values: dict[str, Any] = field(default_factory=dict)
    completed_subtasks: dict[str, str] = field(default_factory=dict)
    last_tool_results: list[ToolResult] = field(default_factory=list)
    last_error: str | None = None
    final_result: dict[str, Any] | None = None
    failure_streak: int = 0


class ToolRuntime:
    def __init__(self, page: Any, memory: SessionMemory | None = None) -> None:
        self._page = page
        self.memory = memory or SessionMemory()
        self._registry: dict[str, tuple[type[Any], ToolHandler]] = {
            "navigate": (NavigateInput, playwright_tools.handle_navigate),
            "reload_page": (ReloadInput, playwright_tools.handle_reload_page),
            "go_back": (GoBackInput, playwright_tools.handle_go_back),
            "click": (ClickInput, playwright_tools.handle_click),
            "fill": (FillInput, playwright_tools.handle_fill),
            "type_text": (TypeInput, playwright_tools.handle_type_text),
            "press": (PressInput, playwright_tools.handle_press),
            "hover": (HoverInput, playwright_tools.handle_hover),
            "check": (CheckInput, playwright_tools.handle_check),
            "scroll": (ScrollInput, playwright_tools.handle_scroll),
            "wait_for": (WaitForSelectorInput, playwright_tools.handle_wait_for),
            "wait_for_load_state": (
                WaitForLoadStateInput,
                playwright_tools.handle_wait_for_load_state,
            ),
            "wait_for_timeout": (
                WaitForTimeoutInput,
                playwright_tools.handle_wait_for_timeout,
            ),
            "read_text": (ReadTextInput, playwright_tools.handle_read_text),
            "get_page_info": (GetPageInfoInput, playwright_tools.handle_get_page_info),
            "is_visible": (IsVisibleInput, playwright_tools.handle_is_visible),
            "assert_visible": (
                AssertVisibleInput,
                playwright_tools.handle_assert_visible,
            ),
            "assert_text": (AssertTextInput, playwright_tools.handle_assert_text),
            "remember": (RememberInput, playwright_tools.handle_remember),
            "mark_subtask_done": (
                MarkSubtaskDoneInput,
                playwright_tools.handle_mark_subtask_done,
            ),
            "report_result": (ReportResultInput, playwright_tools.handle_report_result),
        }

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        registration = self._registry.get(tool_name)
        if registration is None:
            return self._record_result(
                ToolResult(
                    ok=False,
                    error=f"Unknown tool: {tool_name}",
                    retryable=False,
                )
            )

        input_model_cls, handler = registration

        try:
            input_model = input_model_cls.model_validate(arguments)
        except ValueError as error:
            return self._record_result(
                ToolResult(
                    ok=False,
                    error=f"Validation error for {tool_name}: {error}",
                    retryable=False,
                )
            )

        try:
            result = await handler(self._page, input_model, self.memory)
        except Exception as error:
            result = ToolResult(
                ok=False,
                error=f"Unhandled error while executing {tool_name}: {error}",
                retryable=True,
            )

        return self._record_result(result)

    def _record_result(self, result: ToolResult) -> ToolResult:
        self.memory.last_tool_results.append(result)
        if result.ok:
            self.memory.last_error = None
            self.memory.failure_streak = 0
        else:
            self.memory.last_error = result.error
            self.memory.failure_streak += 1
        return result
