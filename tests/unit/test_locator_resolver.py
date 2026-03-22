from __future__ import annotations

from unittest.mock import MagicMock

from immiclaw_test.locator_resolver import resolve_locator
from immiclaw_test.tool_models import LocatorRef


def test_resolve_locator_maps_css_kind() -> None:
    page = MagicMock()
    resolved = MagicMock()
    page.locator.return_value = resolved
    loc = LocatorRef(kind="css", value="#submit")

    result = resolve_locator(page, loc)

    page.locator.assert_called_once_with("#submit")
    assert result is resolved


def test_resolve_locator_maps_role_kind_with_name_and_level() -> None:
    page = MagicMock()
    resolved = MagicMock()
    page.get_by_role.return_value = resolved
    loc = LocatorRef(kind="role", value="heading", name="Dashboard", level=2)

    result = resolve_locator(page, loc)

    page.get_by_role.assert_called_once_with("heading", name="Dashboard", level=2)
    assert result is resolved


def test_resolve_locator_maps_text_kind_with_exact() -> None:
    page = MagicMock()
    resolved = MagicMock()
    page.get_by_text.return_value = resolved
    loc = LocatorRef(kind="text", value="Submit", exact=True)

    result = resolve_locator(page, loc)

    page.get_by_text.assert_called_once_with("Submit", exact=True)
    assert result is resolved


def test_resolve_locator_maps_placeholder_kind_with_exact() -> None:
    page = MagicMock()
    resolved = MagicMock()
    page.get_by_placeholder.return_value = resolved
    loc = LocatorRef(kind="placeholder", value="Email", exact=True)

    result = resolve_locator(page, loc)

    page.get_by_placeholder.assert_called_once_with("Email", exact=True)
    assert result is resolved


def test_resolve_locator_maps_test_id_kind() -> None:
    page = MagicMock()
    resolved = MagicMock()
    page.get_by_test_id.return_value = resolved
    loc = LocatorRef(kind="test_id", value="nav-menu")

    result = resolve_locator(page, loc)

    page.get_by_test_id.assert_called_once_with("nav-menu")
    assert result is resolved


def test_resolve_locator_maps_label_kind_with_exact() -> None:
    page = MagicMock()
    resolved = MagicMock()
    page.get_by_label.return_value = resolved
    loc = LocatorRef(kind="label", value="Password", exact=True)

    result = resolve_locator(page, loc)

    page.get_by_label.assert_called_once_with("Password", exact=True)
    assert result is resolved


def test_resolve_locator_applies_nth_when_specified() -> None:
    page = MagicMock()
    base_locator = MagicMock()
    nth_locator = MagicMock()
    page.get_by_text.return_value = base_locator
    base_locator.nth.return_value = nth_locator
    loc = LocatorRef(kind="text", value="Item", nth=3)

    result = resolve_locator(page, loc)

    page.get_by_text.assert_called_once_with("Item", exact=False)
    base_locator.nth.assert_called_once_with(3)
    assert result is nth_locator
