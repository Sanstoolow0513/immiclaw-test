# YAML Flow Assembly System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a YAML-based flow assembly system that lets the LLM test agent autonomously explore the application, using scenario YAMLs as verification tools and skill YAMLs as operational guidance.

**Architecture:** A new `flow_runner.py` implements a continuous agent loop separate from the existing `run_scenario()`. The LLM receives a system prompt with preset + skills + scenario catalog, then autonomously operates the browser. It can call `verify` to validate page state against scenario assertions, `list` to check progress, and `complete` to end the session. A reflect mechanism feeds completed/pending scenario status back into the conversation.

**Tech Stack:** Python 3.13+, Pydantic v2, PyYAML, OpenAI async SDK, Playwright async API, pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-03-24-yaml-flow-assembly-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `immiclaw_test/flow_models.py` | Create | `Flow`, `Skill`, `VerifyResult`, `AssertionResult`, `FlowStepRecord`, `FlowReport` Pydantic models |
| `immiclaw_test/skill_loader.py` | Create | Load skill YAMLs from `config/skills/`, filter by `applies_to`, assemble prompt text |
| `immiclaw_test/flow_config.py` | Create | `load_flow()`, `load_skill()`, placeholder expansion, static validation |
| `immiclaw_test/flow_verifier.py` | Create | `verify_scenario()` — load scenario YAML, get page state, LLM-evaluate assertions |
| `immiclaw_test/flow_runner.py` | Create | Continuous agent loop, `parse_flow_response()`, reflect injection, tool dispatch |
| `immiclaw_test/executor.py` | Modify | Add `flow_mode` param to disable `report_result` injection in flow mode |
| `immiclaw_test/reporter.py` | Modify | Add `print_flow_report()` and `save_flow_report()` |
| `main.py` | Modify | Add `--flow` and `--list-flows` CLI arguments |
| `config/flows/new-user-journey.yaml` | Create | Sample flow YAML |
| `config/skills/operation/login.yaml` | Create | Sample operation skill |
| `config/skills/strategy/error-handling.yaml` | Create | Sample strategy skill |
| `tests/test_flow_models.py` | Create | Unit tests for flow data models |
| `tests/test_skill_loader.py` | Create | Unit tests for skill loading and filtering |
| `tests/test_flow_config.py` | Create | Unit tests for flow loading and validation |
| `tests/test_flow_verifier.py` | Create | Unit tests for assertion evaluation |
| `tests/test_flow_runner.py` | Create | Unit tests for flow response parsing and reflect |
| `tests/test_flow_reporter.py` | Create | Unit tests for flow report output |
| `tests/test_flow_cli.py` | Create | Unit tests for CLI argument parsing |

---

## Task 1: Flow Data Models

**Files:**
- Create: `immiclaw_test/flow_models.py`
- Test: `tests/test_flow_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_flow_models.py
from immiclaw_test.flow_models import (
    Skill,
    Flow,
    AssertionResult,
    VerifyResult,
    FlowStepRecord,
    FlowReport,
)
from immiclaw_test.models import TestResult


def test_skill_model():
    s = Skill(
        name="login",
        type="operation",
        description="Login guide",
        prompt="Step 1: fill email...",
    )
    assert s.name == "login"
    assert s.type == "operation"
    assert s.applies_to == []


def test_skill_with_applies_to():
    s = Skill(
        name="login",
        type="operation",
        description="Login guide",
        prompt="...",
        applies_to=["qmr-login"],
    )
    assert s.applies_to == ["qmr-login"]


def test_flow_model():
    f = Flow(
        name="test-flow",
        description="A test flow",
        preset="You are a test agent.",
        scenarios=["qmr-login", "qmr-register"],
        start_url="{base_url}/login",
    )
    assert f.name == "test-flow"
    assert f.skills == []
    assert f.max_steps == 100
    assert f.timeout_seconds == 600
    assert f.context == {}


def test_flow_with_all_fields():
    f = Flow(
        name="full",
        description="Full flow",
        preset="preset",
        scenarios=["a", "b"],
        start_url="{base_url}/",
        skills=["login"],
        context={"user": {"email": "test@test.com"}},
        max_steps=50,
        timeout_seconds=300,
    )
    assert f.skills == ["login"]
    assert f.max_steps == 50
    assert f.context["user"]["email"] == "test@test.com"


def test_assertion_result():
    ar = AssertionResult(
        assertion="URL contains /cases",
        satisfied=True,
        evidence="Current URL is /cases",
    )
    assert ar.satisfied is True


def test_verify_result():
    vr = VerifyResult(
        scenario_name="qmr-login",
        passed=True,
        assertions=[
            AssertionResult(assertion="a", satisfied=True, evidence="ok"),
        ],
        reason="All passed",
        step_number=5,
    )
    assert vr.passed is True
    assert len(vr.assertions) == 1


def test_flow_step_record():
    sr = FlowStepRecord(
        step_number=1,
        action="code",
        thinking="Let me click login",
        code="await page.click('#login')",
    )
    assert sr.action == "code"
    assert sr.success is True


def test_flow_report():
    fr = FlowReport(
        flow_name="test",
        result=TestResult.PASS,
        verify_results=[],
        steps=[],
        scenarios_verified=[],
        scenarios_unverified=["qmr-login"],
        total_steps=0,
        elapsed_seconds=1.0,
    )
    assert fr.result == TestResult.PASS
    assert fr.scenarios_unverified == ["qmr-login"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_flow_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'immiclaw_test.flow_models'`

- [ ] **Step 3: Write minimal implementation**

```python
# immiclaw_test/flow_models.py
"""Data models for the flow assembly system."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .models import TestResult


class Skill(BaseModel):
    name: str
    type: str  # "operation" | "strategy"
    description: str
    prompt: str
    applies_to: list[str] = Field(default_factory=list)


class Flow(BaseModel):
    name: str
    description: str
    preset: str
    scenarios: list[str]
    start_url: str
    skills: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    max_steps: int = 100
    timeout_seconds: int = 600


class AssertionResult(BaseModel):
    assertion: str
    satisfied: bool
    evidence: str


class VerifyResult(BaseModel):
    scenario_name: str
    passed: bool
    assertions: list[AssertionResult]
    reason: str
    step_number: int


class FlowStepRecord(BaseModel):
    step_number: int
    action: str  # "code" | "verify" | "list" | "complete"
    thinking: str = ""
    code: str = ""
    scenario: str = ""
    output: str = ""
    error: str | None = None
    success: bool = True
    page_url: str | None = None


class FlowReport(BaseModel):
    flow_name: str
    result: TestResult
    verify_results: list[VerifyResult]
    steps: list[FlowStepRecord]
    scenarios_verified: list[str]
    scenarios_unverified: list[str]
    total_steps: int
    elapsed_seconds: float
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_flow_models.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/sanstoolow/immiclaw/immiclaw-test
git add immiclaw_test/flow_models.py tests/test_flow_models.py
git commit -m "feat: add flow assembly data models"
```

---

## Task 2: Skill Loader

**Files:**
- Create: `immiclaw_test/skill_loader.py`
- Create: `config/skills/operation/login.yaml`
- Create: `config/skills/strategy/error-handling.yaml`
- Test: `tests/test_skill_loader.py`

- [ ] **Step 1: Create sample skill YAML files**

```yaml
# config/skills/operation/login.yaml
name: login
type: operation
description: "登录操作指南"
applies_to:
  - qmr-login
  - qmr-journey-case-workflow
prompt: |
  当需要执行登录操作时，按以下步骤操作：
  1. 找到占位符为「请输入账号」的输入框，填入 test_data 中的 account/email
  2. 找到「请输入密码」的输入框，填入 password
  3. 点击「登录」按钮
  4. 等待 URL 离开 /login，预期跳转到 /cases
```

