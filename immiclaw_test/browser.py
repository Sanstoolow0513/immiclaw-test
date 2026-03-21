"""Playwright browser lifecycle management."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator

from .models import BrowserConfig

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page


@asynccontextmanager
async def create_browser(
    config: BrowserConfig,
) -> AsyncGenerator[tuple[Browser, BrowserContext, Page], None]:
    """Launch a browser and yield (browser, context, page).

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
        page = await context.new_page()

        try:
            yield browser, context, page
        finally:
            await context.close()
            await browser.close()
