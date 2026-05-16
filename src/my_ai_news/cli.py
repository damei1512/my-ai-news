from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_config
from .pipeline import run_pipeline


def format_run_summary(result: dict) -> str:
    lines = [
        f"run_id: {result.get('run_id')}",
        f"status: {result.get('status', 'unknown')}",
        f"sources: {result.get('sources', 0)}",
        f"raw_items: {result.get('raw_items', 0)}",
        f"stories: {result.get('stories', 0)}",
    ]

    llm = result.get("llm") or {}
    if llm:
        lines.append(f"llm_status: {llm.get('status', 'unknown')}")
        degraded_items = llm.get("degraded_items")
        if degraded_items:
            lines.append(f"llm_degraded_items: {degraded_items}")

    x_digest = result.get("x_digest") or {}
    if x_digest:
        lines.append(f"x_digest_items: {x_digest.get('items', 0)}")
        if x_digest.get("path"):
            lines.append(f"x_digest_path: {x_digest['path']}")

    source_statuses = result.get("source_statuses") or []
    if source_statuses:
        success_statuses = {"success", "empty"}
        degraded_statuses = {"fallback_success", "fallback_empty"}
        failed = [item for item in source_statuses if item.get("status") not in success_statuses | degraded_statuses]
        degraded = [item for item in source_statuses if item.get("status") in degraded_statuses]
        healthy_count = len(source_statuses) - len(failed) - len(degraded)
        lines.append(f"source_success: {healthy_count}/{len(source_statuses)}")
        if degraded:
            degraded_names = ", ".join(item.get("source_name", item.get("source_id", "unknown")) for item in degraded[:5])
            lines.append(f"source_degraded: {degraded_names}")
        if failed:
            failed_names = ", ".join(item.get("source_name", item.get("source_id", "unknown")) for item in failed[:5])
            lines.append(f"source_failed: {failed_names}")

    if result.get("publish_dir"):
        lines.append(f"publish_dir: {result['publish_dir']}")
    if result.get("status_path"):
        lines.append(f"status_path: {result['status_path']}")
    if result.get("source_health_path"):
        lines.append(f"source_health_path: {result['source_health_path']}")

    return "\n".join(lines)


def load_status(project_root: Path) -> dict:
    config = load_config(project_root)
    if not config.status_path.exists():
        raise FileNotFoundError(f"status file not found: {config.status_path}")
    return json.loads(config.status_path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run or inspect the my-ai-news pipeline.")
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print the latest pipeline status from public/data/status.json.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of the human summary.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    project_root = Path(__file__).resolve().parents[2]

    if args.status:
        payload = load_status(project_root)
    else:
        payload = run_pipeline(project_root)

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(format_run_summary(payload))

    return 0