```yaml
# config/skills/strategy/error-handling.yaml
name: error-handling
type: strategy
description: "错误处理策略"
prompt: |
  遇到页面错误时：
  - 红色错误提示框：记录内容，判断是否可恢复
  - 白屏：尝试刷新一次，仍白屏则标记为失败
  - 控制台错误：不影响测试判断，除非页面功能异常
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_skill_loader.py
import tempfile
from pathlib import Path

import yaml

from immiclaw_test.skill_loader import load_skills, filter_skills_for_scenario, assemble_skills_prompt


def _write_skill(dir_path: Path, subdir: str, data: dict) -> Path:
    skill_dir = dir_path / subdir
    skill_dir.mkdir(parents=True, exist_ok=True)
    path = skill_dir / f"{data['name']}.yaml"
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_load_skills_from_dir():
    with tempfile.TemporaryDirectory() as tmp:
        skills_dir = Path(tmp)
        _write_skill(skills_dir, "operation", {
            "name": "login",
            "type": "operation",
            "description": "Login",
            "prompt": "Do login",
        })
        _write_skill(skills_dir, "strategy", {
            "name": "error-handling",
            "type": "strategy",
            "description": "Errors",
            "prompt": "Handle errors",
        })
        skills = load_skills(["login", "error-handling"], skills_dir)
        assert len(skills) == 2
        names = {s.name for s in skills}
        assert names == {"login", "error-handling"}


def test_load_skills_missing_raises():
    with tempfile.TemporaryDirectory() as tmp:
        import pytest
        with pytest.raises(FileNotFoundError):
            load_skills(["nonexistent"], Path(tmp))


def test_filter_skills_universal():
    """Skills without applies_to are always included."""
    from immiclaw_test.flow_models import Skill
    skills = [
        Skill(name="a", type="strategy", description="", prompt="universal"),
    ]
    result = filter_skills_for_scenario(skills, "any-scenario")
    assert len(result) == 1


def test_filter_skills_with_applies_to():
    """Skills with applies_to are included for matching scenarios, but still injected in flow mode."""
    from immiclaw_test.flow_models import Skill
    skills = [
        Skill(name="login", type="operation", description="", prompt="login stuff", applies_to=["qmr-login"]),
        Skill(name="general", type="strategy", description="", prompt="general stuff"),
    ]
    # In flow mode, all skills are injected (applies_to is informational annotation)
    result = filter_skills_for_scenario(skills, scenario_name=None)
    assert len(result) == 2


def test_assemble_skills_prompt():
    from immiclaw_test.flow_models import Skill
    skills = [
        Skill(name="login", type="operation", description="Login", prompt="Do login", applies_to=["qmr-login"]),
        Skill(name="errors", type="strategy", description="Errors", prompt="Handle errors"),
    ]
    prompt = assemble_skills_prompt(skills)
    assert "### 操作级" in prompt
    assert "### 策略级" in prompt
    assert "Do login" in prompt
    assert "Handle errors" in prompt
    assert "适用场景: qmr-login" in prompt
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_skill_loader.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

```python
# immiclaw_test/skill_loader.py
"""Load and assemble skill YAML files into LLM prompt fragments."""

from __future__ import annotations

from pathlib import Path

import yaml

from .flow_models import Skill


def load_skills(skill_names: list[str], skills_dir: Path) -> list[Skill]:
    """Load skill YAMLs by name from skills_dir (searching operation/ and strategy/ subdirs)."""
    skills: list[Skill] = []
    for name in skill_names:
        path = _find_skill_file(name, skills_dir)
        if path is None:
            raise FileNotFoundError(
                f"Skill '{name}' not found in {skills_dir}. "
                f"Searched operation/ and strategy/ subdirectories."
            )
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        skills.append(Skill(**data))
    return skills


def _find_skill_file(name: str, skills_dir: Path) -> Path | None:
    for subdir in ("operation", "strategy"):
        for ext in (".yaml", ".yml"):
            candidate = skills_dir / subdir / f"{name}{ext}"
            if candidate.is_file():
                return candidate
    return None


def filter_skills_for_scenario(
    skills: list[Skill],
    scenario_name: str | None,
) -> list[Skill]:
    """Filter skills for a specific scenario, or return all if scenario_name is None (flow mode)."""
    if scenario_name is None:
        return list(skills)
    return [
        s for s in skills
        if not s.applies_to or scenario_name in s.applies_to
    ]


def assemble_skills_prompt(skills: list[Skill]) -> str:
    """Assemble filtered skills into a structured prompt fragment."""
    operation_skills = [s for s in skills if s.type == "operation"]
    strategy_skills = [s for s in skills if s.type == "strategy"]

    parts: list[str] = []

    if operation_skills:
        parts.append("### 操作级")
        for s in operation_skills:
            header = f"**{s.description}** ({s.name})"
            if s.applies_to:
                header += f"\n适用场景: {', '.join(s.applies_to)}"
            parts.append(f"{header}\n{s.prompt.strip()}")

    if strategy_skills:
        parts.append("### 策略级")
        for s in strategy_skills:
            header = f"**{s.description}** ({s.name})"
            if s.applies_to:
                header += f"\n适用场景: {', '.join(s.applies_to)}"
            parts.append(f"{header}\n{s.prompt.strip()}")

    return "\n\n".join(parts)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_skill_loader.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /home/sanstoolow/immiclaw/immiclaw-test
git add immiclaw_test/skill_loader.py tests/test_skill_loader.py config/skills/
git commit -m "feat: add skill loader with filtering and prompt assembly"
```

---

## Task 3: Flow Config Loader

**Files:**
- Create: `immiclaw_test/flow_config.py`
- Create: `config/flows/new-user-journey.yaml`
- Test: `tests/test_flow_config.py`

- [ ] **Step 1: Create sample flow YAML**

```yaml
# config/flows/new-user-journey.yaml
name: new-user-journey
description: "全新用户从注册到首次对话的完整旅程"

preset: |
  你是 ImmiClaw Web 应用的测试 Agent。你的任务是模拟真实用户，
  自主探索应用并验证功能正确性。
  你拥有完全的决策权——自行判断接下来该测什么、怎么测。
  当你认为某个功能点已经操作到位时，调用 verify 来校验。

skills:
  - login
  - error-handling

scenarios:
  - qmr-smoke-register
  - qmr-smoke-case-create
  - qmr-smoke-chat-basic

start_url: "{base_url}/register"

context:
  new_user:
    email: "flow-{timestamp}@test.com"
    password: "FlowPass123!"

max_steps: 100
timeout_seconds: 600
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_flow_config.py
import tempfile
from pathlib import Path

import pytest
import yaml

from immiclaw_test.flow_config import load_flow, validate_flow


def _make_config_tree(tmp: str, scenarios: list[str], skills: list[dict], flow: dict) -> Path:
    """Build a minimal config directory tree for testing."""
    root = Path(tmp)

    # Create scenario files
    sc_dir = root / "scenarios"
    sc_dir.mkdir(parents=True)
    for name in scenarios:
        (sc_dir / f"{name}.yaml").write_text(
            yaml.dump({"name": name, "description": "test", "target_url": "{base_url}/",
                        "goal": "test goal", "assertions": ["assert 1"]}, allow_unicode=True),
            encoding="utf-8",
        )

    # Create skill files
    sk_dir = root / "skills"
    for s in skills:
        subdir = sk_dir / s["type"]
        subdir.mkdir(parents=True, exist_ok=True)
        (subdir / f"{s['name']}.yaml").write_text(
            yaml.dump(s, allow_unicode=True), encoding="utf-8",
        )

    # Create flow file
    fl_dir = root / "flows"
    fl_dir.mkdir(parents=True)
    (fl_dir / f"{flow['name']}.yaml").write_text(
        yaml.dump(flow, allow_unicode=True), encoding="utf-8",
    )

    return root


