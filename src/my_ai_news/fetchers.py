from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
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


def extract_published_values(entry: object) -> tuple[str, str]:
    raw_value = getattr(entry, "published", "") or getattr(entry, "updated", "") or ""

    parsed_struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed_struct:
        dt = datetime(*parsed_struct[:6], tzinfo=timezone.utc)
        return raw_value, dt.strftime("%Y-%m-%d")

    if raw_value:
        try:
            dt = parsedate_to_datetime(raw_value)
            return raw_value, dt.date().isoformat()
        except (TypeError, ValueError, IndexError):
            pass

    return raw_value, ""


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
        published_at, published_date = extract_published_values(entry)

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
                published_date=published_date,
                fetched_at=fetched_at,
                fingerprint=fingerprint,
                payload_json=payload,
            )
        )

    return items
