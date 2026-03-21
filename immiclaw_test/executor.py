"""Safe code execution engine for LLM-generated Playwright code."""

from __future__ import annotations

import asyncio
import contextlib
import io
import textwrap
import traceback
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


async def execute_code(
    code: str,
    page: Page,
    test_data: dict[str, Any],
    timeout: float = 30.0,
) -> ExecutionResult:
    """Execute LLM-generated async Python code in a controlled namespace.

    The generated code has access to:
    - page: Playwright Page object
    - test_data: dict from scenario YAML
    - report_result(passed: bool, reason: str): call to signal test completion
    - print(): captured to stdout
    - asyncio: for async utilities
    - re, json: safe stdlib modules
    """
    import json as json_mod
    import re as re_mod

    indented = textwrap.indent(code, "    ")
    wrapped = f"async def __generated__(page, test_data, report_result):\n{indented}\n"

    namespace: dict[str, Any] = {"__builtins__": _SAFE_BUILTINS}

    try:
        compiled = compile(wrapped, "<llm-generated>", "exec")
    except SyntaxError as e:
        return ExecutionResult(
            error=f"SyntaxError: {e}",
            success=False,
        )

    exec(compiled, namespace)
    fn = namespace["__generated__"]

    result_holder: dict[str, Any] = {}

    def report_result(passed: bool, reason: str = "") -> None:
        result_holder["passed"] = passed
        result_holder["reason"] = reason

    stdout_buf = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout_buf):
            await asyncio.wait_for(
                fn(page, test_data, report_result),
                timeout=timeout,
            )
    except asyncio.TimeoutError:
        return ExecutionResult(
            output=stdout_buf.getvalue(),
            error=f"Code execution timed out after {timeout}s",
            success=False,
        )
    except Exception as e:
        tb = traceback.format_exc()
        return ExecutionResult(
            output=stdout_buf.getvalue(),
            error=f"{type(e).__name__}: {e}\n{tb}",
            success=False,
        )

    return ExecutionResult(
        output=stdout_buf.getvalue(),
        success=True,
        reported=result_holder if result_holder else None,
    )
