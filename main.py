"""CLI entry point for the LLM-driven Playwright task runner."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
import time

from immiclaw_test.agent import run_task, task_dir_slug
from immiclaw_test.browser import create_browser
from immiclaw_test.config import load_settings, load_task
from immiclaw_test.llm_backends import create_backend
from immiclaw_test.models import Task, TaskReport, TestResult
from immiclaw_test.reporter import print_report, save_report
from immiclaw_test.skill_loader import assemble_skills_prompt, load_skills


def _effective_config_dir(config_dir: str | None) -> Path:
    if config_dir:
        return Path(config_dir)
    return Path(__file__).resolve().parent / "config"


def iter_task_stems(tasks_dir: Path) -> list[str]:
    if not tasks_dir.is_dir():
        return []
    stems = {p.stem for p in tasks_dir.glob("*.yaml")}
    stems |= {p.stem for p in tasks_dir.glob("*.yml")}
    return sorted(stems)


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def new_run_log_dir() -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = _project_root() / "artifacts" / "runs" / stamp
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def task_output_dir(run_dir: Path, task_name: str) -> Path:
    sub = run_dir / f"task-{task_dir_slug(task_name)}"
    sub.mkdir(parents=True, exist_ok=True)
    return sub


def resolve_task_path(task_name: str | None, task_file: str | None, config_dir: Path) -> Path:
    if task_file:
        path = Path(task_file)
        if path.is_file():
            return path.resolve()
        raise SystemExit(f"Error: task file {task_file!r} not found.")

    if not task_name:
        raise SystemExit("Error: provide a task name or --file.")

    path = Path(task_name)
    if path.is_file():
        return path.resolve()

    tasks_dir = config_dir / "tasks"
    base = Path(task_name).stem if task_name.endswith((".yaml", ".yml")) else task_name
    for ext in (".yaml", ".yml"):
        candidate = tasks_dir / f"{base}{ext}"
        if candidate.is_file():
            return candidate.resolve()

    stems = iter_task_stems(tasks_dir)
    hint = f" Known names: {', '.join(stems)}." if stems else ""
    raise SystemExit(f"Error: task {task_name!r} not found under {tasks_dir}.{hint}")


_CLI_EPILOG = """
How execution is chosen:
  task TASK_NAME       Run a single task from config/tasks or a direct YAML path.
  --list-tasks         Print task stems under config/tasks; no browser, no LLM.

Dedicated subcommands handled before the parser:
  llm-list …           LLM proxy model listing.
  llmtest …            LLM proxy full test.

Defaults when omitted:
  --config-dir         <directory containing main.py>/config
  --headless           From settings.yaml in that config dir
  --base-url           From settings.yaml / environment (.env)
  --trace              Off unless you pass --trace (optional DIR defaults to ./artifacts/traces)
""".strip()


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config-dir",
        default=None,
        help="Path to config directory (default: <immiclaw-test>/config)",
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
            "Record Playwright trace for the task (zip under DIR; default: ./artifacts/traces). "
            "Inspect with: playwright show-trace <file.zip>"
        ),
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="LLM-driven Playwright web task runner",
        epilog=_CLI_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--list-tasks",
        action="store_true",
        help="Print task short names under config/tasks and exit",
    )
    _add_common_args(parser)

    subparsers = parser.add_subparsers(dest="command")
    task_parser = subparsers.add_parser("task", help="Run a task")
    task_parser.add_argument("task_name", nargs="?", metavar="TASK_NAME", help="Task name or YAML path")
    task_parser.add_argument("--file", dest="task_file", default=None, help="Path to task YAML")
    _add_common_args(task_parser)
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.list_tasks:
        return args
    if args.command != "task":
        parser.error("choose either --list-tasks or the 'task' subcommand")
    if not args.task_name and not args.task_file:
        parser.error("task requires TASK_NAME or --file")
    return args


def load_task_skills(task, cfg_root: Path):
    skills_dir = cfg_root / "skills"
    skills = load_skills(task.skills, skills_dir) if task.skills else []
    skills_prompt = assemble_skills_prompt(skills) if skills else ""
    return skills, skills_prompt


def _build_error_report(task: Task, reason: str, *, start_time: float) -> TaskReport:
    return TaskReport(
        task_name=task.name,
        result=TestResult.ERROR,
        reason=reason,
        elapsed_seconds=round(time.time() - start_time, 2),
    )


async def run_task_cmd(args: argparse.Namespace) -> int:
    _install_quiet_exception_handler()
    cfg_root = _effective_config_dir(args.config_dir)
    config_dir = Path(args.config_dir) if args.config_dir else None
    settings = load_settings(config_dir)

    if args.headless is not None:
        settings.browser.headless = args.headless == "true"
    if args.base_url:
        settings.base_url = args.base_url

    task_path = resolve_task_path(args.task_name, args.task_file, cfg_root)

    if not settings.llm.api_key:
        print("Error: LLM_API_KEY not set. Create a .env file or set the environment variable.")
        return 1

    task = load_task(task_path)
    skills, skills_prompt = load_task_skills(task, cfg_root)

    run_dir = new_run_log_dir()
    out_dir = task_output_dir(run_dir, task.name)
    print(f"Run log: {run_dir.resolve()}")
    print(f"  Task output: {out_dir.resolve()}")

    trace_file: Path | None = None
    if args.trace:
        trace_dir = Path(args.trace)
        trace_file = trace_dir / f"{task.name}-{datetime.now():%Y%m%d-%H%M%S}.zip"

    print(f"Running task: {task.name}")
    print(f"  Target: {task.start_url.format(base_url=settings.base_url)}")
    print(f"  Model:  {settings.llm.model}")
    print(f"  Goal:   {task.goal[:80]}...")
    print()

    started_at = time.time()
    try:
        async with create_browser(settings.browser, trace_path=trace_file) as (_, _, page):
            report = await run_task(
                task=task,
                page=page,
                backend=create_backend(settings.llm),
                settings=settings,
                skills=skills,
                skills_prompt=skills_prompt,
                output_dir=out_dir,
            )
    except Exception as exc:
        report = _build_error_report(
            task,
            f"{type(exc).__name__}: {exc}",
            start_time=started_at,
        )

    print_report(report)

    report_path = save_report(report, output_dir=out_dir)
    print(f"Report saved to: {report_path}")
    if trace_file is not None:
        print(f"Playwright trace: {trace_file.resolve()}")

    return 0 if report.result.value == "pass" else 1


def _install_quiet_exception_handler() -> None:
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


def cmd_list_tasks(args: argparse.Namespace) -> int:
    cfg_root = _effective_config_dir(args.config_dir)
    tasks_dir = cfg_root / "tasks"
    if not tasks_dir.is_dir():
        print(f"Error: tasks directory not found: {tasks_dir}", file=sys.stderr)
        return 1
    for stem in iter_task_stems(tasks_dir):
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

    if not argv:
        build_arg_parser().print_help()
        sys.exit(0)

    args = parse_args(argv)
    if args.list_tasks:
        sys.exit(cmd_list_tasks(args))

    exit_code = asyncio.run(run_task_cmd(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
