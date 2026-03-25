"""Typed input and result models for tool-calling runtime."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocatorRef(ToolModel):
    """Reference to a page element using Playwright locator strategies."""

    kind: Literal["css", "role", "text", "placeholder", "test_id", "label"]
    value: str
    name: str | None = None
    exact: bool = False
    nth: int | None = Field(default=None, ge=0)
    level: int | None = Field(default=None, ge=1, le=6)


class NavigateInput(ToolModel):
    """Navigate to a URL."""

    url: str
    wait_until: Literal["load", "domcontentloaded", "networkidle", "commit"] = "load"


class ReloadInput(ToolModel):
    """Reload the current page."""

    wait_until: Literal["load", "domcontentloaded", "networkidle", "commit"] = "load"


class GoBackInput(ToolModel):
    """Navigate one step back in browser history."""

    wait_until: Literal["load", "domcontentloaded", "networkidle", "commit"] = "load"


class ClickInput(ToolModel):
    """Click an element."""

    locator: LocatorRef
    button: Literal["left", "right", "middle"] = "left"
    click_count: int = Field(default=1, ge=1)
    delay_ms: int = Field(default=0, ge=0)


class FillInput(ToolModel):
    """Fill an input element with text."""

    locator: LocatorRef
    text: str
    clear_first: bool = True


class TypeInput(ToolModel):
    """Type text into an element character-by-character."""

    locator: LocatorRef
    text: str
    delay_ms: int = Field(default=0, ge=0)


class PressInput(ToolModel):
    """Press a key or key combination on an element."""

    locator: LocatorRef
    key: str


class HoverInput(ToolModel):
    """Hover over an element."""

    locator: LocatorRef


class CheckInput(ToolModel):
    """Check or uncheck a checkbox-like element."""

    locator: LocatorRef
    checked: bool = True


class ScrollInput(ToolModel):
    """Scroll the page by pixel deltas."""

    delta_x: int = 0
    delta_y: int = 500


class WaitForSelectorInput(ToolModel):
    """Wait for an element to reach a target state."""

    locator: LocatorRef
    state: Literal["attached", "detached", "visible", "hidden"] = "visible"
    timeout_ms: int = Field(default=30000, ge=0)


class WaitForLoadStateInput(ToolModel):
    """Wait for page load state."""

    state: Literal["load", "domcontentloaded", "networkidle"] = "load"
    timeout_ms: int = Field(default=30000, ge=0)


class WaitForTimeoutInput(ToolModel):
    """Wait a fixed amount of time in milliseconds."""

    timeout_ms: int = Field(ge=0)


class ReadTextInput(ToolModel):
    """Read element text content."""

    locator: LocatorRef
    save_as: str | None = None


class ReadValueInput(ToolModel):
    """Read form element value."""

    locator: LocatorRef
    save_as: str | None = None


class GetPageInfoInput(ToolModel):
    """Get current page URL and title."""


class IsVisibleInput(ToolModel):
    """Check whether an element is visible."""

    locator: LocatorRef


class AssertVisibleInput(ToolModel):
    """Assert an element becomes visible within timeout."""

    locator: LocatorRef
    timeout_ms: int = Field(default=5000, ge=0)


class AssertTextInput(ToolModel):
    """Assert an element contains expected text."""

    locator: LocatorRef
    expected: str
    exact: bool = False
    timeout_ms: int = Field(default=5000, ge=0)


class AssertTitleInput(ToolModel):
    """Assert page title against expected text."""

    expected: str
    exact: bool = False
    timeout_ms: int = Field(default=5000, ge=0)


class AssertUrlInput(ToolModel):
    """Assert current URL against expected value."""

    expected: str
    exact: bool = False
    timeout_ms: int = Field(default=5000, ge=0)


class ScreenshotInput(ToolModel):
    """Capture a screenshot of the current page."""

    path: str | None = None
    full_page: bool = False


class RememberInput(ToolModel):
    """Save a JSON-serializable value in session memory."""

    name: str
    value: Any


class MarkSubtaskDoneInput(ToolModel):
    """Mark a named subtask as completed with a short evidence note."""

    name: str
    reason: str


class ReportResultInput(ToolModel):
    """Report the final task result. This ends the task run."""

    passed: bool
    reason: str
    evidence_points: list[str] = Field(default_factory=list)
    screenshot_on_fail: bool = True


class ToolResult(ToolModel):
    """Standardized result payload returned by all tools."""

    ok: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    retryable: bool = False
    hint: str | None = None


def to_openai_tool_schema(model: type[BaseModel], name: str) -> dict[str, Any]:
    """Generate OpenAI function-tool schema from a Pydantic model."""

    schema = model.model_json_schema()
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": model.__doc__ or "",
            "parameters": {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", []),
            },
            "strict": True,
        },
    }


_REGISTERED_TOOLS: dict[str, type[BaseModel]] = {}


def register_tool(name: str, model: type[BaseModel]) -> None:
    """Register a named tool input model."""

    _REGISTERED_TOOLS[name] = model


def get_all_tool_schemas() -> list[dict[str, Any]]:
    """Return OpenAI-compatible schemas for all registered tools."""

    return [to_openai_tool_schema(model, name) for name, model in _REGISTERED_TOOLS.items()]


def get_tool_schemas(tool_names: list[str] | None = None) -> list[dict[str, Any]]:
    """Return OpenAI-compatible schemas for selected tools, or all when omitted."""

    if tool_names is None:
        return get_all_tool_schemas()

    missing = [name for name in tool_names if name not in _REGISTERED_TOOLS]
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise KeyError(f"Unknown registered tools requested: {missing_text}")

    return [to_openai_tool_schema(_REGISTERED_TOOLS[name], name) for name in tool_names]
