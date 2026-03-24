"""Safe code execution engine for LLM-generated Playwright code."""

from __future__ import annotations

import ast
import asyncio
import contextlib
import io
import traceback
import warnings
from typing import TYPE_CHECKING, Any

from .models import ExecutionResult

if TYPE_CHECKING:
    from playwright.async_api import Page

_SAFE_BUILTINS = {
    "True": True,
    "False": False,
    "None": None,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "Exception": Exception,
    "AssertionError": AssertionError,
    "ValueError": ValueError,
    "TypeError": TypeError,
    "KeyError": KeyError,
    "RuntimeError": RuntimeError,
    "TimeoutError": TimeoutError,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "getattr": getattr,
    "hasattr": hasattr,
    "hash": hash,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "print": print,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
    "__import__": __import__,
}

# Names injected by the framework — never written back to step_state.
_FRAMEWORK_NAMES = frozenset({
    "__builtins__",
    "__doc__",
    "__loader__",
    "__name__",
    "__package__",
    "__spec__",
    "page",
    "test_data",
    "report_result",
    "expect",
    "asyncio",
    "re",
    "json",
})


def _compile_llm_code(code: str):
    """Compile LLM-generated source; suppress SyntaxWarning for sloppy regex string literals."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return compile(
            code,
            "<llm-generated>",
            "exec",
            ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
        )


def _close_dangling_coroutines(namespace: dict[str, Any]) -> None:
    """Close any coroutine objects left in namespace to suppress RuntimeWarning."""
    for val in list(namespace.values()):
        if asyncio.iscoroutine(val):
            val.close()


def _persist_state(
    namespace: dict[str, Any],
    step_state: dict[str, Any],
) -> None:
    """Copy user-defined variables from namespace back to step_state."""
    for key, val in namespace.items():
        if key in _FRAMEWORK_NAMES or key.startswith("__"):
            continue
        if asyncio.iscoroutine(val):
            val.close()
            continue
        step_state[key] = val


async def execute_code(
    code: str,
    page: "Page",
    test_data: dict[str, Any],
    timeout: float = 30.0,
    step_state: dict[str, Any] | None = None,
) -> ExecutionResult:
    """Execute LLM-generated async Python code in a controlled namespace.

    The generated code has access to:
    - page: Playwright Page object
    - test_data: dict from scenario YAML
    - expect: Playwright async expect() helper (same as playwright.async_api.expect)
    - report_result(passed: bool, reason: str): sync or async call to signal test completion
    - asyncio: standard asyncio module
    - print(): captured to stdout
    - re, json: safe stdlib modules

    Variables defined in one step are preserved in step_state and re-injected in the
    next step, so the LLM can reference values across steps without re-reading the page.
    """
    import json as json_mod
    import re as re_mod

    from playwright.async_api import expect as _playwright_expect

    result_holder: dict[str, Any] = {}

    async def report_result(passed: bool, reason: str = "") -> None:
        """Signal test completion. Safe to call with or without `await`."""
        result_holder["passed"] = passed
        result_holder["reason"] = reason

    namespace: dict[str, Any] = {
        "__builtins__": _SAFE_BUILTINS,
        "page": page,
        "test_data": test_data,
        "report_result": report_result,
        "expect": _playwright_expect,
        "asyncio": asyncio,
        "re": re_mod,
        "json": json_mod,
    }

    # Restore variables persisted from previous steps.
    if step_state:
        namespace.update(step_state)

    try:
        compiled = _compile_llm_code(code)
    except SyntaxError as e:
        return ExecutionResult(
            error=f"SyntaxError: {e}",
            success=False,
        )

    stdout_buf = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout_buf):
            coro_or_none = eval(compiled, namespace)  # noqa: S307
            if asyncio.iscoroutine(coro_or_none):
                await asyncio.wait_for(coro_or_none, timeout=timeout)
    except asyncio.TimeoutError:
        # Persist whatever was defined before the timeout so the next step can reuse it.
        if step_state is not None:
            _persist_state(namespace, step_state)
        else:
            _close_dangling_coroutines(namespace)
        return ExecutionResult(
            output=stdout_buf.getvalue(),
            error=f"Code execution timed out after {timeout}s",
            success=False,
        )
    except Exception as e:
        tb = traceback.format_exc()
        # Persist whatever was defined before the exception so the next step can reuse it.
        if step_state is not None:
            _persist_state(namespace, step_state)
        else:
            _close_dangling_coroutines(namespace)
        return ExecutionResult(
            output=stdout_buf.getvalue(),
            error=f"{type(e).__name__}: {e}\n{tb}",
            success=False,
        )

    # Persist user-defined variables for future steps and clean up coroutines.
    if step_state is not None:
        _persist_state(namespace, step_state)
    else:
        _close_dangling_coroutines(namespace)

    return ExecutionResult(
        output=stdout_buf.getvalue(),
        success=True,
        reported=result_holder if result_holder else None,
    )
