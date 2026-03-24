"""Playwright browser lifecycle management."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator

from .models import BrowserConfig

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page


@asynccontextmanager
async def create_browser(
    config: BrowserConfig,
    *,
    trace_path: Path | None = None,
) -> AsyncGenerator[tuple[Browser, BrowserContext, Page], None]:
    """Launch a browser and yield (browser, context, page).

    When ``trace_path`` is set, starts Playwright tracing and writes ``trace.zip`` on exit
    (use ``playwright show-trace <path>`` to inspect).

    Ensures all resources are cleaned up on exit.
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=config.headless)
        context = await browser.new_context(
            viewport={
                "width": config.viewport.width,
                "height": config.viewport.height,
            },
            locale="zh-CN",
        )
        if trace_path is not None:
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = await context.new_page()

        try:
            yield browser, context, page
        finally:
            if trace_path is not None:
                await context.tracing.stop(path=str(trace_path))
            await context.close()
            await browser.close()
