# YAML Flow Assembly System Design

> immiclaw-test 自主测试 Agent 与 Skill/场景引导体系

## 问题

当前 immiclaw-test 的每个 scenario YAML 是原子执行单元：单起点、单目标、由独立的 agent 循环驱动至 pass/fail。真实用户旅程是非线性的——登录后可能走注册引导，也可能进入已有案件工作流。现有的 journey 场景把整条路径塞进一个超长 YAML，不灵活、不可复用。

## 方案概述

将测试从"系统驱动的逐场景执行"转变为"LLM 自主探索 + 场景验证"：

- **一个连续的 agent 会话**——LLM 全权决定测试路径，不受预定义图约束
- **场景 YAML 变成验证工具**——LLM 操作到某个阶段后主动调用验证，系统读取场景 YAML 校验 assertions
- **Skill YAML 提供操作与策略引导**——注入 LLM 的 prompt，教它怎么做和怎么判断
- **Reflect 机制**——已完成测试列表实时反馈给 LLM，引导它探索未覆盖的路径
- **Flow YAML 是会话配置**——不是执行图，而是"可用场景目录 + skills + 预设提示词"

现有 scenario YAML 零改动。单场景模式 `immiclaw-test qmr-login` 仍然独立工作。

## 文件体系

```
immiclaw-test/config/
├── settings.yaml              # 不变
├── scenarios/                 # 不变，原子场景（现作为验证规范）
│   ├── qmr-login.yaml
│   ├── qmr-smoke-register.yaml
│   └── ...
├── flows/                     # 新增：测试会话配置
│   ├── new-user-journey.yaml
│   ├── daily-workflow.yaml
│   └── ...
└── skills/                    # 新增：agent 引导
    ├── operation/             # 操作级 skill
    │   ├── login.yaml
    │   ├── upload-file.yaml
    │   └── ...
    └── strategy/              # 策略级 skill
        ├── error-handling.yaml
        ├── wait-ai-response.yaml
        └── ...
```

三种 YAML 的角色：

| 类型 | 角色 | 说明 |
|------|------|------|
| Scenario | 验证规范 | LLM 主动调用时，系统用其 `assertions` 校验当前页面状态 |
| Skill | 知识注入 | 操作指南和策略知识，拼入 system prompt |
| Flow | 会话配置 | 可用场景目录 + skills + 预设提示词 + 共享 test_data |

## YAML Schema

### Skill YAML（不变）

```yaml
name: login
type: operation                    # operation | strategy
description: "登录操作指南"
applies_to:                        # 可选：适用的场景名，不写则通用
  - qmr-login
  - qmr-journey-case-workflow
prompt: |
  当需要执行登录操作时，按以下步骤操作：
  1. 找到占位符为「请输入账号」的输入框，填入 test_data 中的 account/email
  2. 找到「请输入密码」的输入框，填入 password
  3. 点击「登录」按钮
  4. 等待 URL 离开 /login，预期跳转到 /cases
  5. 若出现红色错误提示，记录错误内容并判断是否需要终止
```

```yaml
name: wait-ai-response
type: strategy
description: "等待 AI agent 回复的策略"
prompt: |
  当页面发送消息后等待 AI 回复时：
  - 不要立刻判断为失败，AI 回复可能需要 60-120 秒
  - 每隔 5-10 秒重新观察页面，检查是否有新的助手消息出现
  - 如果超过 120 秒仍无回复，才判断为超时
  - 等待期间不要执行其他操作，避免干扰
```

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `name` | 是 | string | 唯一标识 |
| `type` | 是 | `operation` \| `strategy` | 操作级或策略级 |
| `description` | 是 | string | 人类可读简述 |
| `applies_to` | 否 | list[string] | 适用的场景名；不写则通用 |
| `prompt` | 是 | string | 注入 LLM system prompt 的内容 |

### Flow YAML（重新设计）

Flow 不再是场景间的执行图，而是测试会话的配置文件：