def test_load_flow_basic():
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_config_tree(
            tmp,
            scenarios=["sc-a", "sc-b"],
            skills=[{"name": "sk1", "type": "operation", "description": "d", "prompt": "p"}],
            flow={
                "name": "test-flow",
                "description": "Test",
                "preset": "You are a tester",
                "scenarios": ["sc-a", "sc-b"],
                "start_url": "{base_url}/",
                "skills": ["sk1"],
                "context": {"key": "val-{timestamp}"},
            },
        )
        flow = load_flow("test-flow", root, base_url="http://localhost:3000")
        assert flow.name == "test-flow"
        # {timestamp} should be expanded
        assert "{timestamp}" not in flow.context["key"]
        # {base_url} in start_url is NOT expanded at load time (used at runtime)
        assert "{base_url}" in flow.start_url


def test_validate_flow_missing_scenario():
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_config_tree(
            tmp,
            scenarios=["sc-a"],
            skills=[],
            flow={
                "name": "bad-flow",
                "description": "Bad",
                "preset": "p",
                "scenarios": ["sc-a", "sc-nonexistent"],
                "start_url": "{base_url}/",
            },
        )
        with pytest.raises(ValueError, match="sc-nonexistent"):
            load_flow("bad-flow", root, base_url="http://localhost")


def test_validate_flow_missing_skill():
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_config_tree(
            tmp,
            scenarios=["sc-a"],
            skills=[],
            flow={
                "name": "bad-flow",
                "description": "Bad",
                "preset": "p",
                "scenarios": ["sc-a"],
                "skills": ["missing-skill"],
                "start_url": "{base_url}/",
            },
        )
        with pytest.raises(ValueError, match="missing-skill"):
            load_flow("bad-flow", root, base_url="http://localhost")


def test_load_flow_file_path():
    """Can also load by file path instead of name."""
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_config_tree(
            tmp,
            scenarios=["sc-a"],
            skills=[],
            flow={
                "name": "path-flow",
                "description": "D",
                "preset": "p",
                "scenarios": ["sc-a"],
                "start_url": "{base_url}/",
            },
        )
        flow_path = root / "flows" / "path-flow.yaml"
        flow = load_flow(str(flow_path), root, base_url="http://localhost")
        assert flow.name == "path-flow"


def test_validate_flow_bad_start_url():
    with tempfile.TemporaryDirectory() as tmp:
        root = _make_config_tree(
            tmp,
            scenarios=["sc-a"],
            skills=[],
            flow={
                "name": "bad-url",
                "description": "Bad",
                "preset": "p",
                "scenarios": ["sc-a"],
                "start_url": "not-a-url",
            },
        )
        with pytest.raises(ValueError, match="start_url"):
            load_flow("bad-url", root, base_url="http://localhost")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_flow_config.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Write minimal implementation**

```python
# immiclaw_test/flow_config.py
"""Flow configuration loading, validation, and placeholder expansion."""

from __future__ import annotations

import time
from pathlib import Path

import yaml

from .flow_models import Flow


def load_flow(
    flow_name_or_path: str,
    config_dir: Path,
    *,
    base_url: str = "",
) -> Flow:
    """Load a flow YAML by name or file path, validate, and expand placeholders."""
    flow_path = _resolve_flow_path(flow_name_or_path, config_dir)

    with open(flow_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    timestamp = str(int(time.time()))
    if "context" in data and isinstance(data["context"], dict):
        data["context"] = _replace_templates(
            data["context"],
            {"timestamp": timestamp, "base_url": base_url},
        )

    flow = Flow(**data)
    validate_flow(flow, config_dir)
    return flow


def validate_flow(flow: Flow, config_dir: Path) -> None:
    """Static validation: check that all referenced scenarios, skills exist, and start_url is valid."""
    scenarios_dir = config_dir / "scenarios"
    for name in flow.scenarios:
        found = False
        for ext in (".yaml", ".yml"):
            if (scenarios_dir / f"{name}{ext}").is_file():
                found = True
                break
        if not found:
            raise ValueError(
                f"Scenario '{name}' referenced in flow '{flow.name}' "
                f"not found in {scenarios_dir}"
            )

    skills_dir = config_dir / "skills"
    for name in flow.skills:
        found = False
        for subdir in ("operation", "strategy"):
            for ext in (".yaml", ".yml"):
                if (skills_dir / subdir / f"{name}{ext}").is_file():
                    found = True
                    break
            if found:
                break
        if not found:
            raise ValueError(
                f"Skill '{name}' referenced in flow '{flow.name}' "
                f"not found in {skills_dir}"
            )

    if "{base_url}" not in flow.start_url and not flow.start_url.startswith(("http://", "https://")):
        raise ValueError(
            f"start_url '{flow.start_url}' must contain {{base_url}} or be an absolute URL"
        )


def _resolve_flow_path(flow_name_or_path: str, config_dir: Path) -> Path:
    path = Path(flow_name_or_path)
    if path.is_file():
        return path.resolve()
    flows_dir = config_dir / "flows"
    for ext in (".yaml", ".yml"):
        candidate = flows_dir / f"{flow_name_or_path}{ext}"
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        f"Flow '{flow_name_or_path}' not found in {flows_dir}"
    )


def _replace_templates(obj: object, variables: dict[str, str]) -> object:
    if isinstance(obj, str):
        for key, value in variables.items():
            obj = obj.replace(f"{{{key}}}", value)
        return obj
    if isinstance(obj, dict):
        return {k: _replace_templates(v, variables) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_templates(item, variables) for item in obj]
    return obj
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_flow_config.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /home/sanstoolow/immiclaw/immiclaw-test
git add immiclaw_test/flow_config.py tests/test_flow_config.py config/flows/
git commit -m "feat: add flow config loader with validation and placeholder expansion"
```

---

## Task 4: Flow Verifier

**Files:**
- Create: `immiclaw_test/flow_verifier.py`
- Test: `tests/test_flow_verifier.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_flow_verifier.py
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from immiclaw_test.flow_models import AssertionResult, VerifyResult
from immiclaw_test.flow_verifier import (
    build_verify_prompt,
    parse_verify_response,
    verify_scenario,
)
from immiclaw_test.models import LLMConfig, Scenario


def test_build_verify_prompt():
    scenario = Scenario(
        name="test",
        description="Test scenario",
        target_url="{base_url}/",
        goal="Verify login works",
        assertions=["URL contains /cases", "No error visible"],
    )
    page_state = {
        "url": "http://localhost/cases",
        "title": "Cases",
        "accessibility_tree": "[WebArea] ...",
    }
    prompt = build_verify_prompt(scenario, page_state)
    assert "Verify login works" in prompt
    assert "URL contains /cases" in prompt
    assert "No error visible" in prompt
    assert "http://localhost/cases" in prompt


def test_parse_verify_response_pass():
    response_text = json.dumps({
        "passed": True,
        "assertions": [
            {"assertion": "URL contains /cases", "satisfied": True, "evidence": "URL is /cases"},
        ],
        "reason": "All good",
    })
    result = parse_verify_response(response_text, "test-scenario", step_number=5)
    assert result.passed is True
    assert result.scenario_name == "test-scenario"
    assert result.step_number == 5
    assert len(result.assertions) == 1


def test_parse_verify_response_fail():
    response_text = json.dumps({
        "passed": False,
        "assertions": [
            {"assertion": "URL contains /cases", "satisfied": False, "evidence": "URL is /login"},
        ],
        "reason": "Login failed",
    })
    result = parse_verify_response(response_text, "test-scenario", step_number=3)
    assert result.passed is False


def test_parse_verify_response_json_in_code_block():
    response_text = "```json\n" + json.dumps({
        "passed": True,
        "assertions": [],
        "reason": "ok",
    }) + "\n```"
    result = parse_verify_response(response_text, "s", step_number=1)
    assert result.passed is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_flow_verifier.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

