# Repository Guidelines

## Project Structure & Module Organization
Core Python code lives in `immiclaw_test/`. `main.py` is the CLI entrypoint and exposes `task` plus LLM proxy commands. YAML configuration is under `config/`: use `config/tasks/` for task files, `config/skills/` for reusable prompt fragments, and `config/settings.yaml` for local settings. Test fixtures and unit/integration coverage live in `tests/` and `tests/integration/`. Sample upload files are stored in `assets/files/`. Design notes and implementation plans belong in `docs/`.

## Build, Test, and Development Commands
Set up the environment with `uv sync --extra dev`, then run `uv pip install -e .` before testing so imports use the local workspace copy. Run a single task with `python main.py task qmr-login`, list available tasks with `python main.py --list-tasks`, and execute the suite with `python -m pytest tests/ -v`. Use `--ignore=tests/integration` for faster unit-only runs. If the package is installed, `immiclaw-test` and `llmtest` mirror the CLI entrypoints defined in `pyproject.toml`.

## Coding Style & Naming Conventions
Follow existing Python style: 4-space indentation, type hints on public functions, and short module docstrings where useful. Keep modules focused by domain (`task`, `llm_*`, `tool_*`, `*_runner`, `*_models`). Use `snake_case` for files, functions, variables, and YAML filenames such as `qmr-smoke-login.yaml`. Prefer explicit, descriptive names over abbreviations, and keep config keys aligned with the Pydantic models they feed.

## Testing Guidelines
Pytest is the test runner, with `pytest-asyncio` enabled via `asyncio_mode = "auto"`. Name tests `test_*.py` and keep fixtures in `tests/conftest.py` when shared across modules. Mark async tests with `@pytest.mark.asyncio` when needed. Add or update tests alongside behavior changes, especially for CLI parsing, task execution, and config loading paths.

## Commit & Pull Request Guidelines
Recent history follows conventional prefixes such as `feat:`, `docs(config):`, and `test:`. Keep commit subjects imperative and scoped when useful, for example `feat(flow): add trace output for parallel runs`. PRs should summarize behavior changes, note any config or environment requirements, link the relevant issue, and include sample CLI output or screenshots when user-visible reporting changes.

## Configuration & Runtime Notes
Use Python 3.13 or newer. Do not commit secrets; `LLM_API_KEY` should come from the environment or a local `.env` file. Runtime artifacts are written under `artifacts/runs/` and optional Playwright traces under `artifacts/traces/`.
