from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .models import Story


WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def week_label(story_date: str) -> str:
    try:
        weekday = datetime.strptime(story_date, "%Y-%m-%d").weekday()
        return WEEKDAYS[weekday]
    except ValueError:
        return ""


def build_archive(stories: list[Story]) -> dict:
    archive: dict[str, dict] = defaultdict(lambda: {"week": "", "articles": []})

    for story in stories:
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


def publish(stories: list[Story], publish_dir: Path) -> None:
    publish_dir.mkdir(parents=True, exist_ok=True)
    daily_dir = publish_dir / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    archive = build_archive(stories)

    with (publish_dir / "latest.json").open("w", encoding="utf-8") as handle:
        json.dump(archive, handle, ensure_ascii=False, indent=2)

    for story_date, payload in archive.items():
        with (daily_dir / f"{story_date}.json").open("w", encoding="utf-8") as handle:
            json.dump({story_date: payload}, handle, ensure_ascii=False, indent=2)