```python
# immiclaw_test/flow_verifier.py
"""Scenario verification — evaluate assertions against current page state via LLM."""

from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI

from .flow_models import AssertionResult, VerifyResult
from .models import LLMConfig, Scenario


def build_verify_prompt(scenario: Scenario, page_state: dict[str, Any], test_data: dict[str, Any] | None = None) -> str:
    assertions_list = "\n".join(
        f"{i+1}. {a}" for i, a in enumerate(scenario.assertions)
    )
    prompt = (
        f"请根据当前页面状态，逐条判断以下断言是否满足：\n\n"
        f"场景：{scenario.name}\n"
        f"目标：{scenario.goal}\n\n"
        f"当前页面 URL: {page_state['url']}\n"
        f"页面标题: {page_state.get('title', '')}\n\n"
        f"页面结构:\n{page_state.get('accessibility_tree', '(unavailable)')}\n\n"
        f"断言列表：\n{assertions_list}\n\n"
        '请以 JSON 回复：\n'
        '{\n'
        '  "passed": true/false,\n'
        '  "assertions": [\n'
        '    {"assertion": "...", "satisfied": true/false, "evidence": "..."},\n'
        '    ...\n'
        '  ],\n'
        '  "reason": "总体判断理由"\n'
        '}'
    )
    if test_data:
        import json as _json
        prompt += f"\n\n测试数据:\n```json\n{_json.dumps(test_data, ensure_ascii=False, indent=2)}\n```"
    return prompt


def parse_verify_response(
    response_text: str,
    scenario_name: str,
    step_number: int,
) -> VerifyResult:
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end_idx = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end_idx = i
                break
        text = "\n".join(lines[1:end_idx])

    data = json.loads(text)
    assertions = [
        AssertionResult(
            assertion=a.get("assertion", ""),
            satisfied=bool(a.get("satisfied", False)),
            evidence=a.get("evidence", ""),
        )
        for a in data.get("assertions", [])
    ]
    return VerifyResult(
        scenario_name=scenario_name,
        passed=bool(data.get("passed", False)),
        assertions=assertions,
        reason=str(data.get("reason", "")),
        step_number=step_number,
    )


async def verify_scenario(
    scenario: Scenario,
    page_state: dict[str, Any],
    llm_config: LLMConfig,
    flow_context: dict[str, Any] | None = None,
) -> VerifyResult:
    """Run a verification of the scenario assertions against current page state.

    Makes an independent LLM call (does not affect the main agent conversation).
    flow_context is merged with scenario.test_data (scenario takes precedence)
    to provide context for assertion evaluation.
    """
    merged_data: dict[str, Any] = {}
    if flow_context:
        merged_data.update(flow_context)
    merged_data.update(scenario.test_data)

    client = AsyncOpenAI(api_key=llm_config.api_key, base_url=llm_config.base_url)
    prompt = build_verify_prompt(scenario, page_state, test_data=merged_data)

    response = await client.chat.completions.create(
        model=llm_config.model,
        messages=[
            {"role": "system", "content": "你是一个 Web 页面状态评估器。根据给定的页面状态判断断言是否满足。仅以 JSON 格式回复。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
    )
    response_text = response.choices[0].message.content or ""
    return parse_verify_response(response_text, scenario.name, step_number=0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_flow_verifier.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/sanstoolow/immiclaw/immiclaw-test
git add immiclaw_test/flow_verifier.py tests/test_flow_verifier.py
git commit -m "feat: add flow verifier with assertion evaluation"
```

---

## Task 5: Flow Runner — Response Parsing and Reflect

**Files:**
- Create: `immiclaw_test/flow_runner.py` (partial — parsing and reflect only)
- Test: `tests/test_flow_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_flow_runner.py
import json

import pytest

from immiclaw_test.flow_models import VerifyResult, AssertionResult
from immiclaw_test.flow_runner import (
    parse_flow_response,
    build_reflect_message,
    build_flow_system_prompt,
    detect_oscillation,
)


def test_parse_flow_response_code():
    text = json.dumps({
        "thinking": "Need to click login",
        "action": "code",
        "code": "await page.click('#login')",
    })
    parsed = parse_flow_response(text)
    assert parsed["action"] == "code"
    assert parsed["code"] == "await page.click('#login')"
    assert parsed["thinking"] == "Need to click login"


def test_parse_flow_response_verify():
    text = json.dumps({
        "thinking": "Login done, verify now",
        "action": "verify",
        "scenario": "qmr-login",
    })
    parsed = parse_flow_response(text)
    assert parsed["action"] == "verify"
    assert parsed["scenario"] == "qmr-login"


def test_parse_flow_response_complete():
    text = json.dumps({
        "thinking": "All done",
        "action": "complete",
        "reason": "All scenarios covered",
    })
    parsed = parse_flow_response(text)
    assert parsed["action"] == "complete"
    assert parsed["reason"] == "All scenarios covered"


def test_parse_flow_response_list():
    text = json.dumps({"thinking": "Check status", "action": "list"})
    parsed = parse_flow_response(text)
    assert parsed["action"] == "list"


def test_parse_flow_response_invalid_action():
    text = json.dumps({"thinking": "hmm", "action": "invalid_action"})
    with pytest.raises(ValueError, match="Unknown action"):
        parse_flow_response(text)


def test_parse_flow_response_code_block():
    inner = json.dumps({"thinking": "t", "action": "code", "code": "pass"})
    text = f"```json\n{inner}\n```"
    parsed = parse_flow_response(text)
    assert parsed["action"] == "code"


def test_build_reflect_message():
    verified = {
        "qmr-login": VerifyResult(
            scenario_name="qmr-login", passed=True,
            assertions=[], reason="ok", step_number=5,
        ),
        "qmr-register": VerifyResult(
            scenario_name="qmr-register", passed=False,
            assertions=[], reason="button not found", step_number=12,
        ),
    }
    all_scenarios = ["qmr-login", "qmr-register", "qmr-chat"]
    scenario_descriptions = {
        "qmr-login": "登录验证",
        "qmr-register": "注册验证",
        "qmr-chat": "聊天功能",
    }
    msg = build_reflect_message(verified, all_scenarios, scenario_descriptions)
    assert "qmr-login" in msg
    assert "pass" in msg
    assert "qmr-register" in msg
    assert "fail" in msg
    assert "qmr-chat" in msg
    assert "聊天功能" in msg


def test_build_flow_system_prompt():
    prompt = build_flow_system_prompt(
        preset="You are a tester.",
        skills_prompt="### 操作级\nDo login",
        scenario_catalog=[
            {"name": "qmr-login", "description": "Login test", "goal": "Verify login"},
        ],
        test_data={"account": "test@test.com"},
    )
    assert "You are a tester." in prompt
    assert "Do login" in prompt
    assert "qmr-login" in prompt
    assert "verify" in prompt
    assert "test@test.com" in prompt


def test_detect_oscillation_true():
    path = ["a", "b", "a", "b"]
    assert detect_oscillation(path) is True


def test_detect_oscillation_false():
    path = ["a", "b", "c", "d"]
    assert detect_oscillation(path) is False


def test_detect_oscillation_short():
    path = ["a", "b"]
    assert detect_oscillation(path) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_flow_runner.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation (parsing, reflect, prompt building)**

```python
# immiclaw_test/flow_runner.py
"""Flow runner — continuous agent session with scenario verification and reflect."""

