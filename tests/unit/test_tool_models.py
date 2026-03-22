from __future__ import annotations

import pytest
from pydantic import ValidationError

from immiclaw_test import tool_models
from immiclaw_test.tool_models import (
    AssertTextInput,
    CheckInput,
    ClickInput,
    FillInput,
    GetPageInfoInput,
    GoBackInput,
    HoverInput,
    IsVisibleInput,
    LocatorRef,
    NavigateInput,
    PressInput,
    ReadTextInput,
    ReloadInput,
    ReportResultInput,
    ScreenshotInput,
    ScrollInput,
    ToolResult,
    TypeInput,
    WaitForLoadStateInput,
    WaitForSelectorInput,
    WaitForTimeoutInput,
    get_all_tool_schemas,
    register_tool,
    to_openai_tool_schema,
)


def test_locator_ref_accepts_expected_shapes() -> None:
    css = LocatorRef(kind="css", value="#submit-button")
    role = LocatorRef(kind="role", value="button", name="Submit")
    heading = LocatorRef(kind="role", value="heading", level=1)
    text = LocatorRef(kind="text", value="Click me", exact=True)
    nth = LocatorRef(kind="css", value=".item", nth=2)

    assert css.kind == "css"
    assert role.name == "Submit"
    assert heading.level == 1
    assert text.exact is True
    assert nth.nth == 2


def test_locator_ref_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        LocatorRef(kind="xpath", value="//button")


def test_navigation_inputs_defaults() -> None:
    navigate = NavigateInput(url="https://example.com")
    reload_page = ReloadInput()
    back = GoBackInput()

    assert navigate.wait_until == "load"
    assert reload_page.wait_until == "load"
    assert back.wait_until == "load"


def test_action_inputs_defaults() -> None:
    locator = LocatorRef(kind="css", value="#email")

    click = ClickInput(locator=locator)
    fill = FillInput(locator=locator, text="user@example.com")
    type_text = TypeInput(locator=locator, text="abc")
    press = PressInput(locator=locator, key="Enter")
    hover = HoverInput(locator=locator)
    check = CheckInput(locator=locator)
    scroll = ScrollInput()

    assert click.button == "left"
    assert click.click_count == 1
    assert click.delay_ms == 0
    assert fill.clear_first is True
    assert type_text.delay_ms == 0
    assert press.key == "Enter"
    assert hover.locator == locator
    assert check.checked is True
    assert scroll.delta_x == 0
    assert scroll.delta_y == 500


def test_waiting_and_reading_inputs() -> None:
    locator = LocatorRef(kind="test_id", value="status")

    wait_for = WaitForSelectorInput(locator=locator)
    wait_for_state = WaitForLoadStateInput()
    wait_for_timeout = WaitForTimeoutInput(timeout_ms=250)
    read_text = ReadTextInput(locator=locator, save_as="status_text")
    visible = IsVisibleInput(locator=locator)
    page_info = GetPageInfoInput()

    assert wait_for.state == "visible"
    assert wait_for.timeout_ms == 30000
    assert wait_for_state.state == "load"
    assert wait_for_state.timeout_ms == 30000
    assert wait_for_timeout.timeout_ms == 250
    assert read_text.save_as == "status_text"
    assert visible.locator == locator
    assert page_info.model_dump() == {}


def test_assertion_evidence_and_report_inputs() -> None:
    locator = LocatorRef(kind="label", value="Name")

    assert_text = AssertTextInput(locator=locator, expected="Alice")
    screenshot = ScreenshotInput()
    report = ReportResultInput(passed=True, reason="All checks passed")

    assert assert_text.exact is False
    assert assert_text.timeout_ms == 5000
    assert screenshot.full_page is False
    assert report.evidence_points == []
    assert report.screenshot_on_fail is True


def test_tool_result_uses_independent_data_defaults() -> None:
    first = ToolResult(ok=True)
    second = ToolResult(ok=True)
    first.data["value"] = 1

    assert first.data == {"value": 1}
    assert second.data == {}


def test_to_openai_tool_schema_uses_model_schema() -> None:
    schema = to_openai_tool_schema(NavigateInput, "navigate")

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "navigate"
    assert schema["function"]["strict"] is True
    parameters = schema["function"]["parameters"]
    assert parameters["type"] == "object"
    assert "url" in parameters["properties"]
    assert "url" in parameters["required"]


def test_register_tool_and_get_all_tool_schemas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tool_models, "_REGISTERED_TOOLS", {})

    register_tool("navigate", NavigateInput)
    register_tool("reload_page", ReloadInput)
    schemas = get_all_tool_schemas()

    names = [entry["function"]["name"] for entry in schemas]
    assert names == ["navigate", "reload_page"]
