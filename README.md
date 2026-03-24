# immiclaw-test

基于 LLM 与 Playwright 的 Web 场景测试工具。

## 环境要求

- **Python**：3.13 及以上（见 `pyproject.toml` 中 `requires-python`）
- **包管理**：推荐使用 [uv](https://docs.astral.sh/uv/)（仓库含 `uv.lock`）
- **被测站点**：默认假定前端在 `http://localhost:3000`（可在配置或环境中修改）

## 环境初始化

在仓库根目录 `immiclaw-test/` 下执行下列步骤。

### 1–2. 依赖与 Playwright（推荐）

已安装 [uv](https://docs.astral.sh/uv/) 时，一步完成原步骤 1、2：

```bash
cd immiclaw-test
make install
```

`playwright install-deps` 在 **Linux / WSL** 上常需 root。若最后一步报错，可在项目根目录执行：`sudo uv run playwright install-deps chromium`（需本机已安装 `uv` 且 root 环境能找到该命令）。

#### 手动执行（与 `make install` 等价）

```bash
cd immiclaw-test
uv venv
uv sync --extra dev
uv run playwright install chromium
uv run playwright install-deps chromium
```

不使用 uv 时，可用任意方式创建虚拟环境后安装：

```bash
cd immiclaw-test
python3.13 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
playwright install-deps chromium
```

### 3. 配置环境变量（`.env`）

```bash
cp .env.example .env
```

编辑 `.env`，至少设置：

| 变量 | 说明 |
|------|------|
| `LLM_API_KEY` | 大模型 API 密钥（必填；主流程会读取并覆盖 `config/settings.yaml` 中的密钥配置） |

可选覆盖（与 `.env.example` 中注释一致）：

- `LLM_MODEL`、`LLM_BASE_URL`：模型与 API 地址
- `BASE_URL`：被测站点根地址（覆盖 `settings.yaml` 的 `base_url`）

用于 `main.py llm-list` / `llmtest` 等子命令时，还可配置 `PROXY_HOST`、`PROVIDERS_YAML` 及各厂商 `*_API_KEY`；详见 `.env.example`。

**注意**：配置加载使用 `python-dotenv` 的默认行为，会在**当前工作目录**查找 `.env`。请在本项目根目录下运行 `uv run python main.py ...` 等命令，或将 `.env` 放在你运行命令时的当前目录。

### 4.（可选）调整默认配置

编辑 `config/settings.yaml`：如 `base_url`、浏览器 `headless`、视口、以及 `llm` 默认模型等。环境变量优先级高于 YAML 中的对应项（见 `immiclaw_test/config.py` 中 `load_settings`）。

## 初始化后自检

```bash
uv run python main.py --list
```

应列出 `config/scenarios/` 下的场景短名。运行单个场景示例：

```bash
uv run python main.py <场景短名>
```

若提示 `LLM_API_KEY not set`，说明 `.env` 未生效（检查是否在项目根目录执行、或变量是否已导出）。

## 常用命令摘要

| 命令 | 作用 |
|------|------|
| `make install` | 初始化虚拟环境、同步依赖、安装 Chromium 与系统库 |
| `uv run python main.py --list` | 列出内置场景名 |
| `uv run python main.py <场景名>` | 跑单个场景 |
| `uv run python main.py --all` | 并行跑 `config/scenarios` 下全部 YAML |
| `uv run pytest` | 运行单元/集成测试（需 `--extra dev`） |

子命令：`llm-list`、`llmtest`（见 `main.py`）用于 LLM 提供方探测与代理相关流程，依赖 `.env.example` 中扩展变量。

## 目录速览

- `config/settings.yaml`：默认设置
- `config/scenarios/*.yaml`：场景定义
- `artifacts/`：运行输出（含 `runs/` 等，勿提交敏感内容）
