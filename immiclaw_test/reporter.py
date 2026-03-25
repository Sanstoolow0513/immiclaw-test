"""Test report output - console and JSON file."""

from __future__ import annotations

import json
from pathlib import Path

from .models import TaskReport, TestResult

_COLORS = {
    TestResult.PASS: "\033[92m",
    TestResult.FAIL: "\033[91m",
    TestResult.TIMEOUT: "\033[93m",
    TestResult.ERROR: "\033[91m",
}
_RESET = "\033[0m"


def print_report(report: TaskReport) -> None:
    """Print a human-readable report to the console."""
    color = _COLORS.get(report.result, "")
    label = report.result.value.upper()

    print()
    print(f"{'=' * 60}")
    print(f"  Task:     {report.task_name}")
    print(f"  Result:   {color}{label}{_RESET}")
    if report.reason:
        print(f"  Reason:   {report.reason}")
    print(f"  Steps:    {report.total_steps}")
    print(f"  Time:     {report.elapsed_seconds:.1f}s")
    if report.completed_subtasks:
        print(f"  Done:     {', '.join(report.completed_subtasks)}")
    print(f"{'=' * 60}")

    if report.steps:
        print()
        for step in report.steps:
            status = "\033[92mOK\033[0m" if step.success else "\033[91mFAIL\033[0m"
            print(f"  Step {step.step_number}: [{status}] {step.thinking[:80]}")
            if step.error:
                print(f"    Error: {step.error[:120]}")
    print()


def save_report(report: TaskReport, output_dir: Path | None = None) -> Path:
    """Save report as JSON. Returns the file path."""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "artifacts" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{report.task_name}.json"
    path = output_dir / filename

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, ensure_ascii=False, indent=2)

    return path