from __future__ import annotations

import json
from typing import Any

from .flow_models import VerifyResult

_VALID_ACTIONS = frozenset({"code", "verify", "list", "complete"})


def parse_flow_response(response_text: str) -> dict[str, Any]:
    """Parse LLM response JSON for flow mode."""
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end_idx = len(lines)
        for i in range(len(lines) - 1, 0, -1):
            if lines[i].strip() == "```":
                end_idx = i
                break
        text = "\n".join(lines[1:end_idx])

    data = json.loads(text)
    action = str(data.get("action", "")).strip()
    if action not in _VALID_ACTIONS:
        raise ValueError(
            f"Unknown action '{action}'. Must be one of: {', '.join(sorted(_VALID_ACTIONS))}"
        )

    return {
        "thinking": str(data.get("thinking", "")),
        "action": action,
        "code": str(data.get("code", "")),
        "scenario": str(data.get("scenario", "")),
        "reason": str(data.get("reason", "")),
    }


def build_reflect_message(
    verified: dict[str, VerifyResult],
    all_scenarios: list[str],
    scenario_descriptions: dict[str, str],
) -> str:
    """Build the reflect message injected after each verify_scenario call."""
    parts = ["--- 测试进度更新 ---"]

    if verified:
        parts.append("已完成的验证：")
        for name, vr in verified.items():
            status = "✓ pass" if vr.passed else "✗ fail"
            parts.append(f"  {status}: {name} (步骤 {vr.step_number}，{vr.reason})")

    unverified = [s for s in all_scenarios if s not in verified]
    if unverified:
        parts.append("\n尚未覆盖的场景：")
        for name in unverified:
            desc = scenario_descriptions.get(name, "")
            parts.append(f"  · {name}: {desc}")

    parts.append(
        "\n请继续探索未覆盖的功能。"
        "对于失败的场景，如果当前页面状态允许，可以尝试重新操作后再次验证。"
    )
    parts.append("---")
    return "\n".join(parts)


def build_flow_system_prompt(
    preset: str,
    skills_prompt: str,
    scenario_catalog: list[dict[str, str]],
    test_data: dict[str, Any],
) -> str:
    """Build the system prompt for a flow session."""
    catalog_lines = []
    for i, s in enumerate(scenario_catalog, 1):
        catalog_lines.append(f"{i}. {s['name']} — {s.get('description', s.get('goal', ''))}")
    catalog_text = "\n".join(catalog_lines)

    test_data_text = json.dumps(test_data, ensure_ascii=False, indent=2) if test_data else "{}"

    return (
        f"{preset}\n\n"
        f"## 你的操作能力\n\n"
        f"你可以生成 Python 代码操作 Playwright page 对象来与页面交互。\n\n"
        f"## 操作指南（Skills）\n\n"
        f"{skills_prompt}\n\n"
        f"## 可用测试场景\n\n"
        f"以下是你可以验证的测试场景。当你认为某个场景的功能点已经操作到位时，\n"
        f'使用 action="verify" 来校验：\n\n'
        f"{catalog_text}\n\n"
        f"## 响应格式\n\n"
        f"每步回复一个 JSON 对象，包含以下字段：\n"
        f'- `"thinking"`: 你的分析和推理\n'
        f'- `"action"`: 选择 "code"、"verify"、"list" 或 "complete"\n'
        f'- `"code"`: action=code 时，要执行的 Python 代码\n'
        f'- `"scenario"`: action=verify 时，要验证的场景名\n'
        f'- `"reason"`: action=complete 时，结束原因\n\n'
        f"每步只允许一个 action。\n\n"
        f"## 测试数据\n\n"
        f"```json\n{test_data_text}\n```"
    )


