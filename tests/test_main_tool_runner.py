from __future__ import annotations

import importlib.util
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from immiclaw_test.models import Task, TaskReport, TaskSubtask, TestResult as RunResult


def _load_local_main_module():
    main_path = Path(__file__).resolve().parents[1] / "main.py"
    spec = importlib.util.spec_from_file_location("immiclaw_test_main", main_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_run_task_cmd_uses_tool_runner(monkeypatch, sample_settings) -> None:
    main = _load_local_main_module()

    args = SimpleNamespace(
        config_dir=None,
        headless=None,
        base_url=None,
        task_name="qmr-login",
        task_file=None,
        trace=None,
    )
    task = Task(
        name="qmr-login",
        description="Login task",
        start_url="{base_url}/login",
        goal="Log in",
        done_when=["Dashboard is visible"],
        subtasks=[TaskSubtask(name="login", goal="Log in", done_when=["Dashboard is visible"])],
    )
    report = TaskReport(
        task_name="qmr-login",
        result=RunResult.PASS,
        reason="ok",
    )
    page = object()
    runner = AsyncMock(return_value=report)
    backend = object()

    @asynccontextmanager
    async def fake_browser(*args, **kwargs):
        yield object(), object(), page

    monkeypatch.setattr(main, "_install_quiet_exception_handler", lambda: None)
    monkeypatch.setattr(main, "load_settings", lambda config_dir: sample_settings)
    monkeypatch.setattr(
        main,
        "resolve_task_path",
        lambda task_name, task_file, cfg_root: Path("/tmp/qmr-login.yaml"),
    )
    monkeypatch.setattr(main, "load_task", lambda task_path: task)
    monkeypatch.setattr(main, "load_task_skills", lambda task, cfg_root: ([], ""))
    monkeypatch.setattr(main, "new_run_log_dir", lambda: Path("/tmp/run-log"))
    monkeypatch.setattr(main, "create_browser", fake_browser)
    monkeypatch.setattr(main, "create_backend", lambda llm: backend)
    monkeypatch.setattr(main, "run_task", runner)
    monkeypatch.setattr(main, "print_report", lambda report: None)
    monkeypatch.setattr(main, "save_report", lambda report, output_dir: output_dir / "report.json")

    exit_code = await main.run_task_cmd(args)

    assert exit_code == 0
    runner.assert_awaited_once_with(
        task=task,
        page=page,
        backend=backend,
        settings=sample_settings,
        skills=[],
        skills_prompt="",
        output_dir=Path("/tmp/run-log/task-qmr-login"),
    )


@pytest.mark.asyncio
async def test_run_task_cmd_turns_runner_exception_into_error_report(
    monkeypatch,
    sample_settings,
) -> None:
    main = _load_local_main_module()

    args = SimpleNamespace(
        config_dir=None,
        headless=None,
        base_url=None,
        task_name="qmr-login",
        task_file=None,
        trace=None,
    )
    task = Task(
        name="qmr-login",
        description="Login task",
        start_url="{base_url}/login",
        goal="Log in",
        done_when=["Dashboard is visible"],
        subtasks=[TaskSubtask(name="login", goal="Log in", done_when=["Dashboard is visible"])],
    )
    page = object()
    captured: dict[str, TaskReport] = {}

    @asynccontextmanager
    async def fake_browser(*args, **kwargs):
        yield object(), object(), page

    async def failing_runner(**kwargs):
        raise RuntimeError("backend exploded")

    def fake_print_report(report: TaskReport) -> None:
        captured["printed"] = report

    def fake_save_report(report: TaskReport, output_dir: Path) -> Path:
        captured["saved"] = report
        return output_dir / "report.json"

    monkeypatch.setattr(main, "_install_quiet_exception_handler", lambda: None)
    monkeypatch.setattr(main, "load_settings", lambda config_dir: sample_settings)
    monkeypatch.setattr(
        main,
        "resolve_task_path",
        lambda task_name, task_file, cfg_root: Path("/tmp/qmr-login.yaml"),
    )
    monkeypatch.setattr(main, "load_task", lambda task_path: task)
    monkeypatch.setattr(main, "load_task_skills", lambda task, cfg_root: ([], ""))
    monkeypatch.setattr(main, "new_run_log_dir", lambda: Path("/tmp/run-log"))
    monkeypatch.setattr(main, "create_browser", fake_browser)
    monkeypatch.setattr(main, "create_backend", lambda llm: object())
    monkeypatch.setattr(main, "run_task", failing_runner)
    monkeypatch.setattr(main, "print_report", fake_print_report)
    monkeypatch.setattr(main, "save_report", fake_save_report)

    exit_code = await main.run_task_cmd(args)

    assert exit_code == 1
    assert captured["printed"].result == RunResult.ERROR
    assert captured["saved"].result == RunResult.ERROR
    assert captured["saved"].reason == "RuntimeError: backend exploded"
