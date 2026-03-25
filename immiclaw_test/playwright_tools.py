from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .locator_resolver import resolve_locator
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

if TYPE_CHECKING:
    from .tool_runtime import SessionMemory


def _error_result(error: Exception, retryable: bool = True) -> ToolResult:
    return ToolResult(ok=False, error=str(error), retryable=retryable)


async def handle_navigate(
    page: Any,
    input: NavigateInput,
    memory: SessionMemory,
) -> ToolResult:
    del memory
    try:
        await page.goto(input.url, wait_until=input.wait_until)
        return ToolResult(ok=True, data={})
    except Exception as error:
        return _error_result(error)


async def handle_reload_page(
    page: Any,
    input: ReloadInput,
    memory: SessionMemory,
) -> ToolResult:
    del memory
    try:
        await page.reload(wait_until=input.wait_until)
        return ToolResult(ok=True, data={})
    except Exception as error:
        return _error_result(error)


async def handle_go_back(
    page: Any,
    input: GoBackInput,
    memory: SessionMemory,
) -> ToolResult:
    del memory
    try:
        await page.go_back(wait_until=input.wait_until)
        return ToolResult(ok=True, data={})
    except Exception as error:
        return _error_result(error)


async def handle_click(page: Any, input: ClickInput, memory: SessionMemory) -> ToolResult:
    del memory
    try:
        locator = resolve_locator(page, input.locator)
        await locator.click(
            button=input.button,
            click_count=input.click_count,
            delay=input.delay_ms,
        )
        return ToolResult(ok=True, data={})
    except Exception as error:
        return _error_result(error)


async def handle_fill(page: Any, input: FillInput, memory: SessionMemory) -> ToolResult:
    del memory
    try:
        locator = resolve_locator(page, input.locator)
        if input.clear_first:
            await locator.fill(input.text)
        else:
            await locator.type(input.text)
        return ToolResult(ok=True, data={})
    except Exception as error:
        return _error_result(error)


async def handle_type_text(
    page: Any,
    input: TypeInput,
    memory: SessionMemory,
) -> ToolResult:
    del memory
    try:
        locator = resolve_locator(page, input.locator)
        await locator.type(input.text, delay=input.delay_ms)
        return ToolResult(ok=True, data={})
    except Exception as error:
        return _error_result(error)


async def handle_press(page: Any, input: PressInput, memory: SessionMemory) -> ToolResult:
    del memory
    try:
        locator = resolve_locator(page, input.locator)
        await locator.press(input.key)
        return ToolResult(ok=True, data={})
    except Exception as error:
        return _error_result(error)


async def handle_hover(page: Any, input: HoverInput, memory: SessionMemory) -> ToolResult:
    del memory
    try:
        locator = resolve_locator(page, input.locator)
        await locator.hover()
        return ToolResult(ok=True, data={})
    except Exception as error:
        return _error_result(error)


async def handle_check(page: Any, input: CheckInput, memory: SessionMemory) -> ToolResult:
    del memory
    try:
        locator = resolve_locator(page, input.locator)
        if input.checked:
            await locator.check()
        else:
            await locator.uncheck()
        return ToolResult(ok=True, data={})
    except Exception as error:
        return _error_result(error)


async def handle_scroll(page: Any, input: ScrollInput, memory: SessionMemory) -> ToolResult:
    del memory
    try:
        await page.mouse.wheel(input.delta_x, input.delta_y)
        return ToolResult(ok=True, data={})
    except Exception as error:
        return _error_result(error)


async def handle_wait_for(
    page: Any,
    input: WaitForSelectorInput,
    memory: SessionMemory,
) -> ToolResult:
    del memory
    try:
        locator = resolve_locator(page, input.locator)
        await locator.wait_for(state=input.state, timeout=input.timeout_ms)
        return ToolResult(ok=True, data={})
    except Exception as error:
        return _error_result(error)


async def handle_wait_for_load_state(
    page: Any,
    input: WaitForLoadStateInput,
    memory: SessionMemory,
) -> ToolResult:
    del memory
    try:
        await page.wait_for_load_state(state=input.state, timeout=input.timeout_ms)
        return ToolResult(ok=True, data={})
    except Exception as error:
        return _error_result(error)


async def handle_wait_for_timeout(
    page: Any,
    input: WaitForTimeoutInput,
    memory: SessionMemory,
) -> ToolResult:
    del memory
    try:
        await page.wait_for_timeout(input.timeout_ms)
        return ToolResult(ok=True, data={})
    except Exception as error:
        return _error_result(error)


async def handle_read_text(
    page: Any,
    input: ReadTextInput,
    memory: SessionMemory,
) -> ToolResult:
    try:
        locator = resolve_locator(page, input.locator)
        text = await locator.inner_text()
        if input.save_as:
            memory.values[input.save_as] = text
        return ToolResult(ok=True, data={"text": text})
    except Exception as error:
        return _error_result(error)


async def handle_get_page_info(
    page: Any,
    input: GetPageInfoInput,
    memory: SessionMemory,
) -> ToolResult:
    del input, memory
    try:
        title = await page.title()
        return ToolResult(ok=True, data={"url": page.url, "title": title})
    except Exception as error:
        return _error_result(error)


async def handle_is_visible(
    page: Any,
    input: IsVisibleInput,
    memory: SessionMemory,
) -> ToolResult:
    del memory
    try:
        locator = resolve_locator(page, input.locator)
        is_visible = await locator.is_visible()
        return ToolResult(ok=True, data={"is_visible": is_visible})
    except Exception as error:
        return _error_result(error)


async def handle_assert_visible(
    page: Any,
    input: AssertVisibleInput,
    memory: SessionMemory,
) -> ToolResult:
    del memory
    try:
        locator = resolve_locator(page, input.locator)
        await locator.wait_for(state="visible", timeout=input.timeout_ms)
        return ToolResult(ok=True, data={})
    except Exception as error:
        return _error_result(error, retryable=False)


async def handle_assert_text(
    page: Any,
    input: AssertTextInput,
    memory: SessionMemory,
) -> ToolResult:
    del memory
    try:
        locator = resolve_locator(page, input.locator)
        await locator.wait_for(state="visible", timeout=input.timeout_ms)
        actual = await locator.inner_text()
        if input.exact and actual != input.expected:
            return ToolResult(
                ok=False,
                error=(f"Expected exact text '{input.expected}' but found '{actual}'"),
                retryable=False,
            )
        if not input.exact and input.expected not in actual:
            return ToolResult(
                ok=False,
                error=(f"Expected text containing '{input.expected}' but found '{actual}'"),
                retryable=False,
            )
        return ToolResult(ok=True, data={"actual": actual})
    except Exception as error:
        return _error_result(error, retryable=False)


async def handle_remember(
    page: Any,
    input: RememberInput,
    memory: SessionMemory,
) -> ToolResult:
    del page
    memory.values[input.name] = input.value
    return ToolResult(ok=True, data={"name": input.name})


async def handle_mark_subtask_done(
    page: Any,
    input: MarkSubtaskDoneInput,
    memory: SessionMemory,
) -> ToolResult:
    del page
    memory.completed_subtasks[input.name] = input.reason
    return ToolResult(ok=True, data={"name": input.name, "reason": input.reason})


async def handle_report_result(
    page: Any,
    input: ReportResultInput,
    memory: SessionMemory,
) -> ToolResult:
    del page
    memory.final_result = {
        "passed": input.passed,
        "reason": input.reason,
        "evidence_points": input.evidence_points,
    }
    return ToolResult(ok=True, data={"is_final": True})
