"""CLI entry point for the LLM-driven Playwright testing tool."""

import argparse
import asyncio
import sys
from pathlib import Path

from immiclaw_test.agent import run_scenario
from immiclaw_test.browser import create_browser
from immiclaw_test.config import load_scenario, load_settings
from immiclaw_test.reporter import print_report, save_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LLM-driven Playwright web testing tool",
    )
    parser.add_argument(
        "scenario",
        help="Path to the scenario YAML file",
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
    return parser.parse_args()


async def run(args: argparse.Namespace) -> int:
    config_dir = Path(args.config_dir) if args.config_dir else None
    settings = load_settings(config_dir)

    if args.headless is not None:
        settings.browser.headless = args.headless == "true"
    if args.base_url:
        settings.base_url = args.base_url

    if not settings.llm.api_key:
        print("Error: LLM_API_KEY not set. Create a .env file or set the environment variable.")
        return 1

    scenario = load_scenario(args.scenario)

    print(f"Running scenario: {scenario.name}")
    print(f"  Target: {scenario.target_url.format(base_url=settings.base_url)}")
    print(f"  Model:  {settings.llm.model}")
    print(f"  Goal:   {scenario.goal[:80]}...")
    print()

    async with create_browser(settings.browser) as (browser, context, page):
        report = await run_scenario(scenario, page, settings)

    print_report(report)

    report_path = save_report(report)
    print(f"Report saved to: {report_path}")

    return 0 if report.result.value == "pass" else 1


def main() -> None:
    args = parse_args()
    exit_code = asyncio.run(run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
