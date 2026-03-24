# Agent Tool Calling Refactor - Design Specification

**Goal:** Refactor the LLM-driven Playwright testing tool from exec-based code execution to a secure Agent + OpenAI-style Tool Calling architecture.

**Architecture:** Replace `executor.py`'s `exec()` with a typed tool runtime. Add a provider-abstract LLM backend interface. Introduce explicit session memory. Keep scenario format, observer, browser lifecycle, and reporting unchanged. Support a hybrid migration mode before removing the legacy path.

**Tech Stack:** Python 3.11+, OpenAI SDK, Playwright, Pydantic v2, pytest

---

## 1. High-Level Architecture Design

### Current Architecture (exec-based)

```
main.py (CLI)
    │
    ▼
agent.py:run_scenario()  ◄── Agent Loop
    │
    ├─► observer.py:get_page_state() ──► accessibility tree text
    │
    ├─► llm.py:create_client() + build_system_prompt()
    │       └─► client.chat.completions.create() [OpenAI SDK]
    │
    ├─► llm.py:parse_llm_response() ──► JSON {thinking, code, status, evidence, final}
    │
    └─► executor.py:execute_code()
            └─► compile(code, "<llm-generated>", "exec", PyCF_ALLOW_TOP_LEVEL_AWAIT)
            └─► eval(compiled, namespace)  ◄── THE EXEC-BASED CORE (RISKY)
```

### Target Architecture (tool-calling)

```
main.py (CLI)
    │
    ▼
agent_runner.py:run_scenario()  ◄── New Tool-Calling Agent Loop
    │
    ├─► observer.py:get_page_state() ──► accessibility tree (unchanged)
    │
    ├─► agent_context.py ──► Build messages with observation + memory + transcript
    │
    ├─► llm_backends.py:LLMBackend.next_turn(messages, tools)
    │       └─► Returns: AssistantTurn {content, tool_calls, finish_reason}
    │
    ├─► tool_runtime.py:ToolRuntime.execute(tool_name, args)
    │       ├─► Validate args via Pydantic
    │       ├─► Dispatch to playwright_tools.py handler
    │       └─► Return: ToolResult {ok, data, error, retryable, hint}
    │
    └─► agent_context.py:SessionMemory ──► Persist values across steps
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Loop execution | One tool call per LLM turn | Simpler state management, easier debugging |
| Tool schema | Pydantic models → OpenAI schemas | Type safety, validation, auto-documentation |
| Context management | Rolling transcript + JSON memory | Simple, explicit, no hidden state |
| Backend abstraction | Protocol-based with OpenAI SDK | Easy to swap providers later |
| Migration path | Hybrid mode with config flag | Safe transition with rollback capability |

---

## 2. Tool Schema Definitions

### 2.1 Locator Reference Model

All tools that target elements use a unified `LocatorRef` model:

```python
class LocatorRef(BaseModel):
    """Reference to a page element using Playwright locator strategies."""
    kind: Literal["css", "role", "text", "placeholder", "test_id", "label"]
    value: str                          # The selector/text/role value
    name: str | None = None             # For role locators: accessible name
    exact: bool = False                 # For text/label: exact match
    nth: int | None = None              # Select nth match (0-indexed)
    level: int | None = None            # For heading roles: level 1-6
```

**Examples:**

```json
{"kind": "css", "value": "#submit-button"}
{"kind": "role", "value": "button", "name": "Submit"}
{"kind": "text", "value": "Click me", "exact": true}
{"kind": "placeholder", "value": "Enter email"}
{"kind": "test_id", "value": "login-btn"}
{"kind": "role", "value": "heading", "level": 1}
{"kind": "css", "value": ".item", "nth": 2}
```

### 2.2 Tool Categories

#### Navigation Tools

| Tool | Input Model | Description |
|------|-------------|-------------|
| `navigate` | `NavigateInput` | Go to URL |
| `reload_page` | `ReloadInput` | Reload current page |
| `go_back` | `GoBackInput` | Navigate back |

```python
class NavigateInput(BaseModel):
    url: str
    wait_until: Literal["load", "domcontentloaded", "networkidle", "commit"] = "load"
```

#### Action Tools

| Tool | Input Model | Description |
|------|-------------|-------------|
| `click` | `ClickInput` | Click element |
| `fill` | `FillInput` | Fill form field (clears first) |
| `type_text` | `TypeInput` | Type text character-by-character |
| `press` | `PressInput` | Press key/combo |
| `select_option` | `SelectOptionInput` | Select dropdown option |
| `hover` | `HoverInput` | Hover over element |
| `check` | `CheckInput` | Check/uncheck checkbox |
| `scroll` | `ScrollInput` | Scroll page |

```python
class ClickInput(BaseModel):
    locator: LocatorRef
    button: Literal["left", "right", "middle"] = "left"
    click_count: int = 1          # 2 for double-click
    delay_ms: int = 0

