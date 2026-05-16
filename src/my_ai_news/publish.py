from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .models import Story


WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def is_valid_story_date(value: str) -> bool:
    if not DATE_RE.match(value):
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def week_label(story_date: str) -> str:
    try:
        weekday = datetime.strptime(story_date, "%Y-%m-%d").weekday()
        return WEEKDAYS[weekday]
    except ValueError:
        return ""


def build_archive(stories: list[Story]) -> dict:
    archive: dict[str, dict] = defaultdict(lambda: {"week": "", "articles": []})

    for story in stories:
        if not is_valid_story_date(story.story_date):
            continue
        if not archive[story.story_date]["week"]:
            archive[story.story_date]["week"] = week_label(story.story_date)
        archive[story.story_date]["articles"].append(
            {
                "category": story.category,
                "tag": story.tags[0] if story.tags else story.source_name,
                "title": story.title,
                "link": story.url,
                "summary": story.summary,
                "comment": story.commentary,
                "image": story.image_url,
                "score": story.score,
            }
        )

    return dict(sorted(archive.items(), reverse=True))


def clean_invalid_daily_files(daily_dir: Path) -> None:
    for path in daily_dir.glob("*.json"):
        if not is_valid_story_date(path.stem):
            path.unlink()


def publish(stories: list[Story], publish_dir: Path) -> None:
    publish_dir.mkdir(parents=True, exist_ok=True)
    daily_dir = publish_dir / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    clean_invalid_daily_files(daily_dir)

    archive = build_archive(stories)

    with (publish_dir / "latest.json").open("w", encoding="utf-8") as handle:
        json.dump(archive, handle, ensure_ascii=False, indent=2)

    for story_date, payload in archive.items():
        with (daily_dir / f"{story_date}.json").open("w", encoding="utf-8") as handle:
            json.dump({story_date: payload}, handle, ensure_ascii=False, indent=2)
