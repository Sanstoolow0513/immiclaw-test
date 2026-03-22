from __future__ import annotations

from typing import Any

from .tool_models import LocatorRef

Page = Any
Locator = Any


def resolve_locator(page: Page, loc: LocatorRef) -> Locator:
    if loc.kind == "css":
        locator = page.locator(loc.value)
    elif loc.kind == "role":
        role_kwargs: dict[str, str | int] = {}
        if loc.name is not None:
            role_kwargs["name"] = loc.name
        if loc.level is not None:
            role_kwargs["level"] = loc.level
        locator = page.get_by_role(loc.value, **role_kwargs)
    elif loc.kind == "text":
        locator = page.get_by_text(loc.value, exact=loc.exact)
    elif loc.kind == "placeholder":
        locator = page.get_by_placeholder(loc.value, exact=loc.exact)
    elif loc.kind == "test_id":
        locator = page.get_by_test_id(loc.value)
    elif loc.kind == "label":
        locator = page.get_by_label(loc.value, exact=loc.exact)
    else:
        raise ValueError(f"Unsupported locator kind: {loc.kind}")

    if loc.nth is not None:
        return locator.nth(loc.nth)
    return locator
