from __future__ import annotations

import html
import re
from collections import OrderedDict
from datetime import datetime

from .ai import AIEnricher
from .models import RawItem, Story


CATEGORY_LABELS = {
    "ai": "人工智能",
    "tech": "数码科技",
    "games": "游戏影视",
    "world": "时事热点",
}


def strip_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = html.unescape(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def deduplicate(items: list[RawItem]) -> list[RawItem]:
    unique_by_url: OrderedDict[str, RawItem] = OrderedDict()
    seen_fingerprints: set[str] = set()

    for item in items:
        if item.canonical_url in unique_by_url:
            continue
        if item.fingerprint in seen_fingerprints:
            continue
        unique_by_url[item.canonical_url] = item
        seen_fingerprints.add(item.fingerprint)

    return list(unique_by_url.values())


def score_item(item: RawItem, source_priority: int) -> int:
    score = source_priority
    if item.image_url:
        score += 5
    if item.summary:
        score += 5
    return min(score, 100)


def story_date_from_item(item: RawItem) -> str:
    if item.published_at:
        return item.published_at[:10]
    return datetime.utcnow().strftime("%Y-%m-%d")


def fallback_summary(item: RawItem) -> str:
    clean_summary = strip_html(item.summary)[:180]
    return clean_summary or "暂无摘要"


def to_story(item: RawItem, source_priority: int, enricher: AIEnricher) -> Story:
    clean_summary = strip_html(item.summary)[:180]
    category = CATEGORY_LABELS.get(item.category, item.category)
    enrichment = enricher.enrich(
        category=category,
        source_name=item.source_name,
        title=strip_html(item.title),
        summary=clean_summary,
        url=item.url,
    )
    return Story(
        source_id=item.source_id,
        source_name=item.source_name,
        category=category,
        tags=enrichment.tags[:3] or [item.source_name],
        title=enrichment.title,
        url=item.url,
        summary=enrichment.summary or fallback_summary(item),
        commentary=enrichment.commentary,
        image_url=item.image_url,
        score=min(100, score_item(item, source_priority) + enrichment.score_delta),
        published_at=item.published_at,
        story_date=story_date_from_item(item),
    )
