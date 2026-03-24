"""CLI entry point for the LLM-driven Playwright testing tool."""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from immiclaw_test.agent import run_scenario, scenario_dir_slug
from immiclaw_test.browser import create_browser
from immiclaw_test.config import load_scenario, load_settings
from immiclaw_test.models import Settings, TestReport
from immiclaw_test.reporter import print_report, save_report


def _effective_config_dir(config_dir: str | None) -> Path:
    if config_dir:
        return Path(config_dir)
    return Path(__file__).resolve().parent / "config"


def iter_scenario_stems(scenarios_dir: Path) -> list[str]:
    """Sorted unique scenario stems (filename without extension) under ``scenarios_dir``."""
    if not scenarios_dir.is_dir():
        return []
    stems = {p.stem for p in scenarios_dir.glob("*.yaml")}
    stems |= {p.stem for p in scenarios_dir.glob("*.yml")}
    return sorted(stems)


def iter_scenario_paths(scenarios_dir: Path) -> list[Path]:
    """Sorted scenario YAML paths under ``scenarios_dir`` (non-recursive)."""
    if not scenarios_dir.is_dir():
        return []
    paths = list(scenarios_dir.glob("*.yaml")) + list(scenarios_dir.glob("*.yml"))
    return sorted(paths, key=lambda p: (p.stem.lower(), p.suffix))


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def new_run_log_dir() -> Path:
    """Create ``artifacts/runs/<YYYYMMDD-HHMMSS>/`` for this CLI invocation."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = _project_root() / "artifacts" / "runs" / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def scenario_output_dir(run_dir: Path, scenario_name: str) -> Path:
    """Per-scenario folder under a run directory."""
    sub = run_dir / scenario_dir_slug(scenario_name)
    sub.mkdir(parents=True, exist_ok=True)
    return sub


def resolve_scenario_path(scenario: str, config_dir: Path) -> Path:
    """Resolve CLI scenario argument to a YAML file path.

    Accepts either a filesystem path to a YAML file or a short name that maps to
    ``<config_dir>/scenarios/<name>.yaml`` (or ``.yml``). A short name may omit
    the extension.
    """
    path = Path(scenario)
    if path.is_file():
        return path.resolve()

    scenarios_dir = config_dir / "scenarios"
    base = scenario
    if base.endswith((".yaml", ".yml")):
        base = Path(base).stem
    for ext in (".yaml", ".yml"):
        candidate = scenarios_dir / f"{base}{ext}"
        if candidate.is_file():
            return candidate.resolve()

    if path.suffix in (".yaml", ".yml"):
        return path

    stems = iter_scenario_stems(scenarios_dir)
    hint = f" Known names: {', '.join(stems)}." if stems else ""
    raise SystemExit(
        f"Error: scenario {scenario!r} not found under {scenarios_dir}.{hint}"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    argv = sys.argv[1:] if argv is None else argv

    parser = argparse.ArgumentParser(
        description="LLM-driven Playwright web testing tool",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print scenario short names under config/scenarios and exit",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run every *.yaml / *.yml under config/scenarios in parallel (no SCENARIO arg)",
    )
    parser.add_argument(
        "scenario",
        nargs="?",
        default=None,
        metavar="SCENARIO",
        help=(
            "Scenario: short name (e.g. smoke-login) loads config/scenarios/<name>.yaml, "
            "or a path to a scenario YAML file (not used with --list or --all)"
        ),
    )
    parser.add_argument(
        "--config-dir",
        default=None,
        help="Path to config directory (default: ./config)",
    )
    parser.add_argument(
        "--headless",
        default=None,
        choices=["true", "false"],
        help="Run browser in headless mode (overrides settings.yaml)",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Target site base URL (overrides settings.yaml and .env)",
    )
    parser.add_argument(
        "--trace",
        nargs="?",
        const=str(Path(__file__).resolve().parent / "artifacts" / "traces"),
        default=None,
        metavar="DIR",
        help=(
            "Record Playwright trace per scenario (zip under DIR; default: ./artifacts/traces). "
            "Inspect with: playwright show-trace <file.zip>"
        ),
    )
    ns = parser.parse_args(argv)
    if ns.list:
        if ns.scenario is not None:
            parser.error("argument SCENARIO: not allowed with --list")
        if ns.all:
            parser.error("argument --all: not allowed with --list")
    elif ns.all:
        if ns.scenario is not None:
            parser.error("argument SCENARIO: not allowed with --all")
    elif ns.scenario is None:
        parser.error(
            "the following arguments are required: SCENARIO (unless --list or --all)"
        )
    return ns


async def run(args: argparse.Namespace) -> int:
    _install_quiet_exception_handler()
    cfg_root = _effective_config_dir(args.config_dir)
    config_dir = Path(args.config_dir) if args.config_dir else None
    settings = load_settings(config_dir)

    if args.headless is not None:
        settings.browser.headless = args.headless == "true"
    if args.base_url:
        settings.base_url = args.base_url

    scenario_path = resolve_scenario_path(args.scenario, cfg_root)

    if not settings.llm.api_key:
        print("Error: LLM_API_KEY not set. Create a .env file or set the environment variable.")
        return 1

    scenario = load_scenario(scenario_path)

    run_dir = new_run_log_dir()
    scen_dir = scenario_output_dir(run_dir, scenario.name)
    print(f"Run log: {run_dir.resolve()}")
    print(f"  Scenario output: {scen_dir.resolve()}")

    trace_file: Path | None = None
    if args.trace:
        trace_dir = Path(args.trace)
        trace_file = trace_dir / f"{scenario.name}-{datetime.now():%Y%m%d-%H%M%S}.zip"

    print(f"Running scenario: {scenario.name}")
    print(f"  Target: {scenario.target_url.format(base_url=settings.base_url)}")
    print(f"  Model:  {settings.llm.model}")
    print(f"  Goal:   {scenario.goal[:80]}...")
    print()

    async with create_browser(settings.browser, trace_path=trace_file) as (
        browser,
        context,
        page,
    ):
        report = await run_scenario(
            scenario, page, settings, scenario_output_dir=scen_dir
        )

    print_report(report)

    report_path = save_report(report, output_dir=scen_dir)
    print(f"Report saved to: {report_path}")
    if trace_file is not None:
        print(f"Playwright trace: {trace_file.resolve()}")

    return 0 if report.result.value == "pass" else 1


async def _run_one_scenario_path(
    scenario_path: Path,
    settings: Settings,
    run_log_dir: Path,
    trace_dir: Path | None = None,
) -> tuple[Path, TestReport | Exception, Path | None]:
    """Run a single scenario file.

    Returns ``(path, report_or_exc, trace_zip_or_none)``.
    """
    trace_file: Path | None = None
    try:
        scenario = load_scenario(scenario_path)
        scen_dir = scenario_output_dir(run_log_dir, scenario.name)
        if trace_dir is not None:
            trace_file = (
                trace_dir
                / f"{scenario.name}-{datetime.now():%Y%m%d-%H%M%S}.zip"
            )
        async with create_browser(settings.browser, trace_path=trace_file) as (
            _,
            _,
            page,
        ):
            report = await run_scenario(
                scenario, page, settings, scenario_output_dir=scen_dir
            )
        return scenario_path, report, trace_file
    except Exception as exc:
        return scenario_path, exc, None


def _install_quiet_exception_handler() -> None:
    """Suppress 'Future exception was never retrieved' noise from cancelled Playwright ops.

    When asyncio.wait_for cancels a timed-out step, Playwright's internal Futures may
    complete with TimeoutError after the task is gone.  Python's default exception handler
    prints a warning for every such Future; we silence those specific cases.
    """
    loop = asyncio.get_event_loop()
    default = loop.get_exception_handler()

    def _handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        msg = context.get("message", "")
        if "Future exception was never retrieved" in msg:
            return
        if callable(default):
            default(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(_handler)


async def run_all_parallel(args: argparse.Namespace) -> int:
    """Load settings once, run every scenario under config/scenarios in parallel."""
    _install_quiet_exception_handler()
    cfg_root = _effective_config_dir(args.config_dir)
    config_dir = Path(args.config_dir) if args.config_dir else None
    settings = load_settings(config_dir)

    if args.headless is not None:
        settings.browser.headless = args.headless == "true"
    if args.base_url:
        settings.base_url = args.base_url

    if not settings.llm.api_key:
        print("Error: LLM_API_KEY not set. Create a .env file or set the environment variable.")
        return 1

    scenarios_dir = cfg_root / "scenarios"
    paths = iter_scenario_paths(scenarios_dir)
    if not paths:
        print(f"Error: no scenario YAML files found under {scenarios_dir}", file=sys.stderr)
        return 1

    run_dir = new_run_log_dir()
    print(f"Run log: {run_dir.resolve()}")

    print(f"Running {len(paths)} scenarios in parallel under {scenarios_dir}")
    print(f"  Model: {settings.llm.model}")
    print(f"  Base:  {settings.base_url}")
    print()

    trace_dir: Path | None = Path(args.trace) if args.trace else None
    if trace_dir is not None:
        trace_dir.mkdir(parents=True, exist_ok=True)

    results = await asyncio.gather(
        *(
            _run_one_scenario_path(p, settings, run_dir, trace_dir)
            for p in paths
        ),
    )

    exit_code = 0
    saved: list[tuple[Path, Path | None, str]] = []

    for scenario_path, outcome, trace_file in results:
        if isinstance(outcome, TestReport):
            print_report(outcome)
            if trace_file is not None:
                print(f"Playwright trace: {trace_file.resolve()}")
            try:
                scen_dir = scenario_output_dir(run_dir, outcome.scenario_name)
                report_path = save_report(outcome, output_dir=scen_dir)
                saved.append((scenario_path, report_path, outcome.result.value))
                print(f"Report saved to: {report_path}")
            except OSError as e:
                saved.append((scenario_path, None, f"save_error:{e}"))
                print(f"Error saving report for {scenario_path}: {e}", file=sys.stderr)
                exit_code = 1
            if outcome.result.value != "pass":
                exit_code = 1
        else:
            print(f"\n{'=' * 60}", file=sys.stderr)
            print(f"  Scenario file failed: {scenario_path}", file=sys.stderr)
            print(f"  {outcome!r}", file=sys.stderr)
            print(f"{'=' * 60}\n", file=sys.stderr)
            saved.append((scenario_path, None, "error"))
            exit_code = 1

    passed = sum(1 for _, _, s in saved if s == "pass")
    print(f"Summary: {passed}/{len(saved)} passed")
    return exit_code


def cmd_list(args: argparse.Namespace) -> int:
    cfg_root = _effective_config_dir(args.config_dir)
    scenarios_dir = cfg_root / "scenarios"
    if not scenarios_dir.is_dir():
        print(f"Error: scenarios directory not found: {scenarios_dir}", file=sys.stderr)
        return 1
    for stem in iter_scenario_stems(scenarios_dir):
        print(stem)
    return 0


def main() -> None:
    argv = sys.argv[1:]
    if argv and argv[0] == "llm-list":
        from immiclaw_test.llm_proxy.default_list import main_llm_list

        sys.exit(main_llm_list())

    if argv and argv[0] == "llmtest":
        from immiclaw_test.llm_proxy.full_test import main as main_llmtest

        sys.exit(main_llmtest())

    args = parse_args()
    if args.list:
        sys.exit(cmd_list(args))
    if args.all:
        exit_code = asyncio.run(run_all_parallel(args))
    else:
        exit_code = asyncio.run(run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