```yaml
name: new-user-journey
description: "全新用户从注册到首次对话的完整旅程"

preset: |
  你是 ImmiClaw Web 应用的测试 Agent。你的任务是模拟真实用户，
  自主探索应用并验证功能正确性。
  你拥有完全的决策权——自行判断接下来该测什么、怎么测。
  当你认为某个功能点已经操作到位时，调用 verify_scenario 来校验。

skills:
  - login
  - upload-file
  - fill-questionnaire
  - wait-ai-response
  - error-handling

scenarios:                         # 可用场景目录（不是执行图）
  - qmr-smoke-register
  - qmr-smoke-case-create
  - qmr-smoke-chat-basic
  - qmr-smoke-chat-interaction
  - qmr-smoke-file-upload

start_url: "{base_url}/register"

context:                           # 共享 test_data
  new_user:
    email: "flow-{timestamp}@test.com"
    password: "FlowPass123!"
  questionnaire:
    name: "李四"
    birth_date: "1988-06-20"
    employer: "某研究院"
    position: "首席研究员"

max_steps: 100                     # 整个会话总步数
timeout_seconds: 600               # 整个会话总超时
```

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `name` | 是 | string | 会话唯一标识 |
| `description` | 是 | string | 人类可读描述 |
| `preset` | 是 | string | 测试预设提示词，定义 agent 的角色与行为准则 |
| `skills` | 否 | list[string] | 加载的 skill name 列表 |
| `scenarios` | 是 | list[string] | 可用场景名目录（LLM 可验证的场景范围） |
| `start_url` | 是 | string | 会话起始 URL |
| `context` | 否 | dict | 共享 test_data，所有场景验证时可用 |
| `max_steps` | 否 | int | 总步数上限，默认 100 |
| `timeout_seconds` | 否 | int | 总超时，默认 600 |

### Scenario YAML（不变）

现有 schema 保持不变：`name`, `description`, `target_url`, `goal`, `assertions`, `max_steps`, `timeout_seconds`, `test_data`。

在 flow 模式下，scenario 的 `goal` 和 `assertions` 被 `verify_scenario` 工具用于校验，`target_url` 不再用于导航（LLM 自己已经在操作页面）。

## 运行时架构

### 核心流程

```
CLI: immiclaw-test --flow new-user-journey
         │
         ▼
  加载 Flow YAML → 加载 Skills → 预加载所有引用的 Scenario YAMLs
         │
         ▼
  构建 System Prompt:
    · preset（测试预设）
    · skills prompt（操作 + 策略引导）
    · 场景目录（每个场景的 name + description + goal 摘要）
    · 工具说明（verify_scenario / list_scenarios / complete_flow）
    · test_data（共享上下文）
         │
         ▼
  打开浏览器，导航到 start_url
         │
         ▼
  ┌─► Agent 循环（单一连续会话）
  │   │
  │   ├─ 观察页面状态（accessibility tree）
  │   ├─ LLM 自主决策：
  │   │   · 执行操作代码（与当前 agent 循环一致）
  │   │   · 调用 verify_scenario(name) 校验某个场景
  │   │   · 调用 complete_flow() 结束会话
  │   │
  │   ├─ 如果调用了 verify_scenario:
  │   │   · 加载场景 YAML 的 assertions
  │   │   · 对当前页面状态逐条校验
  │   │   · 返回 pass/fail + 详情
  │   │   · 更新已完成列表
  │   │   · 注入 Reflect 消息
  │   │
  │   └─ 继续循环
  └───────┘
         │
         ▼
  生成 FlowReport
```

### LLM 可用的工具

在 flow 模式的 agent 循环中，LLM 除了生成操作代码外，还可以调用以下工具：

#### `verify_scenario(name: str) → VerifyResult`

读取指定场景的 YAML，用其 `assertions` 对当前页面状态做校验。