class FillInput(BaseModel):
    locator: LocatorRef
    text: str
    clear_first: bool = True
```

#### Waiting Tools

| Tool | Input Model | Description |
|------|-------------|-------------|
| `wait_for` | `WaitForSelectorInput` | Wait for element state |
| `wait_for_load_state` | `WaitForLoadStateInput` | Wait for page load |
| `wait_for_timeout` | `WaitForTimeoutInput` | Fixed delay |

```python
class WaitForSelectorInput(BaseModel):
    locator: LocatorRef
    state: Literal["attached", "detached", "visible", "hidden"] = "visible"
    timeout_ms: int = 30000
```

#### Reading Tools

| Tool | Input Model | Description |
|------|-------------|-------------|
| `read_text` | `ReadTextInput` | Get element text |
| `read_value` | `ReadValueInput` | Get input value |
| `get_page_info` | `GetPageInfoInput` | Get URL/title |
| `is_visible` | `IsVisibleInput` | Check visibility |

```python
class ReadTextInput(BaseModel):
    locator: LocatorRef
    save_as: str | None = None    # Save to memory for later use
```

#### Assertion Tools

| Tool | Input Model | Description |
|------|-------------|-------------|
| `assert_visible` | `AssertVisibleInput` | Assert element visible |
| `assert_text` | `AssertTextInput` | Assert element text |
| `assert_title` | `AssertTitleInput` | Assert page title |
| `assert_url` | `AssertUrlInput` | Assert current URL |

```python
class AssertVisibleInput(BaseModel):
    locator: LocatorRef
    timeout_ms: int = 5000

class AssertTextInput(BaseModel):
    locator: LocatorRef
    expected: str
    exact: bool = False
    timeout_ms: int = 5000
```

#### Evidence Tools

| Tool | Input Model | Description |
|------|-------------|-------------|
| `take_screenshot` | `ScreenshotInput` | Capture screenshot |
| `remember` | `RememberInput` | Save value to memory |

```python
class RememberInput(BaseModel):
    name: str
    value: Any  # JSON-serializable
```

#### Finalization Tool

```python
class ReportResultInput(BaseModel):
    """Report the final test result. This ends the test run."""
    passed: bool
    reason: str
    evidence_points: list[str] = []
    screenshot_on_fail: bool = True
```

### 2.3 Tool Result Model

All tools return a standardized result:

```python
class ToolResult(BaseModel):
    ok: bool                         # Success flag
    data: dict[str, Any] = {}        # Result data on success
    error: str | None = None         # Error message on failure
    retryable: bool = False          # Can retry fix the issue?
    hint: str | None = None          # Suggestion for fixing
```

**Success Example:**
```json
{"ok": true, "data": {"text": "Hello World", "saved_as": "greeting"}}
```

**Error Example:**
```json
{
  "ok": false,
  "error": "Element not found: #submit-button",
  "retryable": true,
  "hint": "Try wait_for to ensure element is loaded"
}
```

### 2.4 OpenAI Schema Generation

Schemas are auto-generated from Pydantic models:

```python
def to_openai_tool_schema(model: type[BaseModel], name: str) -> dict:
    schema = model.model_json_schema()
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": model.__doc__,
            "parameters": {
                "type": "object",
                "properties": schema["properties"],
                "required": schema.get("required", []),
            },
            "strict": True,
        }
    }
```

---

## 3. Context Management Strategy

### 3.1 Design Principles

1. **Explicit over implicit**: No hidden variable namespace like `step_state`
2. **JSON-serializable**: All memory values must be JSON-compatible
3. **Bounded context**: Rolling transcript with max turns
4. **Fresh observation**: Page state injected each turn

### 3.2 Session Memory Model

```python
@dataclass
class SessionMemory:
    """Session memory for persisting values across tool calls."""
    
    values: dict[str, Any] = field(default_factory=dict)
    # Named values saved via save_as or remember tool
    # Example: {"username": "testuser", "item_count": 5}
    
    last_tool_results: list[ToolResult] = field(default_factory=list)
    # Recent tool outputs for debugging
    
    last_error: str | None = None
    # Most recent error message
    
    final_result: dict[str, Any] | None = None
    # Set by report_result tool
    
    failure_streak: int = 0
    # Consecutive failures (for circuit breaking)
