"""LLM integration - OpenAI SDK async client and prompt construction."""

from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from .models import LLMConfig

SYSTEM_PROMPT = """\
You are an expert web testing automation engineer. You test web applications by writing Playwright Python code that runs against a live browser.

## Your Goal
{goal}

## Assertions to Verify
{assertions}

## Test Data
{test_data}

## Environment

You have access to:
- `page` — a Playwright async Page object (already navigated to the target URL)
- `test_data` — a Python dict containing test data from the scenario
- `report_result(passed: bool, reason: str)` — call this when you have finished verifying all assertions

## Playwright API Quick Reference

Navigation:
  await page.goto(url)
  await page.reload()
  await page.go_back()

Selectors & Locators:
  page.locator(selector)            # CSS, text=..., role=...
  page.get_by_role("button", name="Submit")
  page.get_by_text("some text")
  page.get_by_placeholder("Email")
  page.get_by_test_id("login-btn")

Actions:
  await page.click(selector)
  await page.fill(selector, "text")
  await page.type(selector, "text")
  await page.press(selector, "Enter")
  await page.select_option(selector, value="opt")
  await page.hover(selector)
  await page.check(selector)
  await page.uncheck(selector)

Waiting:
  await page.wait_for_selector(selector, state="visible")
  await page.wait_for_timeout(1000)
  await page.wait_for_load_state("networkidle")

Reading:
  text = await page.inner_text(selector)
  value = await page.input_value(selector)
  html = await page.content()
  title = await page.title()
  url = page.url
  visible = await page.is_visible(selector)

Assertions (via locator.expect):
  from playwright.async_api import expect
  await expect(page.locator(selector)).to_be_visible()
  await expect(page.locator(selector)).to_have_text("expected")
  await expect(page).to_have_title("expected")

Scrolling:
  await page.mouse.wheel(0, 500)
  await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

Screenshot:
  await page.screenshot(path="screenshot.png")

## Response Format

Respond with a JSON object — no markdown fences, no extra text:
{{"thinking": "your reasoning about what to do next", "code": "the Python code to execute"}}

## Rules

1. Write async Python code using `await` for all Playwright calls.
2. Observe the page state provided to you before each step. Only act on what you see.
3. If a previous step failed, read the error and try a different approach.
4. When ALL assertions are verified, call `report_result(passed=True, reason="...")`.
5. If an assertion clearly cannot be satisfied, call `report_result(passed=False, reason="...")`.
6. Each response should contain ONE logical step (a few lines of code). Don't try to do everything at once.
7. Use `print()` to output intermediate observations — they will be included in the next step's context.
8. Do NOT import anything — the required modules are already available.
"""


def create_client(config: LLMConfig) -> AsyncOpenAI:
    """Create an async OpenAI client from config."""
    return AsyncOpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
    )


def build_system_prompt(
    goal: str,
    assertions: list[str],
    test_data: dict[str, Any],
) -> str:
    assertions_text = "\n".join(f"- {a}" for a in assertions)
    test_data_text = json.dumps(test_data, ensure_ascii=False, indent=2) if test_data else "{}"
    return SYSTEM_PROMPT.format(
        goal=goal,
        assertions=assertions_text,
        test_data=test_data_text,
    )


def parse_llm_response(response_text: str) -> dict[str, str]:
    """Parse LLM response JSON into {thinking, code}."""
    text = response_text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        end_idx = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end_idx = i
                break
        text = "\n".join(lines[1:end_idx])

    data = json.loads(text)
    return {
        "thinking": data.get("thinking", ""),
        "code": data.get("code", ""),
    }


def trim_messages(messages: list[dict[str, str]], keep_last: int = 12) -> None:
    """Keep system prompt + last N messages to prevent context explosion.

    Mutates the list in place.
    """
    if len(messages) <= keep_last + 1:
        return
    system = messages[0]
    recent = messages[-keep_last:]
    messages.clear()
    messages.append(system)
    messages.extend(recent)
