"""Compile-time behavior for LLM-generated code."""

from __future__ import annotations

import warnings

import pytest

from immiclaw_test.executor import _compile_llm_code


def test_compile_llm_code_suppresses_invalid_escape_syntax_warning() -> None:
    """Models often emit re.compile('...\\s...') without raw strings; avoid stderr noise."""
    code = "import re\nre.compile('Markdown\\s*编辑器')\n"
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        _compile_llm_code(code)
    bad = [w for w in recorded if issubclass(w.category, SyntaxWarning)]
    assert not bad


def test_compile_llm_code_syntax_error_still_raises() -> None:
    with pytest.raises(SyntaxError):
        _compile_llm_code("def oops(")
