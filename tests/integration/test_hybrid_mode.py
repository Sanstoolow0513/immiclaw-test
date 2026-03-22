from __future__ import annotations

from argparse import Namespace
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import main
from immiclaw_test.models import (
    AgentConfig,
    AgentMode,
    BrowserConfig,
    LLMConfig,
    Scenario,
    Settings,
    TestReport as ScenarioReport,
    TestResult as ScenarioResult,
    ViewportConfig,
)


def _make_settings(mode: AgentMode) -> Settings:
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
            mode=mode,
            max_steps=30,
            step_timeout_seconds=30,
            screenshot_on_failure=True,
        ),
    )


def _make_scenario() -> Scenario:
    return Scenario(
        name="Hybrid mode scenario",
        description="Verify mode dispatch behavior",
        target_url="{base_url}/test",
        goal="Finish scenario",
        assertions=["A check"],
    )


def _make_report(result: ScenarioResult = ScenarioResult.PASS) -> ScenarioReport:
    return ScenarioReport(
        scenario_name="Hybrid mode scenario",
        result=result,
        reason="ok",
    )


def _make_args() -> Namespace:
    return Namespace(
        scenario="tests/scenarios/sample.yaml",
        config_dir=None,
        headless=None,
        base_url=None,
    )


@asynccontextmanager
async def _fake_browser_context():
    yield MagicMock(), MagicMock(), MagicMock()


async def test_hybrid_mode_falls_back_to_exec_when_tools_runner_fails(
    monkeypatch,
) -> None:
    settings = _make_settings(AgentMode.HYBRID)
    scenario = _make_scenario()

    tools_runner = AsyncMock(side_effect=RuntimeError("tool runner failed"))
    exec_runner = AsyncMock(return_value=_make_report())

    monkeypatch.setattr(main, "load_settings", lambda config_dir=None: settings)
    monkeypatch.setattr(main, "load_scenario", lambda _scenario_path: scenario)
    monkeypatch.setattr(main, "create_browser", lambda _config: _fake_browser_context())
    monkeypatch.setattr(main, "create_backend", lambda _llm: object())
    monkeypatch.setattr(main, "run_scenario_with_tools", tools_runner)
    monkeypatch.setattr(main, "run_scenario", exec_runner)
    monkeypatch.setattr(main, "print_report", lambda _report: None)
    monkeypatch.setattr(main, "save_report", lambda _report: Path("report.json"))

    exit_code = await main.run(_make_args())

    assert exit_code == 0
    tools_runner.assert_awaited_once()
    exec_runner.assert_awaited_once()


async def test_tools_mode_uses_tools_runner_only(monkeypatch) -> None:
    settings = _make_settings(AgentMode.TOOLS)
    scenario = _make_scenario()

    tools_runner = AsyncMock(return_value=_make_report())
    exec_runner = AsyncMock(return_value=_make_report())

    monkeypatch.setattr(main, "load_settings", lambda config_dir=None: settings)
    monkeypatch.setattr(main, "load_scenario", lambda _scenario_path: scenario)
    monkeypatch.setattr(main, "create_browser", lambda _config: _fake_browser_context())
    monkeypatch.setattr(main, "create_backend", lambda _llm: object())
    monkeypatch.setattr(main, "run_scenario_with_tools", tools_runner)
    monkeypatch.setattr(main, "run_scenario", exec_runner)
    monkeypatch.setattr(main, "print_report", lambda _report: None)
    monkeypatch.setattr(main, "save_report", lambda _report: Path("report.json"))

    exit_code = await main.run(_make_args())

    assert exit_code == 0
    tools_runner.assert_awaited_once()
    exec_runner.assert_not_awaited()


async def test_exec_mode_uses_exec_runner_only(monkeypatch) -> None:
    settings = _make_settings(AgentMode.EXEC)
    scenario = _make_scenario()

    tools_runner = AsyncMock(return_value=_make_report())
    exec_runner = AsyncMock(return_value=_make_report())

    monkeypatch.setattr(main, "load_settings", lambda config_dir=None: settings)
    monkeypatch.setattr(main, "load_scenario", lambda _scenario_path: scenario)
    monkeypatch.setattr(main, "create_browser", lambda _config: _fake_browser_context())
    monkeypatch.setattr(main, "run_scenario_with_tools", tools_runner)
    monkeypatch.setattr(main, "run_scenario", exec_runner)
    monkeypatch.setattr(main, "print_report", lambda _report: None)
    monkeypatch.setattr(main, "save_report", lambda _report: Path("report.json"))

    exit_code = await main.run(_make_args())

    assert exit_code == 0
    exec_runner.assert_awaited_once()
    tools_runner.assert_not_awaited()
