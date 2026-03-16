#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from my_ai_news.config import load_config


def print_check(label: str, status: str, detail: str) -> None:
    print(f"[{status}] {label}: {detail}")


def main() -> int:
    config = load_config(PROJECT_ROOT)
    failures = 0

    print_check("project_root", "OK", str(PROJECT_ROOT))

    source_status = "OK" if config.source_config.exists() else "FAIL"
    print_check("source_config", source_status, str(config.source_config))
    if source_status == "FAIL":
        failures += 1

    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "update-site-data.yml"
    workflow_status = "OK" if workflow_path.exists() else "FAIL"
    print_check("workflow", workflow_status, str(workflow_path))
    if workflow_status == "FAIL":
        failures += 1

    env_path = PROJECT_ROOT / ".env"
    print_check(".env", "OK" if env_path.exists() else "WARN", str(env_path))
    print_check("publish_dir", "OK", str(config.publish_dir))
    print_check("status_path", "OK", str(config.status_path))

    if config.llm_enabled and not config.llm_api_key:
        print_check("llm", "FAIL", "LLM_ENABLED=true but no API key was found")
        failures += 1
    elif config.llm_enabled:
        print_check("llm", "OK", f"enabled with model {config.llm_model}")
    else:
        print_check("llm", "OK", "fallback mode")

    if failures:
        print(f"\nSetup check failed with {failures} blocking issue(s).")
        return 1

    print("\nSetup check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
