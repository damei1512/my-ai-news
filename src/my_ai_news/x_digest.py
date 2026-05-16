from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urlparse

import feedparser
from openai import OpenAI

from .config import AppConfig, load_x_accounts
from .fetchers import canonicalize_url
from .models import utc_now_iso
from .processing import strip_html


@dataclass(frozen=True)
class XPost:
    account_id: str
    handle: str
    author_name: str
    role: str
    avatar_url: str
    original_text: str
    zh_text: str
    commentary: str
    media_urls: list[str]
    url: str
    canonical_url: str
    published_at: str
    published_date: str
    kind: str
    score: int

    def to_dict(self) -> dict:
        return asdict(self)


def contains_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def normalize_post_text(value: str) -> str:
    text = strip_html(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class ImageExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "img":
            return
        values = {key: value or "" for key, value in attrs}
        src = values.get("src", "").strip()
        if src and src not in self.urls:
            self.urls.append(src)


def extract_image_urls(value: str) -> list[str]:
    parser = ImageExtractor()
    parser.feed(value or "")
    return parser.urls


def feed_avatar_url(feed: object) -> str:
    if isinstance(feed, dict):
        image = feed.get("image")
    else:
        image = getattr(feed, "image", None)
    if isinstance(image, dict):
        return str(image.get("href", "")).strip()
    return str(getattr(image, "href", "") or "").strip()


def x_url_from_handle(handle: str) -> str:
    return f"https://x.com/{handle.lstrip('@')}"


def build_account_feed_urls(account: dict) -> list[str]:
    urls = [str(url).strip() for url in account.get("rss_urls", []) if str(url).strip()]
    direct_url = str(account.get("rss_url", "")).strip()
    if direct_url:
        urls.insert(0, direct_url)

    base_url = os.getenv("X_RSS_BASE_URL", "").strip().rstrip("/")
    handle = str(account.get("handle", "")).strip().lstrip("@")
    if base_url and handle:
        urls.append(f"{base_url}/twitter/user/{quote(handle)}")

    deduped: list[str] = []
    for url in urls:
        if url not in deduped:
            deduped.append(url)
    return deduped


def published_values(entry: object) -> tuple[str, str]:
    raw_value = getattr(entry, "published", "") or getattr(entry, "updated", "") or ""
    parsed_struct = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed_struct:
        dt = datetime(*parsed_struct[:6], tzinfo=timezone.utc)
        return raw_value, dt.date().isoformat()
    if raw_value:
        try:
            dt = parsedate_to_datetime(raw_value)
            return raw_value, dt.date().isoformat()
        except (TypeError, ValueError, IndexError):
            pass
    return raw_value, ""


def classify_kind(text: str) -> str:
    lowered = text.lower()
    if lowered.startswith("rt @") or "retweeted" in lowered or "转推" in text:
        return "repost"
    if lowered.startswith("@") or "回复" in text:
        return "reply"
    return "post"


def fallback_translation(text: str) -> tuple[str, str]:
    if contains_cjk(text):
        return text, ""
    return "", ""


class XPostTranslator:
    def __init__(self, config: AppConfig):
        self.enabled = config.llm_enabled and bool(config.llm_api_key)
        self.model = config.llm_model
        self.client: OpenAI | None = None
        if self.enabled:
            client_kwargs = {"api_key": config.llm_api_key}
            if config.llm_base_url:
                client_kwargs["base_url"] = config.llm_base_url
            self.client = OpenAI(**client_kwargs)

    def translate(self, *, author_name: str, text: str) -> tuple[str, str]:
        if not self.client:
            return fallback_translation(text)

        prompt = f"""
请把 X 上的这条动态翻译并整理为严格 JSON。

要求：
1. zh_text: 忠实中文翻译，保留产品名、人名、机构名；如果原文已是中文，可以润色但不要改意。
2. 输出 JSON object，不要 Markdown。

author={author_name}
text={text}
""".strip()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是克制准确的中英双语科技编辑。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = (response.choices[0].message.content or "{}").strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        payload = json.loads(content.strip())
        zh_text = str(payload.get("zh_text", "")).strip()
        return zh_text or fallback_translation(text)[0], ""


def fetch_account_posts(account: dict, translator: XPostTranslator, limit: int) -> tuple[list[XPost], dict]:
    urls = build_account_feed_urls(account)
    handle = str(account.get("handle", "")).strip().lstrip("@")
    status = {
        "account_id": account.get("id", handle),
        "handle": handle,
        "name": account.get("name", handle),
        "status": "not_configured",
        "items_fetched": 0,
        "active_url": None,
        "attempted_urls": urls,
        "error_message": None,
    }
    if not urls:
        status["error_message"] = "No rss_url configured and X_RSS_BASE_URL is empty"
        return [], status

    last_error = ""
    for url in urls:
        feed = feedparser.parse(url)
        entries = getattr(feed, "entries", []) or []
        if not entries:
            last_error = str(getattr(feed, "bozo_exception", "")) or "empty feed"
            continue

        posts: list[XPost] = []
        avatar_url = feed_avatar_url(getattr(feed, "feed", {}))
        for entry in entries[:limit]:
            summary_html = getattr(entry, "summary", "") or getattr(entry, "title", "")
            raw_text = normalize_post_text(summary_html)
            if not raw_text:
                continue
            link = str(getattr(entry, "link", "")).strip() or x_url_from_handle(handle)
            published_at, published_date = published_values(entry)
            try:
                zh_text, commentary = translator.translate(author_name=str(account.get("name", handle)), text=raw_text)
            except Exception:
                zh_text, commentary = fallback_translation(raw_text)

            posts.append(
                XPost(
                    account_id=str(account.get("id", handle)),
                    handle=handle,
                    author_name=str(account.get("name", handle)),
                    role=str(account.get("role", "")),
                    avatar_url=avatar_url,
                    original_text=raw_text,
                    zh_text=zh_text,
                    commentary=commentary,
                    media_urls=extract_image_urls(summary_html),
                    url=link,
                    canonical_url=canonicalize_url(link) if urlparse(link).scheme else link,
                    published_at=published_at,
                    published_date=published_date,
                    kind=classify_kind(raw_text),
                    score=int(account.get("priority", 50)),
                )
            )

        status.update({"status": "success" if posts else "empty", "items_fetched": len(posts), "active_url": url, "error_message": None})
        return posts, status

    status.update({"status": "fetch_error", "error_message": last_error})
    return [], status


def publish_x_digest(posts: list[XPost], statuses: list[dict], output_path: Path) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    deduped: dict[str, XPost] = {}
    for post in posts:
        deduped.setdefault(post.canonical_url or post.url, post)

    sorted_posts = sorted(
        deduped.values(),
        key=lambda item: (item.published_date, item.score),
        reverse=True,
    )
    payload = {
        "generated_at": utc_now_iso(),
        "total": len(sorted_posts),
        "items": [post.to_dict() for post in sorted_posts[:50]],
        "accounts": statuses,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def run_x_digest(config: AppConfig, *, per_account_limit: int = 3) -> dict:
    accounts = load_x_accounts(config.x_config)
    translator = XPostTranslator(config)
    all_posts: list[XPost] = []
    statuses: list[dict] = []

    for account in accounts:
        posts, status = fetch_account_posts(account, translator, per_account_limit)
        all_posts.extend(posts)
        statuses.append(status)

    return publish_x_digest(all_posts, statuses, config.x_digest_path)
