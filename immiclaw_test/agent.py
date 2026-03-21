"""Agent loop - the observe -> prompt -> LLM -> exec -> feedback cycle."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from .executor import execute_code
from .llm import build_system_prompt, create_client, parse_llm_response, trim_messages
from .models import (
    Scenario,
    Settings,
    StepRecord,
    TestReport,
    TestResult,
)
from .observer import format_state_for_llm, get_page_state

if TYPE_CHECKING:
    from playwright.async_api import Page


async def run_scenario(scenario: Scenario, page: Page, settings: Settings) -> TestReport:
    """Execute a test scenario via the LLM agent loop.

    Loop:
    1. Observe page state (accessibility tree)
    2. Send state to LLM, receive generated Python code
    3. Execute code via exec() with page in namespace
    4. Feed result/error back to LLM
    5. Repeat until report_result() called, max_steps, or timeout
    """
    client = create_client(settings.llm)

    system_prompt = build_system_prompt(
        goal=scenario.goal,
        assertions=scenario.assertions,
        test_data=scenario.test_data,
    )

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]

    max_steps = scenario.max_steps
    step_timeout = settings.agent.step_timeout_seconds

    steps: list[StepRecord] = []
    screenshots: list[str] = []
    start_time = time.time()

    target_url = scenario.target_url.format(base_url=settings.base_url)
    await page.goto(target_url, wait_until="domcontentloaded", timeout=15000)

    for step_num in range(1, max_steps + 1):
        elapsed = time.time() - start_time
        if elapsed > scenario.timeout_seconds:
            return _build_report(
                scenario, TestResult.TIMEOUT,
                "Exceeded scenario timeout",
                steps, screenshots, elapsed,
            )

        page_state = await get_page_state(page)
        state_text = format_state_for_llm(page_state)

        step_msg = f"Step {step_num}/{max_steps}\n\n{state_text}"
        messages.append({"role": "user", "content": step_msg})
        trim_messages(messages)

        try:
            response = await client.chat.completions.create(
                model=settings.llm.model,
                messages=messages,
                temperature=settings.llm.temperature,
            )
            response_text = response.choices[0].message.content or ""
            messages.append({"role": "assistant", "content": response_text})

            parsed = parse_llm_response(response_text)
            thinking = parsed["thinking"]
            code = parsed["code"]
        except Exception as e:
            steps.append(StepRecord(
                step_number=step_num,
                thinking="Failed to get/parse LLM response",
                success=False,
                error=f"LLM error: {e}",
                page_url=page.url,
            ))
            messages.append({
                "role": "user",
                "content": (
                    f"Error parsing your response: {e}\n"
                    'Please respond with valid JSON: {"thinking": "...", "code": "..."}'
                ),
            })
            continue

        if not code.strip():
            steps.append(StepRecord(
                step_number=step_num,
                thinking=thinking,
                success=False,
                error="LLM returned empty code",
                page_url=page.url,
            ))
            messages.append({
                "role": "user",
                "content": "Your response contained no code. Please provide code to execute.",
            })
            continue

        result = await execute_code(
            code=code,
            page=page,
            test_data=scenario.test_data,
            timeout=float(step_timeout),
        )

        steps.append(StepRecord(
            step_number=step_num,
            code=code,
            thinking=thinking,
            output=result.output,
            error=result.error,
            success=result.success,
            page_url=page.url,
        ))

        if result.reported:
            passed = result.reported.get("passed", False)
            reason = result.reported.get("reason", "")
            final_result = TestResult.PASS if passed else TestResult.FAIL
            return _build_report(
                scenario, final_result, reason,
                steps, screenshots, time.time() - start_time,
            )

        if result.success:
            feedback = f"Code executed successfully."
            if result.output:
                feedback += f"\nOutput:\n{result.output}"
        else:
            feedback = f"Code execution failed.\nError: {result.error}"
            if result.output:
                feedback += f"\nPartial output:\n{result.output}"

            if settings.agent.screenshot_on_failure:
                ss_path = f"artifacts/screenshots/fail_step{step_num}.png"
                try:
                    await page.screenshot(path=ss_path)
                    screenshots.append(ss_path)
                except Exception:
                    pass

        messages.append({"role": "user", "content": feedback})

    return _build_report(
        scenario, TestResult.TIMEOUT,
        "Reached max steps",
        steps, screenshots, time.time() - start_time,
    )


def _build_report(
    scenario: Scenario,
    result: TestResult,
    reason: str,
    steps: list[StepRecord],
    screenshots: list[str],
    elapsed: float,
) -> TestReport:
    return TestReport(
        scenario_name=scenario.name,
        result=result,
        reason=reason,
        total_steps=len(steps),
        elapsed_seconds=round(elapsed, 2),
        steps=steps,
        screenshots=screenshots,
    )
