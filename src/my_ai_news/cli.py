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

    source_statuses = result.get("source_statuses") or []
    if source_statuses:
        failed = [item for item in source_statuses if item.get("status") != "success"]
        lines.append(f"source_success: {len(source_statuses) - len(failed)}/{len(source_statuses)}")
        if failed:
            failed_names = ", ".join(item.get("source_name", item.get("source_id", "unknown")) for item in failed[:5])
            lines.append(f"source_failed: {failed_names}")

    if result.get("publish_dir"):
        lines.append(f"publish_dir: {result['publish_dir']}")
    if result.get("status_path"):
        lines.append(f"status_path: {result['status_path']}")

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
