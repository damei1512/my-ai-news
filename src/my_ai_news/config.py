from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    timezone: str
    database_path: Path
    publish_dir: Path
    status_path: Path
    source_health_path: Path
    source_config: Path
    x_config: Path
    x_digest_path: Path
    llm_enabled: bool
    llm_provider: str
    llm_model: str
    llm_base_url: str | None
    llm_base_urls: list[str]
    llm_api_key: str | None


def _parse_list_env(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _normalize_source(source: dict) -> dict:
    normalized = dict(source)
    primary_url = str(normalized.get("url", "")).strip()
    backup_urls = [str(url).strip() for url in normalized.get("backup_urls", []) if str(url).strip()]
    configured_urls = [str(url).strip() for url in normalized.get("urls", []) if str(url).strip()]

    urls = _dedupe_preserve_order([
        *([primary_url] if primary_url else []),
        *configured_urls,
        *backup_urls,
    ])

    if not primary_url and urls:
        primary_url = urls[0]
    if primary_url and primary_url not in urls:
        urls.insert(0, primary_url)

    normalized["url"] = primary_url
    normalized["urls"] = urls
    normalized["backup_urls"] = [url for url in urls if url != primary_url]
    return normalized


def load_config(project_root: Path) -> AppConfig:
    load_dotenv(project_root / ".env")

    timezone = os.getenv("TIMEZONE", "Asia/Shanghai")
    database_path = project_root / os.getenv("DATABASE_PATH", "data/app.db")
    publish_dir = project_root / os.getenv("PUBLISH_DIR", "public/data")
    status_path = project_root / os.getenv("STATUS_PATH", "public/data/status.json")
    source_health_path = project_root / os.getenv("SOURCE_HEALTH_PATH", "public/data/source-health.json")
    source_config = project_root / os.getenv("SOURCE_CONFIG", "config/sources.json")
    x_config = project_root / os.getenv("X_CONFIG", "config/x_accounts.json")
    x_digest_path = project_root / os.getenv("X_DIGEST_PATH", "public/data/x-digest.json")
    llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or None
    llm_enabled_raw = os.getenv("LLM_ENABLED")
    llm_enabled = (llm_enabled_raw.lower() == "true") if llm_enabled_raw is not None else bool(llm_api_key)
    llm_provider = os.getenv("LLM_PROVIDER", "deepseek")
    llm_model = os.getenv("LLM_MODEL", "deepseek-chat")
    llm_base_url = os.getenv("LLM_BASE_URL") or None
    llm_base_urls = _dedupe_preserve_order([
        *([llm_base_url] if llm_base_url else []),
        *_parse_list_env(os.getenv("LLM_BASE_URLS")),
    ])
    if not llm_base_url and llm_base_urls:
        llm_base_url = llm_base_urls[0]

    return AppConfig(
        timezone=timezone,
        database_path=database_path,
        publish_dir=publish_dir,
        status_path=status_path,
        source_health_path=source_health_path,
        source_config=source_config,
        x_config=x_config,
        x_digest_path=x_digest_path,
        llm_enabled=llm_enabled,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_base_url=llm_base_url,
        llm_base_urls=llm_base_urls,
        llm_api_key=llm_api_key,
    )


def load_sources(config_path: Path) -> list[dict]:
    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [_normalize_source(source) for source in payload.get("sources", []) if source.get("enabled", True)]


def load_x_accounts(config_path: Path) -> list[dict]:
    if not config_path.exists():
        return []
    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [dict(account) for account in payload.get("accounts", []) if account.get("enabled", True)]
