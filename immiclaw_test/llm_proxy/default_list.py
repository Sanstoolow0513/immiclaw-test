"""固定行为：列举全部提供者并写入 artifacts/llm-list.json。"""

from __future__ import annotations

import json
import sys

from dotenv import load_dotenv

from .config_loader import effective_proxy_host, load_providers
from .runner import run_list_all
from .settings import project_root

DEFAULT_TIMEOUT = 60.0


def main_llm_list() -> int:
    root = project_root()
    env_path = root / ".env"
    if env_path.is_file():
        load_dotenv(env_path)

    cfg = load_providers()
    host = effective_proxy_host(None, cfg)
    data = run_list_all(
        host,
        None,
        DEFAULT_TIMEOUT,
        cfg,
        include_raw=False,
    )

    out_dir = root / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "llm-list.json"
    try:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        print(f"Error: cannot write {path}: {e}", file=sys.stderr)
        return 1

    print(path.resolve())
    return 0