```

### 3.3 Message Construction

Each LLM turn receives:

```python
messages = [
    # 1. System prompt with scenario contract
    {"role": "system", "content": SYSTEM_PROMPT.format(
        goal=scenario.goal,
        assertions=scenario.assertions,
        test_data=scenario.test_data,
    )},
    
    # 2. Current page observation (injected each turn)
    {"role": "user", "content": f"Current page state:\n{observation}"},
    
    # 3. Memory context (if any values stored)
    {"role": "user", "content": f"Remembered values: {json.dumps(memory.values)}"},
    
    # 4. Rolling transcript (last 8-12 turns)
    # ... previous assistant/user/tool messages ...
]
```

### 3.4 Transcript Trimming

```python
def trim_messages(messages: list[dict], keep_last: int = 10) -> None:
    """Keep system prompt + last N messages. Mutates in place."""
    if len(messages) <= keep_last + 1:
        return
    
    system = messages[0]
    recent = messages[-keep_last:]
    
    messages.clear()
    messages.append(system)
    messages.extend(recent)
```

### 3.5 Comparison with Current step_state

| Aspect | Current `step_state` | New `SessionMemory` |
|--------|---------------------|---------------------|
| Storage | Python locals dict | Explicit JSON dict |
| Persistence | Auto-persisted after exec | Explicit via save_as/remember |
| Debugging | Hard to inspect | Easy to serialize/log |
| Safety | Any Python object | JSON-serializable only |
| Test coverage | Implicit, fragile | Explicit, testable |

---

## 4. Provider Abstraction

### 4.1 Backend Protocol

```python
class LLMBackend(Protocol):
    """Protocol for LLM backends supporting tool calling."""
    
    async def next_turn(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AssistantTurn:
        """Get the next turn from the LLM."""
        ...
```

### 4.2 Normalized Response Types

```python
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON string
    
    def parse_arguments(self) -> dict[str, Any]:
        return json.loads(self.arguments)

@dataclass
class AssistantTurn:
    content: str | None
    tool_calls: list[ToolCall] | None
    finish_reason: str  # "stop", "tool_calls", "length"
    raw: Any = None  # Original provider response
    
    @property
    def is_terminal(self) -> bool:
        """True if conversation should end."""
        return self.finish_reason in ("stop", "length") and not self.tool_calls
    
    @property
    def has_tool_calls(self) -> bool:
        """True if tools need execution."""
        return bool(self.tool_calls)
```

### 4.3 OpenAI Chat Backend

```python
class OpenAIChatBackend:
    """OpenAI Chat Completions API backend."""
    
    def __init__(self, config: LLMConfig):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,  # Supports OpenAI-compatible APIs
        )
        self._model = config.model
        self._temperature = config.temperature
    
    async def next_turn(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AssistantTurn:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=tools if tools else None,
            tool_choice=kwargs.get("tool_choice", "auto"),
            temperature=self._temperature,
        )
        
        message = response.choices[0].message
        
        tool_calls = None
        if message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments,
                )
                for tc in message.tool_calls
            ]
        
        return AssistantTurn(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=response.choices[0].finish_reason,
            raw=response,
        )
```

### 4.4 Provider Support Matrix

| Provider | Implementation | Notes |
|----------|---------------|-------|
| OpenAI | `OpenAIChatBackend` | Full support, native tool calling |
| Doubao/ByteDance | `OpenAIChatBackend` | Via `base_url`, OpenAI-compatible |
| Azure OpenAI | `OpenAIChatBackend` | Via `base_url` |
| Anthropic | Future: `AnthropicBackend` | Different tool format, needs adapter |
| Other OpenAI-compatible | `OpenAIChatBackend` | LiteLLM, OneLLM, local models |

### 4.5 Backend Factory

```python
def create_backend(config: LLMConfig) -> LLMBackend:
    """Factory function to create the appropriate backend."""
    # For now, always use OpenAIChatBackend
    # Future: dispatch based on provider type
    return OpenAIChatBackend(config)
```

---

## 5. Migration Strategy

### 5.1 Migration Phases

```
Phase 1: Foundation (Safe, additive)
├── Add test infrastructure
├── Add characterization tests for current behavior
├── Add backend contract (no usage yet)
└── Add tool models (no usage yet)

Phase 2: Core Implementation (Parallel)
├── Track A: Tool runtime + handlers
├── Track B: Locator resolver
└── Track C: Session memory

Phase 3: Integration (Sequential)
├── Build agent_runner.py loop
├── Wire tools, memory, observer
├── Add error recovery logic
└── Add hybrid mode config flag

