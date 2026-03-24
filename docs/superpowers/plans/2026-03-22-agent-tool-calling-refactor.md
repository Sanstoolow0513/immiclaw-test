# Agent Tool Calling Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor from exec-based code execution to secure Agent + OpenAI-style Tool Calling.

**Architecture:** Replace `executor.py`'s `exec()` with typed tool runtime. Add provider-abstract LLM backend. Introduce explicit session memory.

**Tech Stack:** Python 3.11+, OpenAI SDK, Playwright, Pydantic v2, pytest

**Spec:** `docs/superpowers/specs/2026-03-22-agent-tool-calling-refactor-design.md`

---

## File Structure

### New Files

```
immiclaw_test/
├── agent_runner.py        # Tool-calling agent loop
├── agent_context.py       # Context building, memory management
├── llm_backends.py        # Backend protocol, OpenAI/Fake implementations
├── tool_models.py         # Pydantic tool input/output models
├── tool_runtime.py        # Tool dispatch, validation, execution
├── playwright_tools.py    # Playwright tool handlers
└── locator_resolver.py    # LocatorRef → Playwright locator

tests/
├── conftest.py            # Shared fixtures
├── unit/
│   ├── test_llm_backends.py
│   ├── test_tool_models.py
│   ├── test_locator_resolver.py
│   └── test_tool_runtime.py
└── integration/
    └── test_agent_runner_tool_mode.py
```

### Modified Files

```
immiclaw_test/models.py    # Add AgentMode enum
main.py                    # Wire new runner
pyproject.toml             # Lower Python req, add test deps
```

---

## Parallel Task Breakdown

```
Phase 1 (Sequential)
├── Task 1.1: Test infrastructure
└── Task 1.2: Characterization tests

Phase 2 (Parallel after Phase 1)
├── Task 2.1: Backend contract ─────────────┐
├── Task 2.2: Tool models ──────────────────┼── Can run in parallel
└── Task 2.3: Locator resolver ─────────────┘

Phase 3 (Sequential after Phase 2)
├── Task 3.1: Tool runtime + handlers
├── Task 3.2: Agent context builder
└── Task 3.3: Agent runner loop

Phase 4 (Sequential)
├── Task 4.1: Add mode config
├── Task 4.2: Wire into main.py
└── Task 4.3: Integration tests

Phase 5 (Sequential)
└── Task 5.1: Make tools default, cleanup
```

---

## Phase 1: Foundation

### Task 1.1: Add Test Infrastructure

**Files:** `tests/__init__.py`, `tests/conftest.py`, `tests/unit/__init__.py`, `pyproject.toml`

