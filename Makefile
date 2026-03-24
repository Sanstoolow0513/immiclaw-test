# 环境初始化：Python 依赖 + Playwright 浏览器与系统依赖（对应 README 步骤 1、2）
.PHONY: install venv sync playwright

install: venv sync playwright

venv:
	uv venv

sync:
	uv sync --extra dev

playwright:
	uv run playwright install chromium
	uv run playwright install-deps chromium
