"""Agent loop - the observe -> prompt -> LLM -> exec -> feedback cycle."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import re
import time
from typing import TYPE_CHECKING, Any

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


_FEEDBACK_STDOUT_MAX_CHARS = 6000


def _truncate_feedback_stdout(text: str, max_chars: int = _FEEDBACK_STDOUT_MAX_CHARS) -> str:
    """Limit code stdout in LLM feedback so one verbose print does not blow the context window."""
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n...[stdout truncated for prompt size; full output is in step records / reports]"


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip())
    text = re.sub(r"-{2,}", "-", text).strip("-_")
    return text or "unknown"


def scenario_dir_slug(name: str) -> str:
    """Filesystem-safe single path segment for a scenario name (run output subfolder)."""
    return _slugify(name)


def _build_screenshot_path(
    scenario_output_dir: Path | None,
    scenario_name: str,
    name: str,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name_slug = _slugify(name)
    if scenario_output_dir is not None:
        scenario_output_dir.mkdir(parents=True, exist_ok=True)
        return scenario_output_dir / f"{timestamp}--{name_slug}.png"
    task_slug = _slugify(scenario_name)
    repo_root = Path(__file__).resolve().parent.parent
    runs = repo_root / "artifacts" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    output_path = runs / f"{timestamp}--{task_slug}--{name_slug}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def _write_model_json(
    scenario_output_dir: Path | None,
    scenario_name: str,
    llm_model: str,
    events: list[dict[str, Any]],
) -> None:
    if scenario_output_dir is None:
        return
    scenario_output_dir.mkdir(parents=True, exist_ok=True)
    path = scenario_output_dir / "model.json"
    payload: dict[str, Any] = {
        "scenario_name": scenario_name,
        "llm_model": llm_model,
        "events": events,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _usage_dict(response: Any) -> dict[str, Any] | None:
    u = getattr(response, "usage", None)
    if u is None:
        return None
    return {
        "prompt_tokens": getattr(u, "prompt_tokens", None),
        "completion_tokens": getattr(u, "completion_tokens", None),
        "total_tokens": getattr(u, "total_tokens", None),
    }


async def run_scenario(
    scenario: Scenario,
    page: Page,
    settings: Settings,
    scenario_output_dir: Path | None = None,
) -> TestReport:
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
    step_state: dict[str, Any] = {}
    model_events: list[dict[str, Any]] = []

    target_url = scenario.target_url.format(base_url=settings.base_url)
    await page.goto(target_url, wait_until="domcontentloaded", timeout=15000)

    try:
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
                model_events.append(
                    {
                        "event": "completion",
                        "step": step_num,
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "user_message_chars": len(step_msg),
                        "assistant_message": response_text,
                        "usage": _usage_dict(response),
                    },
                )

                parsed = parse_llm_response(response_text)
                thinking = parsed["thinking"]
                code = parsed["code"]
                status = parsed["status"]
                evidence = parsed["evidence"]
                final = parsed["final"]
                points = evidence.get("points", [])
            except Exception as e:
                model_events.append(
                    {
                        "event": "error",
                        "step": step_num,
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                        "user_message_chars": len(step_msg),
                        "error": str(e),
                    },
                )
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
                        'Please respond with valid JSON fields including '
                        '{"thinking": "...", "code": "...", "status": "continue|final_pass|final_fail"}'
                    ),
                })
                continue

            if status in {"final_pass", "final_fail"}:
                validation_error = _validate_final_payload(status, final, evidence)
                if validation_error:
                    steps.append(StepRecord(
                        step_number=step_num,
                        code=code,
                        thinking=thinking,
                        success=False,
                        error=validation_error,
                        page_url=page.url,
                    ))
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Invalid final response: {validation_error}\n"
                            "Please resend a valid final JSON with required fields."
                        ),
                    })
                    continue

                reason = (final or {}).get("reason", "") or "Final decision reported by model."
                if points:
                    reason = _merge_reason_and_points(reason, points)

                if status == "final_fail" and settings.agent.screenshot_on_failure and evidence.get("screenshot_required", False):
                    ss_path = _build_screenshot_path(
                        scenario_output_dir,
                        scenario.name,
                        f"final-fail-step{step_num}",
                    )
                    try:
                        await page.screenshot(path=str(ss_path))
                        screenshots.append(str(ss_path))
                    except Exception:
                        pass

                steps.append(StepRecord(
                    step_number=step_num,
                    code=code,
                    thinking=thinking,
                    output="",
                    error=None if status == "final_pass" else reason,
                    success=status == "final_pass",
                    page_url=page.url,
                ))
                return _build_report(
                    scenario,
                    TestResult.PASS if status == "final_pass" else TestResult.FAIL,
                    reason,
                    steps,
                    screenshots,
                    time.time() - start_time,
                )

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
                step_state=step_state,
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
                    feedback += f"\nOutput:\n{_truncate_feedback_stdout(result.output)}"
            else:
                feedback = f"Code execution failed.\nError: {result.error}"
                if result.output:
                    feedback += f"\nPartial output:\n{_truncate_feedback_stdout(result.output)}"

                if settings.agent.screenshot_on_failure:
                    ss_path = _build_screenshot_path(
                        scenario_output_dir,
                        scenario.name,
                        f"fail-step{step_num}",
                    )
                    try:
                        await page.screenshot(path=str(ss_path))
                        screenshots.append(str(ss_path))
                    except Exception:
                        pass

            if points:
                feedback += "\nLLM noted issue points:\n" + "\n".join(f"- {p}" for p in points)

            messages.append({"role": "user", "content": feedback})

        return _build_report(
            scenario, TestResult.TIMEOUT,
            "Reached max steps",
            steps, screenshots, time.time() - start_time,
        )
    finally:
        _write_model_json(
            scenario_output_dir,
            scenario.name,
            settings.llm.model,
            model_events,
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


def _validate_final_payload(
    status: str,
    final: dict[str, Any] | None,
    evidence: dict[str, Any],
) -> str | None:
    if final is None:
        return "`final` object is required when status is final_*."

    passed = bool(final.get("passed"))
    if status == "final_pass" and not passed:
        return "`final.passed` must be true when status=final_pass."
    if status == "final_fail" and passed:
        return "`final.passed` must be false when status=final_fail."

    reason = str(final.get("reason", "")).strip()
    if not reason:
        return "`final.reason` is required when status is final_*."

    if status == "final_fail":
        if not evidence.get("screenshot_required", False):
            return "`evidence.screenshot_required` must be true when status=final_fail."
        points = evidence.get("points", [])
        if not isinstance(points, list) or not any(str(p).strip() for p in points):
            return "At least one non-empty item is required in `evidence.points` when status=final_fail."
    return None


def _merge_reason_and_points(reason: str, points: list[str]) -> str:
    clean_points = [p.strip() for p in points if p.strip()]
    if not clean_points:
        return reason
    points_block = "\n".join(f"- {p}" for p in clean_points)
    return f"{reason}\nIssue points:\n{points_block}"
