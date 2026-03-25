"""Pytest fixtures for immiclaw-test."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from immiclaw_test.models import (
    AgentConfig,
    BrowserConfig,
    LLMConfig,
    Settings,
    Task,
    TaskSubtask,
    ViewportConfig,
)


@pytest.fixture
def sample_settings() -> Settings:
    """Provide a sample Settings instance for testing."""
    return Settings(
        base_url="http://test.example.com",
        llm=LLMConfig(
            model="gpt-4o",
            base_url="https://api.openai.com/v1",
            api_key="test-api-key",
            temperature=0.0,
        ),
        browser=BrowserConfig(
            headless=True,
            viewport=ViewportConfig(width=1280, height=720),
        ),
        agent=AgentConfig(
            max_steps=30,
            step_timeout_seconds=30,
            screenshot_on_failure=True,
        ),
    )


@pytest.fixture
def sample_task() -> Task:
    """Provide a sample Task instance for testing."""
    return Task(
        name="Test Login Flow",
        description="Verify user can log in with valid credentials",
        start_url="http://test.example.com/login",
        goal="Successfully authenticate and reach the dashboard",
        done_when=[
            "User is redirected to dashboard after login",
            "Username is displayed in header",
        ],
        subtasks=[
            TaskSubtask(
                name="login",
                goal="Log in with valid credentials",
                done_when=["User is redirected to dashboard after login"],
            )
        ],
        max_steps=30,
        timeout_seconds=120,
        test_data={
            "username": "testuser",
            "password": "testpass123",
        },
    )


@pytest.fixture
def mock_page() -> MagicMock:
    """Provide a mock Playwright Page instance for testing.

    The mock provides common async methods used by Playwright pages,
    configured as AsyncMock for proper async/await support.
    """
    page = MagicMock()
    page.goto = AsyncMock(return_value=None)
    page.click = AsyncMock(return_value=None)
    page.fill = AsyncMock(return_value=None)
    page.type = AsyncMock(return_value=None)
    page.wait_for_selector = AsyncMock(return_value=MagicMock())
    page.wait_for_load_state = AsyncMock(return_value=None)
    page.screenshot = AsyncMock(return_value=b"fake-screenshot-bytes")
    page.evaluate = AsyncMock(return_value=None)
    page.query_selector = AsyncMock(return_value=MagicMock())
    page.query_selector_all = AsyncMock(return_value=[])
    page.get_attribute = AsyncMock(return_value=None)
    page.inner_text = AsyncMock(return_value="")
    page.is_visible = AsyncMock(return_value=True)
    page.is_enabled = AsyncMock(return_value=True)
    page.url = "http://test.example.com"
    page.title = AsyncMock(return_value="Test Page")
    page.close = AsyncMock(return_value=None)

    return page
