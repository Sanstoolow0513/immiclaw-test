"""LLM integration - OpenAI SDK async client and prompt construction."""

from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from .models import LLMConfig

_REASON_FALLBACK_MAX = 2000
_POINT_FALLBACK_MAX = 500


def _normalize_final_and_evidence(
    thinking: str,
    status: str,
    final: dict[str, Any] | None,
    evidence: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Backfill protocol fields the model often omits so runs do not burn steps on JSON nitpicks."""
    if status not in {"final_pass", "final_fail"} or final is None:
        return final, evidence

    out_evidence = {
        "screenshot_required": bool(evidence.get("screenshot_required", False)),
        "points": list(evidence.get("points", [])),
    }

    reason = str(final.get("reason", "")).strip()
    if not reason:
        t = thinking.strip()
        final = dict(final)
        final["reason"] = (t[:_REASON_FALLBACK_MAX] if len(t) > _REASON_FALLBACK_MAX else t) if t else ""

    if status == "final_fail":
        out_evidence["screenshot_required"] = True
        if not any(str(p).strip() for p in out_evidence["points"]):
            r = str(final.get("reason", "")).strip()
            out_evidence["points"] = [
                (r[:_POINT_FALLBACK_MAX] if len(r) > _POINT_FALLBACK_MAX else r)
                if r
                else "未提供具体问题点；请结合 final.reason 与页面状态排查"
            ]

    return final, out_evidence


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
- `expect` — Playwright assertion helper (same as `playwright.async_api.expect`)
- `re` — Python `re` module (regex)
- `json` — Python `json` module
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

Assertions (via locator.expect — `expect` is pre-injected, do not import):
  await expect(page.locator(selector)).to_be_visible()
  await expect(page.locator(selector)).to_have_text("expected")
  await expect(page).to_have_title("expected")

Locator strict mode (multiple matches error):
  Prefer `.first` or narrow the locator, e.g. `page.get_by_role("heading", name="X", level=1).first`
  or `page.get_by_text("X", exact=True)`; avoid `get_by_text` when the same substring appears twice.

Scrolling:
  await page.mouse.wheel(0, 500)
  await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

Screenshot:
  await page.screenshot(path="screenshot.png")

## Response Format

Respond with a JSON object — no markdown fences, no extra text:
{{
  "thinking": "your reasoning about what to do next",
  "code": "the Python code to execute (can be empty only when status is final_*)",
  "status": "continue | final_pass | final_fail",
  "evidence": {{
    "screenshot_required": false,
    "points": []
  }},
  "final": null
}}

For `status="continue"`, keep `"final": null` (or omit `final`). Only include the `final` object when `status` is `final_pass` or `final_fail`.

## Rules

1. Write async Python code using `await` for all Playwright calls.
2. Observe the page state provided to you before each step. Only act on what you see.
3. If a previous step failed, read the error and try a different approach.
4. Use `status="continue"` when more actions are needed; use `"final": null` — never send `final.passed=false` with `continue` (that is treated as a finished failed run only when there is no code).
5. Use `status="final_pass"` only when ALL assertions are verified.
6. Use `status="final_fail"` only when assertion failure is clear and reproducible.
7. For `final_fail`, evidence is mandatory: set `evidence.screenshot_required=true` and provide at least one item in `evidence.points`.
8. Each item in `evidence.points` must include: location clue (element/area/text), abnormal behavior, expected behavior.
9. When using final statuses, include `final.passed` and `final.reason`. `final.passed` must match status.
10. You may still call `report_result(...)` for compatibility, but final status JSON is preferred.
11. Each response should contain ONE logical step (a few lines of code). Don't try to do everything at once.
12. Use `print()` sparingly for short observations only (see §8); they are echoed into the next step.
13. Do NOT use `import` — use the pre-injected names: `expect`, `re`, `json`, `asyncio`, plus `page` and `test_data`.

## Common Mistakes — Read Before Writing Any Code

### 1. await precedence (most common error)
`await` binds to the whole expression on its right, so method-chaining after a coroutine call silently
operates on the coroutine object, not its result.

  WRONG: `text = await locator.inner_text().strip()`
         (calls .strip() on a coroutine object → AttributeError)
  RIGHT: `text = (await locator.inner_text()).strip()`

Apply this rule to ALL chained calls: `.strip()`, `.lower()`, `[0]`, `.split()`, etc.

### 2. report_result is now async — both forms are correct
  `report_result(True, "All checks passed")`       # sync call — OK
  `await report_result(True, "All checks passed")` # await — also OK

### 3. alert role gives false positives
`get_by_role("alert")` matches every ARIA alert region on the page, including invisible
screen-reader-only announcer nodes that are always present. Do NOT count alerts as a proxy
for error messages. To assert a visible error:
  - Use `get_by_text("exact error wording", exact=True)` for visible text
  - Use `get_by_role("alertdialog")` for modal error dialogs
  - Use `page.locator(".error-class")` with a real CSS class

### 4. Variables persist across steps
Any variable you define in step N is automatically available in step N+1. You do NOT need to
re-read the page or recompute values you already have.

  Step 3: `first_title = (await page.locator("h2").first.inner_text()).strip()`
  Step 5: `print(first_title)`  # works — no NameError

### 5. Strict-mode locator conflicts
When a locator matches multiple elements, Playwright raises a strict-mode error. Fix it:
  - Add `.first` to take the first match: `page.get_by_role("heading").first`
  - Narrow with `exact=True`: `page.get_by_text("Home", exact=True)`
  - Add `level=` for headings: `page.get_by_role("heading", level=1)`
  - Use a CSS selector to target a specific container
  - **Never** pass a multi-match locator to `expect(...)` without narrowing: e.g.
    `await expect(page.get_by_text(re.compile(r"博客")).first).to_be_visible()`
  - For homepage/feature **cards**, prefer `get_by_role("link", name=re.compile(r"..."))`
    with a pattern unique to that card, instead of a loose `get_by_text(re.compile(r"编辑器|…"))`
    that also matches paragraphs and list items.

### 6. asyncio is pre-injected
`await asyncio.sleep(1)` and other asyncio utilities are available without import.

### 7. Regex string literals in Python
For `re.compile(...)`, **always** use a raw string when the pattern contains backslashes:
  - RIGHT: `re.compile(r"Markdown\\s*编辑器")` (raw string: pattern is Markdown + optional whitespace + 编辑器)
    or a similar raw string for counts like 共 + whitespace + digits + 篇文章
  - WRONG: non-raw `re.compile("Markdown\\s*编辑器")` — invalid/deprecated escapes and SyntaxWarning.

### 8. Keep stdout small
Avoid dumping `await page.locator("body").inner_text()` (or huge slices) via `print`.
Use at most a short preview (about 400 characters) or a few numeric counters so the next
step’s prompt stays readable.
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


def parse_llm_response(response_text: str) -> dict[str, Any]:
    """Parse LLM response JSON with backward compatibility."""
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
    thinking = str(data.get("thinking", ""))
    code = str(data.get("code", ""))

    status = str(data.get("status", "")).strip() or "continue"
    if status not in {"continue", "final_pass", "final_fail"}:
        status = "continue"

    evidence_raw = data.get("evidence")
    screenshot_required = False
    points: list[str] = []
    if isinstance(evidence_raw, dict):
        screenshot_required = bool(evidence_raw.get("screenshot_required", False))
        raw_points = evidence_raw.get("points", [])
        if isinstance(raw_points, list):
            points = [str(p).strip() for p in raw_points if str(p).strip()]

    final_raw = data.get("final")
    final: dict[str, Any] | None = None
    if isinstance(final_raw, dict) and "passed" in final_raw:
        final = {
            "passed": bool(final_raw.get("passed")),
            "reason": str(final_raw.get("reason", "")).strip(),
        }
    elif status in {"final_pass", "final_fail"}:
        # Allow final decision even if `final` object is omitted.
        final = {
            "passed": status == "final_pass",
            "reason": "",
        }

    # Old schema compatibility: infer final_* from `final.passed` only when there is no code to run.
    # Otherwise models often copy a template `final: {passed: false}` with `continue` + code, which
    # must NOT be promoted to final_fail (would skip execution and end the scenario).
    if status == "continue" and final is not None and not code.strip():
        status = "final_pass" if final["passed"] else "final_fail"

    evidence_dict = {
        "screenshot_required": screenshot_required,
        "points": points,
    }
    final, evidence_dict = _normalize_final_and_evidence(
        thinking, status, final, evidence_dict
    )

    return {
        "thinking": thinking,
        "code": code,
        "status": status,
        "evidence": evidence_dict,
        "final": final,
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
