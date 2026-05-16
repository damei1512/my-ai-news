from __future__ import annotations

import hashlib
import html
import json
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

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


class ArticleListParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.articles: list[dict] = []
        self._current: dict | None = None
        self._in_title = False
        self._in_summary = False
        self._title_parts: list[str] = []
        self._summary_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        classes = set(values.get("class", "").split())

        if tag == "article" and "article-item__container" in classes:
            self._current = {"href": "", "image": "", "image_alt": ""}
            self._title_parts = []
            self._summary_parts = []
            return

        if self._current is None:
            return

        href = values.get("href", "")
        if tag == "a" and "/articles/" in href:
            self._current["href"] = self._current.get("href") or urljoin(self.base_url, href)
            if "article-item__title" in classes:
                self._in_title = True
                self._title_parts = []
            return

        if tag == "img" and not self._current.get("image"):
            src = values.get("src", "")
            if src:
                self._current["image"] = urljoin(self.base_url, src)
            self._current["image_alt"] = values.get("alt", "")

        if tag == "p" and "article-item__summary" in classes:
            self._in_summary = True
            self._summary_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        if self._in_summary:
            self._summary_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_title:
            self._in_title = False
        if tag == "p" and self._in_summary:
            self._in_summary = False
        if tag == "article" and self._current is not None:
            title = normalize_text("".join(self._title_parts)) or normalize_text(self._current.get("image_alt", ""))
            href = self._current.get("href", "")
            if title and href:
                self.articles.append(
                    {
                        "title": title,
                        "url": href,
                        "summary": normalize_text("".join(self._summary_parts)),
                        "image_url": self._current.get("image", ""),
                    }
                )
            self._current = None


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def published_date_from_url(url: str) -> str:
    match = re.search(r"/articles/(\d{4}-\d{2}-\d{2})", url)
    return match.group(1) if match else ""


def _fetch_html_listing(source: dict, url: str) -> list[RawItem]:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; my-ai-news/1.0)"})
    with urlopen(request, timeout=20) as response:
        content = response.read().decode("utf-8", "replace")

    parser = ArticleListParser(url)
    parser.feed(content)

    fetched_at = utc_now_iso()
    items: list[RawItem] = []
    seen_urls: set[str] = set()
    for entry in parser.articles[:10]:
        item_url = entry["url"].strip()
        if not item_url or item_url in seen_urls:
            continue
        seen_urls.add(item_url)
        title = entry["title"].strip()
        summary = entry["summary"].strip()
        published_date = published_date_from_url(item_url)

        items.append(
            RawItem(
                source_id=source["id"],
                source_name=source["name"],
                category=source["category"],
                title=title,
                url=item_url,
                canonical_url=canonicalize_url(item_url),
                summary=summary,
                image_url=entry.get("image_url", ""),
                published_at=published_date,
                published_date=published_date,
                fetched_at=fetched_at,
                fingerprint=fingerprint_text(title, summary),
                payload_json=json.dumps(entry, ensure_ascii=False),
            )
        )

    if not items:
        raise ValueError("empty html listing")
    return items


def _fetch_from_url(source: dict, url: str) -> list[RawItem]:
    if source.get("type") == "html":
        return _fetch_html_listing(source, url)

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
