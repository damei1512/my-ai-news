from __future__ import annotations

import hashlib
import json
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import feedparser

from .models import RawItem, utc_now_iso


SUCCESS_STATUSES = {"success", "empty"}
DEGRADED_STATUSES = {"fallback_success", "fallback_empty"}


@dataclass(frozen=True)
class FetchResult:
    items: list[RawItem]
    status: str
    active_url: str
    attempted_urls: list[str]
    backup_urls: list[str]
    error_message: str | None = None


class SourceFetchError(Exception):
    def __init__(self, status: str, message: str, attempted_urls: list[str], backup_urls: list[str]):
        super().__init__(message)
        self.status = status
        self.message = message
        self.attempted_urls = attempted_urls
        self.backup_urls = backup_urls


def get_source_urls(source: dict) -> list[str]:
    urls = [str(url).strip() for url in source.get("urls", []) if str(url).strip()]
    if urls:
        return urls

    primary_url = str(source.get("url", "")).strip()
    backup_urls = [str(url).strip() for url in source.get("backup_urls", []) if str(url).strip()]
    deduped: list[str] = []
    for url in [primary_url, *backup_urls]:
        if url and url not in deduped:
            deduped.append(url)
    return deduped


def classify_fetch_error(exc: Exception) -> str:
    message = str(exc).lower()
    if isinstance(exc, TimeoutError) or isinstance(exc, socket.timeout) or "timed out" in message:
        return "timeout"
    if "404" in message or "410" in message or "status 4" in message:
        return "http_error"
    if "xml" in message or "parse" in message or "bozo" in message or "not well-formed" in message:
        return "parse_error"
    if "empty" in message or "invalid feed" in message:
        return "invalid_feed"
    return "unexpected_error"


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


def _fetch_from_url(source: dict, url: str) -> list[RawItem]:
    feed = feedparser.parse(url)
    bozo_exception = getattr(feed, "bozo_exception", None)
    if getattr(feed, "bozo", 0) and bozo_exception and not getattr(feed, "entries", None):
        raise ValueError(f"bozo parse error: {bozo_exception}")

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


def fetch_source(source: dict) -> FetchResult:
    urls = get_source_urls(source)
    if not urls:
        raise SourceFetchError(
            status="invalid_feed",
            message="No source URL configured",
            attempted_urls=[],
            backup_urls=[],
        )

    attempted_urls: list[str] = []
    backup_urls = urls[1:]
    last_error: Exception | None = None
    last_status = "unexpected_error"

    for index, url in enumerate(urls):
        attempted_urls.append(url)
        try:
            items = _fetch_from_url(source, url)
            used_backup = index > 0
            status = "fallback_success" if used_backup and items else "fallback_empty" if used_backup else "success" if items else "empty"
            return FetchResult(
                items=items,
                status=status,
                active_url=url,
                attempted_urls=attempted_urls,
                backup_urls=backup_urls,
                error_message=None,
            )
        except Exception as exc:
            last_error = exc
            last_status = classify_fetch_error(exc)

    raise SourceFetchError(
        status=last_status,
        message=str(last_error) if last_error else "Unknown fetch error",
        attempted_urls=attempted_urls,
        backup_urls=backup_urls,
    )
