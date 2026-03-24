"""Agent feedback shaping."""

from __future__ import annotations

from immiclaw_test.agent import _truncate_feedback_stdout


def test_truncate_feedback_stdout_untouched_when_short() -> None:
    s = "hello"
    assert _truncate_feedback_stdout(s, max_chars=100) == s


def test_truncate_feedback_stdout_adds_notice() -> None:
    s = "x" * 100
    out = _truncate_feedback_stdout(s, max_chars=20)
    assert out.startswith("x" * 20)
    assert "truncated" in out
