from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from immiclaw_test.tool_runtime import SessionMemory, ToolRuntime


def _make_page_with_locator() -> MagicMock:
    page = MagicMock()

    locator = MagicMock()
    locator.click = AsyncMock(return_value=None)
    locator.fill = AsyncMock(return_value=None)
    locator.type = AsyncMock(return_value=None)
    locator.press = AsyncMock(return_value=None)
    locator.hover = AsyncMock(return_value=None)
    locator.check = AsyncMock(return_value=None)
    locator.uncheck = AsyncMock(return_value=None)
    locator.wait_for = AsyncMock(return_value=None)
    locator.is_visible = AsyncMock(return_value=True)
    locator.inner_text = AsyncMock(return_value="Welcome")

    page.locator = MagicMock(return_value=locator)
    page.goto = AsyncMock(return_value=None)
    page.reload = AsyncMock(return_value=None)
    page.go_back = AsyncMock(return_value=None)
    page.wait_for_load_state = AsyncMock(return_value=None)
    page.wait_for_timeout = AsyncMock(return_value=None)
    page.title = AsyncMock(return_value="Dashboard")
    page.url = "https://example.test/dashboard"
    page.mouse = MagicMock()
    page.mouse.wheel = AsyncMock(return_value=None)

    return page


async def test_execute_validates_unknown_tool_and_tracks_failure() -> None:
    page = _make_page_with_locator()
    runtime = ToolRuntime(page=page)

    result = await runtime.execute("not_a_tool", {})

    assert result.ok is False
    assert "Unknown tool" in (result.error or "")
    assert runtime.memory.failure_streak == 1
    assert runtime.memory.last_error == result.error
    assert runtime.memory.last_tool_results[-1] == result


async def test_execute_rejects_invalid_arguments() -> None:
    page = _make_page_with_locator()
    runtime = ToolRuntime(page=page)

    result = await runtime.execute("navigate", {"wait_until": "load"})

    assert result.ok is False
    assert "Validation error" in (result.error or "")
    assert runtime.memory.failure_streak == 1
    assert runtime.memory.last_tool_results[-1] == result


async def test_execute_dispatches_click_handler_success() -> None:
    page = _make_page_with_locator()
    runtime = ToolRuntime(page=page)

    result = await runtime.execute(
        "click",
        {
            "locator": {"kind": "css", "value": "#submit"},
            "button": "left",
            "click_count": 2,
            "delay_ms": 25,
        },
    )

    assert result.ok is True
    page.locator.return_value.click.assert_awaited_once_with(
        button="left",
        click_count=2,
        delay=25,
    )
    assert runtime.memory.failure_streak == 0
    assert runtime.memory.last_error is None
    assert runtime.memory.last_tool_results[-1] == result


async def test_execute_updates_memory_on_recovery_after_failure() -> None:
    page = _make_page_with_locator()
    page.goto = AsyncMock(side_effect=[RuntimeError("boom"), None])
    runtime = ToolRuntime(page=page)

    first = await runtime.execute("navigate", {"url": "https://example.test"})
    second = await runtime.execute("navigate", {"url": "https://example.test"})

    assert first.ok is False
    assert runtime.memory.last_tool_results[-2] == first
    assert second.ok is True
    assert runtime.memory.failure_streak == 0
    assert runtime.memory.last_error is None
    assert runtime.memory.last_tool_results[-1] == second


async def test_execute_remember_persists_value_in_memory() -> None:
    page = _make_page_with_locator()
    runtime = ToolRuntime(page=page)

    result = await runtime.execute(
        "remember",
        {"name": "status_text", "value": "Welcome"},
    )

    assert result.ok is True
    assert runtime.memory.values["status_text"] == "Welcome"


async def test_execute_report_result_sets_final_result_and_is_final_flag() -> None:
    page = _make_page_with_locator()
    runtime = ToolRuntime(page=page)

    result = await runtime.execute(
        "report_result",
        {
            "passed": True,
            "reason": "All assertions passed",
            "evidence_points": ["Saw dashboard header"],
        },
    )

    assert result.ok is True
    assert result.data["is_final"] is True
    assert runtime.memory.final_result == {
        "passed": True,
        "reason": "All assertions passed",
        "evidence_points": ["Saw dashboard header"],
    }


async def test_execute_read_text_returns_text_and_can_store_it() -> None:
    page = _make_page_with_locator()
    runtime = ToolRuntime(page=page)

    result = await runtime.execute(
        "read_text",
        {
            "locator": {"kind": "css", "value": "h1"},
            "save_as": "header_text",
        },
    )

    assert result.ok is True
    assert result.data["text"] == "Welcome"
    assert runtime.memory.values["header_text"] == "Welcome"


async def test_execute_assert_text_fails_when_text_does_not_match() -> None:
    page = _make_page_with_locator()
    runtime = ToolRuntime(page=page)

    result = await runtime.execute(
        "assert_text",
        {
            "locator": {"kind": "css", "value": "h1"},
            "expected": "Nope",
            "exact": True,
        },
    )

    assert result.ok is False
    assert result.retryable is False
    assert "Expected exact text" in (result.error or "")