- 输入：场景名（必须在 flow 的 `scenarios` 列表中）
- 行为：
  1. 加载场景 YAML 的 `goal` 和 `assertions`
  2. 获取当前页面状态（URL、accessibility tree）
  3. 用 LLM 逐条评估每个 assertion 是否满足（基于页面状态）
  4. 返回 `VerifyResult(passed: bool, results: list[AssertionResult], reason: str)`
  5. 将结果记入已完成列表
- 同一场景可多次验证（例如修复后重试），以最后一次结果为准

#### `list_scenarios() → ScenarioStatus`

返回所有可用场景的当前状态。

```json
{
  "verified": [
    {"name": "qmr-login", "result": "pass", "step": 5},
    {"name": "qmr-smoke-register", "result": "fail", "step": 12}
  ],
  "unverified": [
    {"name": "qmr-smoke-case-create", "description": "在案件列表页新建案件..."},
    {"name": "qmr-smoke-file-upload", "description": "上传文件并验证..."}
  ]
}
```

状态定义：
- `verified`：已调用过 `verify_scenario` 的场景（含 pass 和 fail），以最后一次结果为准
- `unverified`：从未调用过 `verify_scenario` 的场景

#### `complete_flow(reason: str) → None`

LLM 主动声明 flow 结束。

### Reflect 机制

每次 `verify_scenario` 完成后，系统向 LLM 注入一条 reflect 消息：

```
--- 测试进度更新 ---
已完成的测试：
✓ qmr-smoke-register: pass (步骤 8，注册成功进入 /cases)
✗ qmr-smoke-case-create: fail (步骤 15，未找到新建按钮)

尚未覆盖的场景：
· qmr-smoke-chat-basic: 在工作区发送消息并验证回复
· qmr-smoke-file-upload: 上传文件并验证文件列表
· qmr-smoke-chat-interaction: 多轮对话与追问

请继续探索未覆盖的功能。对于失败的场景，如果当前页面状态允许，可以尝试重新操作后再次验证。
---
```

Reflect 消息的作用：
- 告知 LLM 已完成了什么（避免重复）
- 展示未覆盖的场景（引导探索方向，但不强制）
- 对失败场景给出重试建议
- **不限制 LLM 的选择**——LLM 可以忽略建议，按自己的判断行事

### System Prompt 结构

```
{preset}

## 你的操作能力

你可以生成 Python 代码操作 Playwright page 对象来与页面交互。

## 操作指南（Skills）

### 操作级
{operation skills prompt}

### 策略级
{strategy skills prompt}

## 可用测试场景

以下是你可以验证的测试场景。当你认为某个场景的功能点已经操作到位时，
调用 verify_scenario(name) 来校验：

1. qmr-smoke-register — 注册新用户并验证成功
2. qmr-smoke-case-create — 在案件列表页新建案件
3. ...

## 可用工具

- verify_scenario(name) — 读取场景定义，校验当前页面是否满足断言
- list_scenarios() — 查看所有场景的完成状态
- complete_flow(reason) — 结束测试会话

## 测试数据

{context as JSON}
```

### Flow 模式的 LLM 协议

Flow 模式不复用 `llm.py` 的 `parse_llm_response()`，而是定义自己的响应格式。LLM 每步返回一个 JSON：

```json
{
  "thinking": "分析当前页面状态...",
  "action": "code",
  "code": "await page.click('#submit')"
}
```

`action` 字段的可选值：

| action | 含义 | 必须伴随的字段 |
|--------|------|----------------|
| `code` | 执行 Playwright 操作代码 | `code: str` |
| `verify` | 调用 verify_scenario 校验 | `scenario: str`（场景名） |
| `list` | 查看场景完成状态 | 无 |
| `complete` | 结束 flow | `reason: str` |

每步只允许一个 action。如果 LLM 想先执行代码再校验，需要分两步。

`flow_runner.py` 中实现独立的 `parse_flow_response()` 函数处理此格式。与 `llm.py` 的 `parse_llm_response()` 完全独立，互不影响。

### `report_result` 在 Flow 模式中的处理

