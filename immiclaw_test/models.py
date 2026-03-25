"""Data models for tasks, configuration, and execution reports."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TestResult(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    TIMEOUT = "timeout"
    ERROR = "error"


class LLMConfig(BaseModel):
    model: str = "gpt-4o"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    temperature: float = 0.0


class ViewportConfig(BaseModel):
    width: int = 1280
    height: int = 720


class BrowserConfig(BaseModel):
    headless: bool = True
    viewport: ViewportConfig = Field(default_factory=ViewportConfig)


class AgentConfig(BaseModel):
    max_steps: int = 30
    step_timeout_seconds: int = 30
    screenshot_on_failure: bool = True


class Settings(BaseModel):
    base_url: str = "http://localhost:3000"
    llm: LLMConfig = Field(default_factory=LLMConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)


class Skill(BaseModel):
    name: str
    type: str  # "operation" | "strategy"
    description: str
    prompt: str
    applies_to: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)


class TaskSubtask(BaseModel):
    name: str
    goal: str
    done_when: list[str] = Field(default_factory=list)
    optional: bool = False


class Task(BaseModel):
    name: str
    description: str
    start_url: str
    goal: str
    done_when: list[str] = Field(default_factory=list)
    subtasks: list[TaskSubtask] = Field(default_factory=list)
    preset: str = ""
    skills: list[str] = Field(default_factory=list)
    max_steps: int = 30
    timeout_seconds: int = 120
    test_data: dict[str, Any] = Field(default_factory=dict)


class StepRecord(BaseModel):
    step_number: int
    code: str = ""
    thinking: str = ""
    output: str = ""
    error: str | None = None
    success: bool = True
    page_url: str | None = None


class ExecutionResult(BaseModel):
    output: str = ""
    error: str | None = None
    success: bool = True
    reported: dict[str, Any] | None = None


class TaskReport(BaseModel):
    task_name: str
    result: TestResult
    reason: str = ""
    total_steps: int = 0
    elapsed_seconds: float = 0.0
    steps: list[StepRecord] = Field(default_factory=list)
    completed_subtasks: list[str] = Field(default_factory=list)
    screenshots: list[str] = Field(default_factory=list)
