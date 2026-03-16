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
    source_config: Path
    llm_enabled: bool
    llm_provider: str
    llm_model: str
    llm_base_url: str | None
    llm_api_key: str | None


def load_config(project_root: Path) -> AppConfig:
    load_dotenv(project_root / ".env")

    timezone = os.getenv("TIMEZONE", "Asia/Shanghai")
    database_path = project_root / os.getenv("DATABASE_PATH", "data/app.db")
    publish_dir = project_root / os.getenv("PUBLISH_DIR", "public/data")
    status_path = project_root / os.getenv("STATUS_PATH", "public/data/status.json")
    source_config = project_root / os.getenv("SOURCE_CONFIG", "config/sources.json")
    llm_api_key = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or None
    llm_enabled_raw = os.getenv("LLM_ENABLED")
    llm_enabled = (llm_enabled_raw.lower() == "true") if llm_enabled_raw is not None else bool(llm_api_key)
    llm_provider = os.getenv("LLM_PROVIDER", "deepseek")
    llm_model = os.getenv("LLM_MODEL", "deepseek-chat")
    llm_base_url = os.getenv("LLM_BASE_URL") or None

    return AppConfig(
        timezone=timezone,
        database_path=database_path,
        publish_dir=publish_dir,
        status_path=status_path,
        source_config=source_config,
        llm_enabled=llm_enabled,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
    )


def load_sources(config_path: Path) -> list[dict]:
    with config_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [source for source in payload.get("sources", []) if source.get("enabled", True)]