现有 `executor.py` 中的 `report_result()` 函数在 flow 模式下**被禁用**——`execute_code()` 的命名空间中不注入 `report_result`。Flow 模式下场景结束由 `verify` action 和 `complete` action 控制，避免双通道结束语义冲突。

### Skill 注入规则

1. 收集 flow 中声明的所有 skill
2. 过滤：如果 skill 有 `applies_to` 字段，**在 system prompt 中仍然注入**（因为单一连续会话中可能走到任何场景），但在 prompt 中标注其适用场景
3. 无 `applies_to` 的通用 skill 始终注入
4. 按 `operation` 在前、`strategy` 在后的顺序组织

### 与现有代码的集成

| 文件 | 改动 |
|------|------|
| `flow_runner.py`（新） | 连续 agent 会话循环、reflect 注入、工具调度、`parse_flow_response()` |
| `flow_verifier.py`（新） | `verify_scenario` 的实现：加载场景 YAML、获取页面状态、LLM 评估 assertions |
| `skill_loader.py`（新） | 加载 skill YAML，生成 prompt 片段 |
| `flow_config.py`（新） | `load_flow()`、`load_skill()`、占位符展开（`{timestamp}`/`{base_url}`）、静态校验 |
| `flow_models.py`（新） | `Flow`、`Skill`、`VerifyResult`、`FlowStepRecord`、`FlowReport` 数据模型 |
| `main.py`（扩展） | 增加 `--flow` 和 `--list-flows` CLI 参数 |
| `reporter.py`（扩展） | 增加 `print_flow_report()` 和 `save_flow_report()` |
| `agent.py`（不动） | 单场景模式不受影响 |
| `llm.py`（不动） | 单场景模式不受影响 |
| `config.py`（不动） | 单场景的 `load_scenario` / `load_settings` 不受影响 |

关键设计点：flow 模式的 agent 循环是 **`flow_runner.py` 中的新实现**，不复用 `agent.py` 的 `run_scenario()`。两者共享底层的 `executor.py`（执行代码）、`observer.py`（观察页面）、`browser.py`（浏览器管理），但 prompt 构建和循环控制完全独立。

`flow_config.py` 负责 flow 和 skill 的加载与校验，与 `config.py`（单场景加载）职责分离。Flow 的 `context` 占位符展开在 `flow_config.load_flow()` 中完成，不经过 `config.load_scenario()`。

### 浏览器 Session

- 整个 flow 共享一个 browser context 和 page
- `start_url` 仅在会话开始时导航一次
- 后续导航完全由 LLM 通过生成的代码控制

### `verify_scenario` 的 Assertion 评估

`verify_scenario` 内部调用一次 LLM 来评估 assertions：

```
请根据当前页面状态，逐条判断以下断言是否满足：

场景：{scenario.name}
目标：{scenario.goal}

当前页面 URL: {page.url}
页面状态: {accessibility tree}

断言列表：
1. {assertion_1}
2. {assertion_2}
...

请以 JSON 回复：
{
  "passed": true/false,
  "assertions": [
    {"assertion": "...", "satisfied": true/false, "evidence": "..."},
    ...
  ],
  "reason": "总体判断理由"
}
```

这是一次独立的 LLM 调用，不影响主 agent 循环的对话上下文。

## 错误处理

### Flow 级

| 情况 | 处理 |
|------|------|
| 超 `max_steps` 或 `timeout_seconds` | 终止会话，FlowReport `result` 为 `timeout` |
| LLM 持续生成无效代码（连续 5 步失败） | 注入提示："连续多步失败，请重新评估当前状态" |
| LLM 调用不存在的场景名 | 返回错误信息 + 可用场景列表，不终止会话 |
| LLM 无法解析返回 | 要求重新回复，最多重试 2 次 |

### Verify 级

| 情况 | 处理 |
|------|------|
| 场景验证 fail | 记录 fail，reflect 中提示可重试 |
| 同一场景多次验证 | 以最后一次结果为准 |
| 验证时 LLM 评估调用失败 | 返回 error 状态，不记为 pass 或 fail；不影响其他场景的 result 聚合（仅该条 verify 标记 error） |