def detect_oscillation(path_taken: list[str]) -> bool:
    """Detect A↔B oscillation pattern in the last 4 entries of path_taken."""
    if len(path_taken) < 4:
        return False
    tail = path_taken[-4:]
    return (
        tail[0] == tail[2]
        and tail[1] == tail[3]
        and tail[0] != tail[1]
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_flow_runner.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/sanstoolow/immiclaw/immiclaw-test
git add immiclaw_test/flow_runner.py tests/test_flow_runner.py
git commit -m "feat: add flow runner parsing, reflect, and prompt building"
```

---

## Task 6: Flow Runner — Main Loop

**Files:**
- Modify: `immiclaw_test/flow_runner.py`
- Test: `tests/test_flow_runner_loop.py` (integration-level test with mocked LLM)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_flow_runner_loop.py
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from immiclaw_test.flow_models import Flow, FlowReport
from immiclaw_test.flow_runner import run_flow
from immiclaw_test.models import Settings, Scenario, TestResult


def _make_scenario(name: str) -> Scenario:
    return Scenario(
        name=name,
        description=f"Test {name}",
        target_url="{base_url}/",
        goal=f"Goal for {name}",
        assertions=[f"Assert for {name}"],
    )


def _mock_llm_responses(*responses):
    """Create a mock OpenAI client that returns the given responses in order."""
    client = AsyncMock()
    side_effects = []
    for text in responses:
        choice = MagicMock()
        choice.message.content = text
        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = None
        side_effects.append(resp)
    client.chat.completions.create = AsyncMock(side_effect=side_effects)
    return client


@pytest.mark.asyncio
async def test_run_flow_complete_immediately():
    """LLM immediately calls complete — result should be error (no verify)."""
    flow = Flow(
        name="test",
        description="Test",
        preset="p",
        scenarios=["sc-a"],
        start_url="http://localhost/",
        max_steps=10,
    )
    scenarios = {"sc-a": _make_scenario("sc-a")}

    responses = [
        json.dumps({"thinking": "done", "action": "complete", "reason": "nothing to test"}),
    ]

    page = AsyncMock()
    page.url = "http://localhost/"
    page.title = AsyncMock(return_value="Test")
    page.accessibility = MagicMock()
    page.accessibility.snapshot = AsyncMock(return_value=None)
    page.goto = AsyncMock()

    with patch("immiclaw_test.flow_runner.create_client") as mock_create:
        mock_create.return_value = _mock_llm_responses(*responses)
        report = await run_flow(
            flow=flow,
            scenarios=scenarios,
            page=page,
            settings=Settings(),
            skills_prompt="",
        )

    assert report.result == TestResult.ERROR
    assert report.total_steps == 1


@pytest.mark.asyncio
async def test_run_flow_code_then_verify_pass():
    """LLM runs code, then verifies — should pass."""
    flow = Flow(
        name="test",
        description="Test",
        preset="p",
        scenarios=["sc-a"],
        start_url="http://localhost/",
        max_steps=10,
    )
    scenarios = {"sc-a": _make_scenario("sc-a")}

    responses = [
        # Step 1: execute code
        json.dumps({"thinking": "click button", "action": "code", "code": "pass"}),
        # Step 2: verify
        json.dumps({"thinking": "verify now", "action": "verify", "scenario": "sc-a"}),
        # Step 3: complete
        json.dumps({"thinking": "all done", "action": "complete", "reason": "all verified"}),
    ]

    verify_response = json.dumps({
        "passed": True,
        "assertions": [{"assertion": "Assert for sc-a", "satisfied": True, "evidence": "ok"}],
        "reason": "All pass",
    })

    page = AsyncMock()
    page.url = "http://localhost/"
    page.title = AsyncMock(return_value="Test")
    page.accessibility = MagicMock()
    page.accessibility.snapshot = AsyncMock(return_value=None)
    page.goto = AsyncMock()

    with patch("immiclaw_test.flow_runner.create_client") as mock_create, \
         patch("immiclaw_test.flow_runner._verify_scenario_impl") as mock_verify:
        from immiclaw_test.flow_models import VerifyResult, AssertionResult
        mock_verify.return_value = VerifyResult(
            scenario_name="sc-a",
            passed=True,
            assertions=[AssertionResult(assertion="Assert for sc-a", satisfied=True, evidence="ok")],
            reason="All pass",
            step_number=2,
        )
        mock_create.return_value = _mock_llm_responses(*responses)
        report = await run_flow(
            flow=flow,
            scenarios=scenarios,
            page=page,
            settings=Settings(),
            skills_prompt="",
        )

    assert report.result == TestResult.PASS
    assert len(report.verify_results) == 1
    assert report.scenarios_verified == ["sc-a"]
    assert report.scenarios_unverified == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_flow_runner_loop.py -v`
Expected: FAIL with `ImportError` (run_flow not defined)

- [ ] **Step 2.5: Modify executor.py to support flow_mode**

Add a `flow_mode` parameter to `execute_code()` in `immiclaw_test/executor.py`. When `flow_mode=True`, `report_result` is **not** injected into the namespace:

In `execute_code()`, change the namespace construction:

```python
async def execute_code(
    code: str,
    page: "Page",
    test_data: dict[str, Any],
    timeout: float = 30.0,
    step_state: dict[str, Any] | None = None,
    flow_mode: bool = False,   # NEW PARAMETER
) -> ExecutionResult:
```

And conditionally add `report_result`:

```python
    namespace: dict[str, Any] = {
        "__builtins__": _SAFE_BUILTINS,
        "page": page,
        "test_data": test_data,
        "expect": _playwright_expect,
        "asyncio": asyncio,
        "re": re_mod,
        "json": json_mod,
    }
    if not flow_mode:
        namespace["report_result"] = report_result
```

Also update `_FRAMEWORK_NAMES` handling: when `flow_mode=True`, `report_result` is not a framework name (since it's not injected).

Add a test in `tests/test_flow_runner_loop.py`:

```python
@pytest.mark.asyncio
async def test_execute_code_flow_mode_no_report_result():
    """In flow_mode, report_result should not be available."""
    from immiclaw_test.executor import execute_code
    page = AsyncMock()
    result = await execute_code(
        code="print('report_result' in dir())",
        page=page,
        test_data={},
        flow_mode=True,
    )
    assert result.success
    assert "False" in result.output
```

- [ ] **Step 3: Write the run_flow implementation**

Add the following to `immiclaw_test/flow_runner.py` (appending to existing file):

```python
# --- Append to immiclaw_test/flow_runner.py ---

import time
from collections import Counter

from openai import AsyncOpenAI

from .executor import execute_code
from .flow_models import Flow, FlowReport, FlowStepRecord, VerifyResult
from .flow_verifier import verify_scenario as _raw_verify_scenario
from .models import LLMConfig, Scenario, Settings, TestResult
from .observer import format_state_for_llm, get_page_state

if TYPE_CHECKING:
    from playwright.async_api import Page


_STDOUT_TRUNCATE = 6000
_MAX_PARSE_RETRIES = 3


def create_client(llm_config: LLMConfig) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=llm_config.api_key, base_url=llm_config.base_url)


async def _verify_scenario_impl(
    scenario: Scenario,
    page: "Page",
    llm_config: LLMConfig,
    step_number: int,
    flow_context: dict[str, Any] | None = None,
) -> VerifyResult:
    page_state = await get_page_state(page)
    result = await _raw_verify_scenario(scenario, page_state, llm_config, flow_context=flow_context)
    result.step_number = step_number
    return result


async def run_flow(
    flow: Flow,
    scenarios: dict[str, Scenario],
    page: "Page",
    settings: Settings,
    skills_prompt: str,
    output_dir: Path | None = None,
) -> FlowReport:
    """Execute a flow session: single continuous agent loop with verification tools."""
    client = create_client(settings.llm)

    scenario_catalog = [
        {"name": s.name, "description": s.description, "goal": s.goal}
        for s in scenarios.values()
    ]
    system_prompt = build_flow_system_prompt(
        preset=flow.preset,
        skills_prompt=skills_prompt,
        scenario_catalog=scenario_catalog,
        test_data=flow.context,
    )
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]

    steps: list[FlowStepRecord] = []
    verified: dict[str, VerifyResult] = {}
    scenario_visit_count: Counter[str] = Counter()
    path_taken: list[str] = []
    start_time = time.time()
    step_state: dict[str, Any] = {}
    parse_retries = 0

    start_url = flow.start_url.format(base_url=settings.base_url)
    await page.goto(start_url, wait_until="domcontentloaded", timeout=15000)

    scenario_descriptions = {s.name: s.description for s in scenarios.values()}

    for step_num in range(1, flow.max_steps + 1):
        elapsed = time.time() - start_time
        if elapsed > flow.timeout_seconds:
            return _build_flow_report(
                flow, TestResult.TIMEOUT, verified, steps, scenarios, elapsed,
            )

        page_state = await get_page_state(page)
        state_text = format_state_for_llm(page_state)
        step_msg = f"Step {step_num}/{flow.max_steps}\n\n{state_text}"
        messages.append({"role": "user", "content": step_msg})
        _trim_flow_messages(messages)

        try:
            response = await client.chat.completions.create(
                model=settings.llm.model,
                messages=messages,
                temperature=settings.llm.temperature,
            )
            response_text = response.choices[0].message.content or ""
            messages.append({"role": "assistant", "content": response_text})
            parsed = parse_flow_response(response_text)
            parse_retries = 0
        except Exception as e:
            parse_retries += 1
            steps.append(FlowStepRecord(
                step_number=step_num, action="code",
                thinking="Failed to get/parse response",
                error=str(e), success=False, page_url=page.url,
            ))
            if parse_retries >= _MAX_PARSE_RETRIES:
                return _build_flow_report(
                    flow, TestResult.ERROR, verified, steps, scenarios, time.time() - start_time,
                )
            messages.append({"role": "user", "content": f"响应解析错误: {e}\n请以正确的 JSON 格式回复。"})
            continue

        action = parsed["action"]
        thinking = parsed["thinking"]

        if action == "complete":
            steps.append(FlowStepRecord(
                step_number=step_num, action="complete",
                thinking=thinking, page_url=page.url,
            ))
            return _build_flow_report(
                flow, None, verified, steps, scenarios, time.time() - start_time,
            )

        if action == "list":
            steps.append(FlowStepRecord(
                step_number=step_num, action="list",
                thinking=thinking, page_url=page.url,
            ))
            status_msg = _build_list_response(verified, flow.scenarios, scenario_descriptions)
            messages.append({"role": "user", "content": status_msg})
            continue

        if action == "verify":
            scenario_name = parsed["scenario"]
            if scenario_name not in scenarios:
                steps.append(FlowStepRecord(
                    step_number=step_num, action="verify",
                    thinking=thinking, scenario=scenario_name,
                    error=f"Unknown scenario: {scenario_name}",
                    success=False, page_url=page.url,
                ))
                available = ", ".join(flow.scenarios)
                messages.append({"role": "user", "content": f"场景 '{scenario_name}' 不存在。可用场景: {available}"})
                continue

            scenario_visit_count[scenario_name] += 1
            if scenario_visit_count[scenario_name] > 3:
                steps.append(FlowStepRecord(
                    step_number=step_num, action="verify",
                    thinking=thinking, scenario=scenario_name,
                    error="Scenario verified too many times",
                    success=False, page_url=page.url,
                ))
                return _build_flow_report(
                    flow, TestResult.ERROR, verified, steps, scenarios, time.time() - start_time,
                )

            path_taken.append(scenario_name)
            if detect_oscillation(path_taken):
                steps.append(FlowStepRecord(
                    step_number=step_num, action="verify",
                    thinking=thinking, scenario=scenario_name,
                    error="Oscillation detected",
                    success=False, page_url=page.url,
                ))
                return _build_flow_report(
                    flow, TestResult.ERROR, verified, steps, scenarios, time.time() - start_time,
                )

            try:
                vr = await _verify_scenario_impl(
                    scenarios[scenario_name], page, settings.llm, step_num,
                    flow_context=flow.context,
                )
                verified[scenario_name] = vr
                steps.append(FlowStepRecord(
                    step_number=step_num, action="verify",
                    thinking=thinking, scenario=scenario_name,
                    output=f"{'pass' if vr.passed else 'fail'}: {vr.reason}",
                    success=vr.passed, page_url=page.url,
                ))
            except Exception as e:
                steps.append(FlowStepRecord(
                    step_number=step_num, action="verify",
                    thinking=thinking, scenario=scenario_name,
                    error=f"Verification error: {e}",
                    success=False, page_url=page.url,
                ))

            reflect = build_reflect_message(verified, flow.scenarios, scenario_descriptions)
            messages.append({"role": "user", "content": reflect})
            continue

        if action == "code":
            code = parsed["code"]
            if not code.strip():
                steps.append(FlowStepRecord(
                    step_number=step_num, action="code",
                    thinking=thinking, error="Empty code",
                    success=False, page_url=page.url,
                ))
                messages.append({"role": "user", "content": "代码为空，请提供要执行的代码。"})
                continue

            result = await execute_code(
                code=code,
                page=page,
                test_data=flow.context,
                timeout=float(settings.agent.step_timeout_seconds),
                step_state=step_state,
                flow_mode=True,
            )

            steps.append(FlowStepRecord(
                step_number=step_num, action="code",
                thinking=thinking, code=code,
                output=result.output, error=result.error,
                success=result.success, page_url=page.url,
            ))

            if result.success:
                feedback = "Code executed successfully."
                if result.output:
                    out = result.output
                    if len(out) > _STDOUT_TRUNCATE:
                        out = out[:_STDOUT_TRUNCATE] + "\n...[truncated]"
                    feedback += f"\nOutput:\n{out}"
            else:
                feedback = f"Code execution failed.\nError: {result.error}"
                if result.output:
                    feedback += f"\nPartial output:\n{result.output[:_STDOUT_TRUNCATE]}"
            messages.append({"role": "user", "content": feedback})
            continue

    return _build_flow_report(
        flow, TestResult.TIMEOUT, verified, steps, scenarios, time.time() - start_time,
    )


def _build_flow_report(
    flow: Flow,
    forced_result: TestResult | None,
    verified: dict[str, VerifyResult],
    steps: list[FlowStepRecord],
    scenarios: dict[str, Scenario],
    elapsed: float,
) -> FlowReport:
    has_fail = any(not vr.passed for vr in verified.values())

    # Priority: fail > timeout > error > pass
    if has_fail:
        result = TestResult.FAIL
    elif forced_result == TestResult.TIMEOUT:
        result = TestResult.TIMEOUT
    elif forced_result == TestResult.ERROR:
        result = TestResult.ERROR
    elif forced_result is not None:
        result = forced_result
    elif not verified:
        result = TestResult.ERROR
    else:
        result = TestResult.PASS

    return FlowReport(
        flow_name=flow.name,
        result=result,
        verify_results=list(verified.values()),
        steps=steps,
        scenarios_verified=[n for n in flow.scenarios if n in verified],
        scenarios_unverified=[n for n in flow.scenarios if n not in verified],
        total_steps=len(steps),
        elapsed_seconds=round(elapsed, 2),
    )


def _build_list_response(
    verified: dict[str, VerifyResult],
    all_scenarios: list[str],
    scenario_descriptions: dict[str, str],
) -> str:
    parts = ["场景状态："]
    for name in all_scenarios:
        if name in verified:
            vr = verified[name]
            status = "pass" if vr.passed else "fail"
            parts.append(f"  [{status}] {name}: {vr.reason}")
        else:
            desc = scenario_descriptions.get(name, "")
            parts.append(f"  [未验证] {name}: {desc}")
    return "\n".join(parts)


def _trim_flow_messages(
    messages: list[dict[str, str]],
    max_pairs: int = 20,
) -> None:
    """Keep system prompt + last N user/assistant pairs."""
    if len(messages) <= 1 + max_pairs * 2:
        return
    system = messages[0]
    tail = messages[-(max_pairs * 2):]
    messages.clear()
    messages.append(system)
    messages.extend(tail)
```

Note: The imports at the top of `flow_runner.py` need to be updated. Add `from __future__ import annotations`, `from typing import TYPE_CHECKING, Any`, `from pathlib import Path`, and the `if TYPE_CHECKING: from playwright.async_api import Page` block.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_flow_runner_loop.py -v`
Expected: Both tests PASS

- [ ] **Step 5: Run all flow runner tests together**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_flow_runner.py tests/test_flow_runner_loop.py -v`
Expected: All 12 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /home/sanstoolow/immiclaw/immiclaw-test
git add immiclaw_test/flow_runner.py tests/test_flow_runner_loop.py
git commit -m "feat: add flow runner main loop with verify/code/list/complete actions"
```

---

## Task 7: Flow Reporter

**Files:**
- Modify: `immiclaw_test/reporter.py`
- Test: `tests/test_flow_reporter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_flow_reporter.py
import json
import tempfile
from pathlib import Path

from immiclaw_test.flow_models import FlowReport, FlowStepRecord, VerifyResult, AssertionResult
from immiclaw_test.models import TestResult
from immiclaw_test.reporter import print_flow_report, save_flow_report


def _sample_report() -> FlowReport:
    return FlowReport(
        flow_name="test-flow",
        result=TestResult.PASS,
        verify_results=[
            VerifyResult(
                scenario_name="sc-a",
                passed=True,
                assertions=[AssertionResult(assertion="a", satisfied=True, evidence="ok")],
                reason="All pass",
                step_number=3,
            ),
        ],
        steps=[
            FlowStepRecord(step_number=1, action="code", thinking="click", code="pass"),
            FlowStepRecord(step_number=2, action="verify", thinking="check", scenario="sc-a"),
            FlowStepRecord(step_number=3, action="complete", thinking="done"),
        ],
        scenarios_verified=["sc-a"],
        scenarios_unverified=["sc-b"],
        total_steps=3,
        elapsed_seconds=12.5,
    )


def test_print_flow_report(capsys):
    report = _sample_report()
    print_flow_report(report)
    captured = capsys.readouterr()
    assert "test-flow" in captured.out
    assert "PASS" in captured.out
    assert "sc-a" in captured.out


def test_save_flow_report():
    report = _sample_report()
    with tempfile.TemporaryDirectory() as tmp:
        path = save_flow_report(report, output_dir=Path(tmp))
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["flow_name"] == "test-flow"
        assert data["result"] == "pass"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_flow_reporter.py -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Add print_flow_report and save_flow_report to reporter.py**

Append to `immiclaw_test/reporter.py`:

```python
from .flow_models import FlowReport


def print_flow_report(report: FlowReport) -> None:
    """Print a human-readable flow report to the console."""
    color = _COLORS.get(report.result, "")
    label = report.result.value.upper()

    print()
    print(f"{'=' * 60}")
    print(f"  Flow:     {report.flow_name}")
    print(f"  Result:   {color}{label}{_RESET}")
    print(f"  Steps:    {report.total_steps}")
    print(f"  Time:     {report.elapsed_seconds:.1f}s")
    print(f"{'=' * 60}")

    if report.verify_results:
        print("\n  Verifications:")
        for vr in report.verify_results:
            status = "\033[92m✓\033[0m" if vr.passed else "\033[91m✗\033[0m"
            print(f"    {status} {vr.scenario_name}: {vr.reason[:80]}")

    if report.scenarios_verified:
        print(f"\n  Verified:   {', '.join(report.scenarios_verified)}")
    if report.scenarios_unverified:
        print(f"  Unverified: {', '.join(report.scenarios_unverified)}")
    print()


def save_flow_report(report: FlowReport, output_dir: Path | None = None) -> Path:
    """Save flow report as JSON. Returns the file path."""
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent.parent / "artifacts" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"flow-{report.flow_name}.json"
    path = output_dir / filename

    with open(path, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, ensure_ascii=False, indent=2)

    return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_flow_reporter.py -v`
Expected: Both tests PASS

- [ ] **Step 5: Commit**

```bash
cd /home/sanstoolow/immiclaw/immiclaw-test
git add immiclaw_test/reporter.py tests/test_flow_reporter.py
git commit -m "feat: add flow report printing and saving"
```

---

## Task 8: CLI Integration

**Files:**
- Modify: `main.py`
- Test: `tests/test_flow_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_flow_cli.py
import pytest

from main import parse_args


def test_parse_args_flow():
    ns = parse_args(["--flow", "new-user-journey"])
    assert ns.flow == "new-user-journey"


def test_parse_args_list_flows():
    ns = parse_args(["--list-flows"])
    assert ns.list_flows is True


def test_parse_args_flow_with_base_url():
    ns = parse_args(["--flow", "test", "--base-url", "http://example.com"])
    assert ns.flow == "test"
    assert ns.base_url == "http://example.com"


def test_parse_args_flow_mutually_exclusive_with_scenario():
    with pytest.raises(SystemExit):
        parse_args(["--flow", "test", "qmr-login"])


def test_parse_args_flow_mutually_exclusive_with_all():
    with pytest.raises(SystemExit):
        parse_args(["--flow", "test", "--all"])


def test_parse_args_flow_mutually_exclusive_with_list():
    with pytest.raises(SystemExit):
        parse_args(["--flow", "test", "--list"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_flow_cli.py -v`
Expected: FAIL (parse_args doesn't recognize `--flow`)

- [ ] **Step 3: Update main.py**

Modify `parse_args()` in `main.py` to add `--flow` and `--list-flows` arguments, and add `run_flow_cmd()` and `cmd_list_flows()` functions. Key changes:

1. Add `--flow` and `--list-flows` to argparse
2. Update mutual exclusion logic in `parse_args()`
3. Add `run_flow_cmd()` async function that loads flow config, loads skills, loads scenarios, creates browser, and calls `run_flow()`
4. Add `cmd_list_flows()` function
5. Update `main()` to dispatch to flow commands

```python
# Add to parse_args() — new arguments:
parser.add_argument(
    "--flow",
    default=None,
    metavar="FLOW",
    help="Run a flow session (name or path to flow YAML)",
)
parser.add_argument(
    "--list-flows",
    action="store_true",
    help="List available flow names under config/flows and exit",
)

# Update mutual exclusion in parse_args():
# --flow is mutually exclusive with SCENARIO, --all, --list
# --list-flows is mutually exclusive with SCENARIO, --all, --list, --flow

# Add run_flow_cmd():
async def run_flow_cmd(args: argparse.Namespace) -> int:
    _install_quiet_exception_handler()
    cfg_root = _effective_config_dir(args.config_dir)
    config_dir = Path(args.config_dir) if args.config_dir else None
    settings = load_settings(config_dir)

    if args.headless is not None:
        settings.browser.headless = args.headless == "true"
    if args.base_url:
        settings.base_url = args.base_url

    if not settings.llm.api_key:
        print("Error: LLM_API_KEY not set.")
        return 1

    from immiclaw_test.flow_config import load_flow
    from immiclaw_test.skill_loader import load_skills, assemble_skills_prompt
    from immiclaw_test.flow_runner import run_flow
    from immiclaw_test.reporter import print_flow_report, save_flow_report

    flow = load_flow(args.flow, cfg_root, base_url=settings.base_url)

    skills_dir = cfg_root / "skills"
    skills = load_skills(flow.skills, skills_dir) if flow.skills else []
    skills_prompt = assemble_skills_prompt(skills) if skills else ""

    scenarios = {}
    scenarios_dir = cfg_root / "scenarios"
    for name in flow.scenarios:
        scenario_path = resolve_scenario_path(name, cfg_root)
        scenarios[name] = load_scenario(scenario_path)

    run_dir = new_run_log_dir()
    flow_dir = run_dir / f"flow-{flow.name}"
    flow_dir.mkdir(parents=True, exist_ok=True)

    print(f"Running flow: {flow.name}")
    print(f"  Scenarios: {', '.join(flow.scenarios)}")
    print(f"  Skills: {', '.join(flow.skills) if flow.skills else '(none)'}")
    print(f"  Model: {settings.llm.model}")
    print(f"  Start: {flow.start_url.format(base_url=settings.base_url)}")
    print()

    trace_file = None
    if args.trace:
        trace_dir = Path(args.trace)
        trace_file = trace_dir / f"flow-{flow.name}-{datetime.now():%Y%m%d-%H%M%S}.zip"

    async with create_browser(settings.browser, trace_path=trace_file) as (_, _, page):
        report = await run_flow(
            flow=flow,
            scenarios=scenarios,
            page=page,
            settings=settings,
            skills_prompt=skills_prompt,
            output_dir=flow_dir,
        )

    print_flow_report(report)
    report_path = save_flow_report(report, output_dir=flow_dir)
    print(f"Report saved to: {report_path}")

    return 0 if report.result.value == "pass" else 1

# Add cmd_list_flows():
def cmd_list_flows(args: argparse.Namespace) -> int:
    cfg_root = _effective_config_dir(args.config_dir)
    flows_dir = cfg_root / "flows"
    if not flows_dir.is_dir():
        print(f"Error: flows directory not found: {flows_dir}", file=sys.stderr)
        return 1
    stems = sorted({p.stem for p in flows_dir.glob("*.yaml")} | {p.stem for p in flows_dir.glob("*.yml")})
    for stem in stems:
        print(stem)
    return 0

# Update main():
# Add dispatching for --flow and --list-flows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/test_flow_cli.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/ -v --ignore=tests/integration`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd /home/sanstoolow/immiclaw/immiclaw-test
git add main.py tests/test_flow_cli.py
git commit -m "feat: add --flow and --list-flows CLI commands"
```

---

## Task 9: Integration Smoke Test

**Files:**
- All previously created files
- Existing `config/scenarios/*.yaml`

- [ ] **Step 1: Verify sample flow YAML loads correctly**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -c "from immiclaw_test.flow_config import load_flow; from pathlib import Path; f = load_flow('new-user-journey', Path('config'), base_url='http://localhost:3000'); print(f'Flow: {f.name}, scenarios: {f.scenarios}, skills: {f.skills}')"`
Expected: Prints flow info without errors

- [ ] **Step 2: Verify --list-flows works**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python main.py --list-flows`
Expected: Prints `new-user-journey`

- [ ] **Step 3: Run full test suite one final time**

Run: `cd /home/sanstoolow/immiclaw/immiclaw-test && python -m pytest tests/ -v --ignore=tests/integration`
Expected: All tests PASS, no regressions

- [ ] **Step 4: Final commit**

```bash
cd /home/sanstoolow/immiclaw/immiclaw-test
git add -A
git commit -m "feat: complete YAML flow assembly system"
```
