"""Page state extraction - converts browser state to LLM-readable text."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page


async def get_page_state(page: Page) -> dict:
    """Extract current page state for LLM consumption."""
    state: dict = {
        "url": page.url,
        "title": await page.title(),
    }

    try:
        snapshot = await page.accessibility.snapshot()
        state["accessibility_tree"] = (
            _simplify_tree(snapshot) if snapshot else "Page has no accessible content"
        )
    except Exception:
        state["accessibility_tree"] = "Failed to get accessibility tree"

    return state


def _simplify_tree(node: dict, depth: int = 0) -> str:
    """Convert accessibility tree to indented text representation."""
    lines: list[str] = []
    role = node.get("role", "")
    name = node.get("name", "")
    value = node.get("value", "")

    skip_roles = {"generic", "none", "presentation"}
    if role in skip_roles and not name:
        for child in node.get("children", []):
            lines.append(_simplify_tree(child, depth))
        return "\n".join(filter(None, lines))

    indent = "  " * depth
    parts = [f"{indent}[{role}]"]
    if name:
        parts.append(f'"{name}"')
    if value:
        parts.append(f"value={value}")

    focused = node.get("focused", False)
    disabled = node.get("disabled", False)
    checked = node.get("checked")
    if focused:
        parts.append("(focused)")
    if disabled:
        parts.append("(disabled)")
    if checked is not None:
        parts.append(f"(checked={checked})")

    lines.append(" ".join(parts))

    for child in node.get("children", []):
        child_text = _simplify_tree(child, depth + 1)
        if child_text:
            lines.append(child_text)

    return "\n".join(lines)


def format_state_for_llm(state: dict) -> str:
    """Format page state into a prompt-friendly string."""
    parts = [
        f"Current URL: {state['url']}",
        f"Page Title: {state['title']}",
        "",
        "Page Structure (Accessibility Tree):",
        state["accessibility_tree"],
    ]
    return "\n".join(parts)
