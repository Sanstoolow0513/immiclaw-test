"""经代理执行 list + probe 可用性测试，写入 ``artifacts/llm-test.json``。"""

from __future__ import annotations

import json
import sys
from typing import Any

from dotenv import load_dotenv

from .config_loader import effective_proxy_host, load_providers
from .runner import run_list_all, run_probe_all
from .settings import project_root

DEFAULT_TIMEOUT = 60.0
ARTIFACT_NAME = "llm-test.json"


def _all_probe_ok(probe_out: dict[str, Any]) -> bool:
    """非 skipped 的提供者须 list 与 probe 均成功。"""
    for r in probe_out.get("results", []):
        if r.get("skipped"):
            continue
        lst = r.get("list")
        if not isinstance(lst, dict) or not lst.get("ok"):
            return False
        pr = r.get("probe")
        if pr is None or not isinstance(pr, dict) or not pr.get("ok"):
            return False
    return True


def main() -> int:
    root = project_root()
    env_path = root / ".env"
    if env_path.is_file():
        load_dotenv(env_path)

    cfg = load_providers()
    host = effective_proxy_host(None, cfg)

    list_out = run_list_all(
        host, None, DEFAULT_TIMEOUT, cfg, include_raw=False
    )
    probe_out = run_probe_all(
        host, None, DEFAULT_TIMEOUT, None, cfg, include_raw=False
    )

    payload: dict[str, Any] = {
        "proxy_host": host,
        "timeout_seconds": DEFAULT_TIMEOUT,
        "list": list_out,
        "probe": probe_out,
    }

    out_dir = root / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / ARTIFACT_NAME
    try:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        print(f"Error: cannot write {path}: {e}", file=sys.stderr)
        return 1

    print(path.resolve())

    if not _all_probe_ok(probe_out):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