Phase 4: Validation
├── Integration tests with fake backend
├── Run scenarios in both modes
└── Compare results, fix discrepancies

Phase 5: Cutover
├── Make tool mode default
├── Update prompts
└── Remove legacy exec after stabilization
```

### 5.2 Hybrid Mode

```python
class AgentMode(str, Enum):
    EXEC = "exec"        # Current exec-based behavior
    TOOLS = "tools"      # New tool-calling behavior
    HYBRID = "hybrid"    # Try tools, fallback to exec on error

# In settings.yaml
agent:
  mode: "tools"
  max_steps: 30
```

**Hybrid Mode Behavior:**
1. Try tool-calling path first
2. If model returns plain text (no tool calls), check for legacy JSON format
3. If legacy format detected, route to exec path
4. Log deprecation warning when using exec path

### 5.3 Backward Compatibility

| Component | Compatibility Strategy |
|-----------|----------------------|
| Scenario YAML | Unchanged - same format |
| TestReport | Unchanged - same output |
| StepRecord | Extended - add `tool_calls` field, keep `code` |
| CLI arguments | Unchanged |
| Config files | Extended - add `mode` option |

### 5.4 Rollback Plan

If tool mode shows regressions:
1. Set `agent.mode: "exec"` in settings.yaml
2. No code changes required
3. Investigate and fix in next iteration

---

## 6. File Structure

### 6.1 New Files

```
immiclaw_test/
├── agent_runner.py        # NEW: Tool-calling agent loop
├── agent_context.py       # NEW: Context building, memory management
├── llm_backends.py        # NEW: Backend protocol, OpenAI implementation
├── tool_models.py         # NEW: Pydantic tool input/output models
├── tool_runtime.py        # NEW: Tool dispatch, validation, execution
├── playwright_tools.py    # NEW: Playwright tool handlers
└── locator_resolver.py    # NEW: LocatorRef → Playwright locator

tests/
├── conftest.py            # Shared fixtures
├── unit/
│   ├── test_llm_backends.py
│   ├── test_tool_models.py
│   ├── test_locator_resolver.py
│   ├── test_tool_runtime.py
│   └── test_agent_context.py
└── integration/
    ├── test_agent_runner_tool_mode.py
    └── test_hybrid_mode.py
```

### 6.2 Modified Files

```
immiclaw_test/
├── agent.py               # MOD: Add mode dispatch, deprecation warnings
├── llm.py                 # MOD: Keep for backward compat, mark deprecated
├── models.py              # MOD: Add AgentMode, ToolCallRecord, extend StepRecord
└── config.py              # MOD: Support agent.mode config

main.py                    # MOD: Wire new agent_runner
pyproject.toml             # MOD: Lower Python requirement, add test deps
```

### 6.3 Deprecated Files (Remove in Phase 5)

```
immiclaw_test/
└── executor.py            # DEPRECATED: Remove after tool mode stabilized
```

---

## 7. Parallel Task Breakdown

### Wave 1: Foundation (Sequential)

| Task | Description | Dependencies |
|------|-------------|--------------|
| 1.1 | Add test infrastructure | None |
| 1.2 | Add characterization tests | 1.1 |

### Wave 2: Core Implementation (Parallel)

| Task | Description | Dependencies |
|------|-------------|--------------|
| 2.1 | Backend contract + FakeBackend | 1.2 |
| 2.2 | Tool input models + schemas | 1.2 |
| 2.3 | Locator resolver | 2.2 |
| 2.4 | Tool runtime + handlers | 2.2, 2.3 |
| 2.5 | Session memory model | 2.2 |

**Parallelization:**
- Tasks 2.1 and 2.2 can run in parallel
- Task 2.3 depends on 2.2
- Tasks 2.4 and 2.5 can run in parallel after their dependencies

### Wave 3: Integration (Sequential)

| Task | Description | Dependencies |
|------|-------------|--------------|
| 3.1 | Agent context builder | 2.1, 2.5 |
| 3.2 | Agent runner loop | 2.4, 3.1 |
| 3.3 | Hybrid mode implementation | 3.2 |
| 3.4 | Config/CLI wiring | 3.3 |

### Wave 4: Validation (Parallel)

| Task | Description | Dependencies |
|------|-------------|--------------|
| 4.1 | Integration tests with fake backend | 3.2 |
| 4.2 | Scenario parity tests | 3.4 |
| 4.3 | Documentation updates | 3.4 |
| 4.4 | Python version floor update | 3.4 |

### Wave 5: Cutover (Sequential)

| Task | Description | Dependencies |
|------|-------------|--------------|
| 5.1 | Make tool mode default | 4.1, 4.2 |
| 5.2 | Remove legacy exec path | 5.1 (after stabilization) |

---

## 8. Error Handling Strategy

### 8.1 Tool Execution Errors

```python
# Tool returns structured error, not exception
return ToolResult(
    ok=False,
    error="Element not found: #submit-button",
    retryable=True,
    hint="Try wait_for to ensure element is loaded"
)
```

### 8.2 Error Feedback Loop

```
LLM calls tool → Tool fails → ToolResult with error/hint
                                          │
                                          ▼
