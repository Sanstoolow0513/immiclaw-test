from __future__ import annotations

import json

from immiclaw_test.llm import parse_llm_response


def test_parse_llm_response_accepts_status_payloads() -> None:
    for status in ["continue", "final_pass", "final_fail"]:
        payload = {
            "thinking": f"status={status}",
            "code": "print('hello')",
            "status": status,
            "evidence": {
                "points": ["p1", "p2"],
                "screenshot_required": status == "final_fail",
            },
            "final": {
                "passed": status == "final_pass",
                "reason": "done",
            },
        }

        parsed = parse_llm_response(json.dumps(payload))

        assert parsed == {
            "thinking": payload["thinking"],
            "code": payload["code"],
        }


def test_parse_llm_response_handles_markdown_fenced_json() -> None:
    response = """```json
{"thinking": "next step", "code": "print('ok')"}
```"""

    parsed = parse_llm_response(response)

    assert parsed == {
        "thinking": "next step",
        "code": "print('ok')",
    }