### FlowReport

```python
class VerifyResult(BaseModel):
    scenario_name: str
    passed: bool
    assertions: list[AssertionResult]
    reason: str
    step_number: int                    # 在第几步触发的验证

class AssertionResult(BaseModel):
    assertion: str
    satisfied: bool
    evidence: str

class FlowStepRecord(BaseModel):
    step_number: int
    action: str                         # "code" | "verify" | "list" | "complete"
    thinking: str = ""
    code: str = ""                      # action=code 时
    scenario: str = ""                  # action=verify 时
    output: str = ""
    error: str | None = None
    success: bool = True
    page_url: str | None = None

class FlowReport(BaseModel):
    flow_name: str
    result: TestResult                  # 见下方取值规则
    verify_results: list[VerifyResult]  # 所有验证结果（含重试），以最后一次为准
    steps: list[FlowStepRecord]         # 完整步骤记录
    scenarios_verified: list[str]       # 已验证场景名
    scenarios_unverified: list[str]     # 未验证场景名
    total_steps: int
    elapsed_seconds: float
```

> 值与 `models.py` 中 `TestResult` 枚举保持一致（小写字符串）。

`FlowReport.result` 取值规则：

| 情况 | result |
|------|--------|
| 至少验证了一个场景，且所有已验证场景最终结果均为 pass | `pass` |
| 任一场景最终结果为 fail | `fail` |
| 超时或超步数 | `timeout` |
| 未验证任何场景即结束（含正常 `complete` 和异常） | `error` |

优先级：`fail` > `timeout` > `error` > `pass`。

**未被验证的场景不影响 result**——如果 LLM 正常调用 `complete` 结束 flow，且已验证的场景全部 pass，即使仍有场景未覆盖，result 仍为 `pass`。这符合"LLM 全权决策"的设计原则——它认为测够了就可以结束。未覆盖的场景信息记录在 `FlowReport` 中供人类审查。

## 静态校验

Flow YAML 加载时进行校验：

1. `scenarios` 中的每个场景名必须在 `config/scenarios/` 下有对应 YAML 文件
2. `skills` 中的每个 skill 名必须在 `config/skills/`（`operation/` 和 `strategy/` 子目录均搜索）下有对应 YAML 文件
3. `start_url` 必须包含 `{base_url}` 占位符或为绝对 URL
4. 校验失败时抛出明确错误，拒绝启动

## Context 规则

- Flow 级 `context` 中的占位符（`{timestamp}`、`{base_url}`）在 flow 启动时展开一次
- `context` 作为 test_data 注入 system prompt，LLM 在操作代码中可通过 `test_data` 变量访问
- `verify_scenario` 时，flow 的 `context` 与场景自带的 `test_data` 合并（场景优先级高），用于评估 assertions

## CLI 接口

```bash
# 现有用法不变
immiclaw-test qmr-login
immiclaw-test --all

# 新增 flow 模式
immiclaw-test --flow new-user-journey
immiclaw-test --flow daily-workflow --base-url http://example.com

# 列出可用 flows
immiclaw-test --list-flows
```

参数互斥规则：`--flow` 与 `SCENARIO`/`--all`/`--list` 互斥。

退出码：与单场景模式一致——`FlowReport.result == "pass"` 返回 0，其余返回 1。

报告落盘：flow 模式的报告写入 `artifacts/runs/<timestamp>/flow-<name>/`，包含 `flow-report.json`（FlowReport 序列化）和每次 verify 的详细结果。复用 `reporter.py` 的序列化逻辑。

## 适用范围

本设计引入独立的 flow agent 循环（`flow_runner.py`），不修改现有的 `agent.py`（exec 模式）和 `agent_runner.py`（tools 模式）。三者共享底层的 `executor.py`、`observer.py`、`browser.py`。

## 兼容性

`immiclaw-test qmr-login` 仍走原有 `run()` → `run_scenario()` 路径，不涉及 flow/skill 机制。两条路径独立，不互相影响。