LLM receives: {"ok": false, "error": "...", "hint": "..."}
                                          │
                                          ▼
LLM can: retry with different args, or try different approach
```

### 8.3 Circuit Breaker

```python
MAX_FAILURE_STREAK = 3

if memory.failure_streak >= MAX_FAILURE_STREAK:
    # Force model to report result
    messages.append({
        "role": "user",
        "content": "Multiple consecutive failures. Please report_result now."
    })
```

### 8.4 Timeout Handling

```python
# Per-tool timeout in ToolRuntime
async def execute_with_timeout(tool_name, args, timeout_ms=30000):
    try:
        return await asyncio.wait_for(
            self.execute(tool_name, args),
            timeout=timeout_ms / 1000
        )
    except asyncio.TimeoutError:
        return ToolResult(
            ok=False,
            error=f"Tool {tool_name} timed out after {timeout_ms}ms",
            retryable=True,
            hint="Consider using wait_for_timeout if you need a longer wait"
        )
```

---

## 9. Security Improvements

### 9.1 What We Remove

- `exec()` with arbitrary LLM-generated code
- Uncontrolled namespace injection
- Python locals persistence with arbitrary objects
- Potential for filesystem/network access in generated code

### 9.2 What We Add

- Whitelisted tool set (explicit capabilities)
- Pydantic validation on all inputs
- Structured error handling (no exceptions to catch)
- JSON-only memory (no Python objects)
- Explicit save_as/remember for persistence

### 9.3 Threat Model Comparison

| Threat | exec() Mode | Tool Mode |
|--------|-------------|-----------|
| Arbitrary code execution | Possible | Not possible |
| Filesystem access | Possible via generated code | Not exposed |
| Network access | Possible via generated code | Not exposed |
| Privilege escalation | Possible | Not possible |
| Data exfiltration | Possible | Limited to tool outputs |

---

## 10. Testing Strategy

### 10.1 Unit Tests

- `test_llm_backends.py`: Backend contract, FakeBackend, OpenAI parsing
- `test_tool_models.py`: Pydantic validation, schema generation
- `test_locator_resolver.py`: LocatorRef → Playwright locator mapping
- `test_tool_runtime.py`: Tool dispatch, error handling, memory updates
- `test_agent_context.py`: Message building, trimming, memory context

### 10.2 Integration Tests

- `test_agent_runner_tool_mode.py`: Full loop with fake backend
- `test_hybrid_mode.py`: Fallback from tools to exec

### 10.3 Characterization Tests

- Preserve current parsing behavior
- Preserve current report format
- Ensure backward compatibility during migration

### 10.4 Test Fixtures

```python
@pytest.fixture
def fake_backend_with_click_sequence():
    """Backend that returns click tool call, then report_result."""
    backend = FakeBackend()
    backend.add_response(AssistantTurn(
        content=None,
        tool_calls=[ToolCall(id="1", name="click", arguments='{"locator": {"kind": "css", "value": "#btn"}}')],
        finish_reason="tool_calls"
    ))
    backend.add_response(AssistantTurn(
        content=None,
        tool_calls=[ToolCall(id="2", name="report_result", arguments='{"passed": true, "reason": "Done"}')],
        finish_reason="tool_calls"
    ))
    return backend
```

---

## 11. Success Criteria

### Phase 2 Complete When

- [ ] All unit tests pass for backend contract
- [ ] All unit tests pass for tool models
- [ ] All unit tests pass for locator resolver
- [ ] All unit tests pass for tool runtime
- [ ] Tool schemas generated correctly

### Phase 3 Complete When

- [ ] Agent runner executes tool-calling loop
- [ ] Hybrid mode falls back to exec when needed
- [ ] Session memory persists across steps
- [ ] Error feedback reaches LLM

### Phase 4 Complete When

- [ ] Integration tests pass with fake backend
- [ ] Real scenarios run in tool mode
- [ ] Results comparable to exec mode
- [ ] No regressions in report format

### Phase 5 Complete When

- [ ] Tool mode is default
- [ ] Legacy exec path removed
- [ ] All tests pass
- [ ] Documentation updated
