from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlparse

import feedparser

from .models import RawItem, utc_now_iso


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    canonical = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return canonical.rstrip("/")


def fingerprint_text(title: str, summary: str) -> str:
    text = f"{title} {summary}".lower()
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def extract_image(entry: object) -> str:
    media_content = getattr(entry, "media_content", None)
    if media_content:
        for media in media_content:
            image_url = media.get("url")
            if image_url:
                return image_url

    links = getattr(entry, "links", [])
    for link in links:
        if link.get("type", "").startswith("image/"):
            return link.get("href", "")
    return ""


def fetch_source(source: dict) -> list[RawItem]:
    feed = feedparser.parse(source["url"])
    fetched_at = utc_now_iso()
    items: list[RawItem] = []

    for entry in feed.entries[:10]:
        title = getattr(entry, "title", "").strip()
        url = getattr(entry, "link", "").strip()
        summary = getattr(entry, "summary", "")[:2000]
        canonical_url = canonicalize_url(url) if url else ""
        fingerprint = fingerprint_text(title, summary)
        payload = json.dumps(dict(entry), ensure_ascii=False)
        published_at = getattr(entry, "published", "") or getattr(entry, "updated", "")

        if not title or not url:
            continue

        items.append(
            RawItem(
                source_id=source["id"],
                source_name=source["name"],
                category=source["category"],
                title=title,
                url=url,
                canonical_url=canonical_url,
                summary=summary,
                image_url=extract_image(entry),
                published_at=published_at,
                fetched_at=fetched_at,
                fingerprint=fingerprint,
                payload_json=payload,
            )
        )

    return items
