from __future__ import annotations

from immiclaw_test.executor import execute_code


async def test_execute_code_runs_simple_code_successfully(mock_page) -> None:
    result = await execute_code(
        code="x = 1 + 1\nprint(x)",
        page=mock_page,
        test_data={},
    )

    assert result.success is True
    assert result.error is None
    assert result.output == "2\n"
    assert result.reported is None


async def test_execute_code_captures_stdout(mock_page) -> None:
    result = await execute_code(
        code="print('first')\nprint('second')",
        page=mock_page,
        test_data={},
    )

    assert result.success is True
    assert result.output == "first\nsecond\n"


async def test_execute_code_injects_test_data(mock_page) -> None:
    result = await execute_code(
        code="print(test_data['username'])",
        page=mock_page,
        test_data={"username": "alice"},
    )

    assert result.success is True
    assert result.output == "alice\n"


async def test_execute_code_returns_runtime_errors(mock_page) -> None:
    result = await execute_code(
        code="print(1 / 0)",
        page=mock_page,
        test_data={},
    )

    assert result.success is False
    assert result.error is not None
    assert "ZeroDivisionError" in result.error
    assert "Traceback" in result.error


async def test_execute_code_captures_report_result(mock_page) -> None:
    result = await execute_code(
        code="report_result(True, 'all assertions met')",
        page=mock_page,
        test_data={},
    )

    assert result.success is True
    assert result.reported == {
        "passed": True,
        "reason": "all assertions met",
    }


async def test_execute_code_does_not_persist_state_across_calls(mock_page) -> None:
    first = await execute_code(
        code="global marker\nmarker = 'set in previous step'",
        page=mock_page,
        test_data={},
    )
    second = await execute_code(
        code="print(marker)",
        page=mock_page,
        test_data={},
    )

    assert first.success is True
    assert second.success is False
    assert second.error is not None
    assert "NameError" in second.error