- [ ] Add pytest to pyproject.toml:
```toml
[project.optional-dependencies]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] Create `tests/conftest.py` with fixtures: `sample_settings`, `sample_scenario`, `mock_page`

- [ ] Run: `uv sync --extra dev && pytest --collect-only`

- [ ] Commit: `test: add pytest infrastructure`

---

### Task 1.2: Add Characterization Tests

**Files:** `tests/unit/test_llm_parsing.py`, `tests/unit/test_executor_behavior.py`

- [ ] Test `parse_llm_response()` for: continue, final_pass, final_fail, markdown fences

- [ ] Test `execute_code()` for: simple code, output capture, test_data injection, errors, report_result, step_state persistence

- [ ] Commit: `test: add characterization tests for LLM parsing and executor`

---

## Phase 2: Core Models (Parallel)

### Task 2.1: Define LLM Backend Contract

**Files:** `immiclaw_test/llm_backends.py`, `tests/unit/test_llm_backends.py`

- [ ] Create `ToolCall` dataclass with `id`, `name`, `arguments`, `parse_arguments()`

- [ ] Create `AssistantTurn` dataclass with `content`, `tool_calls`, `finish_reason`, `is_terminal`, `has_tool_calls`

- [ ] Create `LLMBackend` Protocol with `next_turn(messages, tools)`

- [ ] Create `OpenAIChatBackend` implementing the protocol

- [ ] Create `FakeBackend` for testing with `add_response()` method

- [ ] Commit: `feat: add normalized llm backend contract`

---

### Task 2.2: Define Tool Input Models

**Files:** `immiclaw_test/tool_models.py`, `tests/unit/test_tool_models.py`

- [ ] Create `LocatorRef` model with kind, value, name, exact, nth, level

- [ ] Create navigation inputs: `NavigateInput`, `ReloadInput`, `GoBackInput`

- [ ] Create action inputs: `ClickInput`, `FillInput`, `TypeInput`, `PressInput`, `HoverInput`, `CheckInput`, `ScrollInput`

- [ ] Create waiting inputs: `WaitForSelectorInput`, `WaitForLoadStateInput`, `WaitForTimeoutInput`

- [ ] Create reading inputs: `ReadTextInput`, `ReadValueInput`, `GetPageInfoInput`, `IsVisibleInput`

- [ ] Create assertion inputs: `AssertVisibleInput`, `AssertTextInput`, `AssertTitleInput`, `AssertUrlInput`

- [ ] Create evidence inputs: `ScreenshotInput`, `RememberInput`

- [ ] Create `ReportResultInput` with passed, reason, evidence_points

- [ ] Create `ToolResult` model with ok, data, error, retryable, hint

- [ ] Create `to_openai_tool_schema()` function

- [ ] Create `register_tool()` and `get_all_tool_schemas()`

- [ ] Commit: `feat: add typed tool input models`

---

### Task 2.3: Implement Locator Resolver

**Files:** `immiclaw_test/locator_resolver.py`, `tests/unit/test_locator_resolver.py`

- [ ] Create `resolve_locator(page, loc)` function

- [ ] Map `kind="css"` → `page.locator(value)`

- [ ] Map `kind="role"` → `page.get_by_role(value, name=..., level=...)`

- [ ] Map `kind="text"` → `page.get_by_text(value, exact=...)`

- [ ] Map `kind="placeholder"` → `page.get_by_placeholder(value, exact=...)`

- [ ] Map `kind="test_id"` → `page.get_by_test_id(value)`

- [ ] Map `kind="label"` → `page.get_by_label(value, exact=...)`

- [ ] Apply `.nth(n)` if specified

- [ ] Commit: `feat: add locator resolver`

---

## Phase 3: Runtime & Agent

### Task 3.1: Implement Tool Runtime

**Files:** `immiclaw_test/tool_runtime.py`, `immiclaw_test/playwright_tools.py`, `tests/unit/test_tool_runtime.py`

- [ ] Create `SessionMemory` dataclass with values, last_error, failure_streak, final_result

- [ ] Create `ToolRuntime` class with `execute(tool_name, arguments)` method

- [ ] Implement handler dispatch with validation

- [ ] Create handlers in `playwright_tools.py`:
  - `handle_navigate`, `handle_reload_page`, `handle_go_back`
  - `handle_click`, `handle_fill`, `handle_type_text`, `handle_press`
  - `handle_hover`, `handle_check`, `handle_scroll`
  - `handle_wait_for`, `handle_wait_for_load_state`, `handle_wait_for_timeout`
  - `handle_read_text`, `handle_get_page_info`, `handle_is_visible`
  - `handle_assert_visible`, `handle_assert_text`
  - `handle_remember`, `handle_report_result`

- [ ] `handle_report_result` sets `memory.final_result` and returns `is_final: true`

- [ ] Commit: `feat: add playwright tool runtime and handlers`

---

### Task 3.2: Implement Agent Context Builder

**Files:** `immiclaw_test/agent_context.py`

- [ ] Create `build_system_prompt(scenario)` using scenario goal/assertions/test_data

- [ ] Create `build_turn_messages(system_prompt, observation, memory, transcript)`:
  1. System prompt
  2. Current observation
  3. Memory values (if any)
  4. Trimmed transcript (last 10)

- [ ] Create `build_tool_result_message(tool_call_id, result)` for tool role messages

- [ ] Commit: `feat: add agent context builder`

---

### Task 3.3: Implement Agent Runner

**Files:** `immiclaw_test/agent_runner.py`, `tests/integration/test_agent_runner_tool_mode.py`

- [ ] Create `run_scenario_with_tools(scenario, page, backend, settings)`:
  ```
  for each step:
    1. Observe page state
    2. Build messages
    3. Call backend.next_turn(messages, tools)
    4. If terminal: return FAIL (unexpected)
    5. For each tool_call:
       - Execute via runtime
       - Append tool result to transcript
       - If is_final: return TestReport
    6. Check failure_streak >= 3: return FAIL
  ```

- [ ] Handle `report_result` specially: extract passed/reason from memory.final_result

- [ ] Write integration test with FakeBackend:
  - Test simple click then report pass
  - Test report fail with evidence
  - Test memory persists across steps

- [ ] Commit: `feat: add tool-calling agent runner`

---

## Phase 4: Integration

### Task 4.1: Add Agent Mode Configuration

**Files:** `immiclaw_test/models.py`

- [ ] Add `AgentMode` enum: `EXEC`, `TOOLS`, `HYBRID`

- [ ] Add `mode: AgentMode = AgentMode.TOOLS` to `AgentConfig`

- [ ] Commit: `feat: add agent mode configuration`

---

### Task 4.2: Wire Agent Runner into Main

**Files:** `main.py`

- [ ] Import `run_scenario_with_tools` and `create_backend`

- [ ] In `run()` function, dispatch based on `settings.agent.mode`:
  - `TOOLS` → use `run_scenario_with_tools`
  - `EXEC` → use existing `run_scenario`
  - `HYBRID` → try tools first, fallback to exec

- [ ] Commit: `feat: wire tool-calling runner into CLI`

---

### Task 4.3: Integration Tests

**Files:** `tests/integration/test_hybrid_mode.py`

- [ ] Test hybrid mode falls back to exec when tools fail

- [ ] Test mode configuration is respected

- [ ] Commit: `test: add hybrid mode integration tests`

---

## Phase 5: Cutover

### Task 5.1: Make Tools Default

**Files:** `config/settings.yaml`, `pyproject.toml`

- [ ] Set `mode: "tools"` as default in settings.yaml

- [ ] Lower `requires-python` from `>=3.13` to `>=3.11`

- [ ] Update README with new architecture

- [ ] Commit: `chore: make tool mode default, lower python requirement`

---

### Task 5.2: Remove Legacy (After Stabilization)

**Files:** `immiclaw_test/executor.py`, `immiclaw_test/llm.py`

- [ ] Remove `executor.py`

- [ ] Remove legacy JSON parsing from `llm.py` (keep client creation)

- [ ] Remove hybrid mode support

- [ ] Commit: `refactor: remove legacy exec path`

---

## Atomic Commit Strategy

| # | Commit Message |
|---|----------------|
| 1 | `test: add pytest infrastructure and shared fixtures` |
| 2 | `test: add characterization tests for LLM parsing and executor` |
| 3 | `feat: add normalized llm backend contract with OpenAI and fake` |
| 4 | `feat: add typed tool input models with OpenAI schema generation` |
| 5 | `feat: add locator resolver to convert LocatorRef to Playwright locators` |
| 6 | `feat: add playwright tool runtime and handlers` |
| 7 | `feat: add agent context builder for tool-calling mode` |
| 8 | `feat: add tool-calling agent runner with integration tests` |
| 9 | `feat: add agent mode configuration (exec/tools/hybrid)` |
| 10 | `feat: wire tool-calling runner into CLI` |
| 11 | `test: add hybrid mode integration tests` |
| 12 | `chore: make tool mode default, lower python requirement to 3.11` |
| 13 | `refactor: remove legacy exec path` |

---

## Success Criteria

### Phase 2 Complete When
- [ ] All unit tests pass for backend contract
- [ ] All unit tests pass for tool models
- [ ] All unit tests pass for locator resolver

### Phase 3 Complete When
- [ ] Tool runtime executes all handlers
- [ ] Agent runner completes test scenarios with FakeBackend
- [ ] Memory persists across tool calls

### Phase 4 Complete When
- [ ] CLI dispatches based on mode
- [ ] Hybrid mode falls back correctly
- [ ] Real scenarios run in tool mode

### Phase 5 Complete When
- [ ] Tool mode is default
- [ ] Legacy exec removed
- [ ] All tests pass
