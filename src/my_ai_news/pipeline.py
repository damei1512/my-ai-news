from __future__ import annotations

import sqlite3
from pathlib import Path

from .ai import NoopEnricher, build_enricher
from .config import load_config, load_sources
from .db import connect, init_db
from .fetchers import DEGRADED_STATUSES, SUCCESS_STATUSES, FetchResult, SourceFetchError, fetch_source
from .models import Story, utc_now_iso
from .processing import deduplicate, to_story
from .publish import publish
from .status import write_status


def classify_llm_error(exc: Exception) -> str:
    message = str(exc).lower()
    if isinstance(exc, TimeoutError) or "timed out" in message:
        return "timeout"
    if "401" in message or "403" in message or "api key" in message or "authentication" in message:
        return "auth_error"
    if "429" in message or "rate limit" in message or "quota" in message:
        return "rate_limited"
    if "json" in message or "decode" in message:
        return "invalid_response"
    return "unexpected_error"


def _coerce_fetch_result(source: dict, fetched: FetchResult | list) -> FetchResult:
    if isinstance(fetched, FetchResult):
        return fetched

    active_url = source.get("url", "")
    backup_urls = [str(url).strip() for url in source.get("backup_urls", []) if str(url).strip()]
    return FetchResult(
        items=list(fetched),
        status="success" if fetched else "empty",
        active_url=active_url,
        attempted_urls=[active_url] if active_url else [],
        backup_urls=backup_urls,
        error_message=None,
    )


def build_source_health_payload(*, config, run_id: int, finished_at: str, source_statuses: list[dict]) -> dict:
    healthy_sources = sum(1 for item in source_statuses if item.get("status") in SUCCESS_STATUSES)
    degraded_sources = sum(1 for item in source_statuses if item.get("status") in DEGRADED_STATUSES)
    unhealthy_sources = len(source_statuses) - healthy_sources - degraded_sources
    return {
        "run_id": run_id,
        "generated_at": finished_at,
        "source_health_path": str(config.source_health_path),
        "summary": {
            "total_sources": len(source_statuses),
            "healthy_sources": healthy_sources,
            "degraded_sources": degraded_sources,
            "unhealthy_sources": unhealthy_sources,
        },
        "sources": source_statuses,
    }


def insert_run(connection: sqlite3.Connection, sources_total: int) -> int:
    cursor = connection.execute(
        """
        INSERT INTO runs (started_at, status, sources_total)
        VALUES (?, 'running', ?)
        """,
        (utc_now_iso(), sources_total),
    )
    connection.commit()
    return int(cursor.lastrowid)


def finish_run(
    connection: sqlite3.Connection,
    run_id: int,
    status: str,
    raw_items_total: int,
    stories_total: int,
    error_message: str | None = None,
) -> None:
    connection.execute(
        """
        UPDATE runs
        SET finished_at = ?, status = ?, raw_items_total = ?, stories_total = ?, error_message = ?
        WHERE id = ?
        """,
        (utc_now_iso(), status, raw_items_total, stories_total, error_message, run_id),
    )
    connection.commit()


def store_raw_items(connection: sqlite3.Connection, items: list) -> None:
    connection.executemany(
        """
        INSERT OR IGNORE INTO raw_items (
            source_id, source_name, category, title, url, canonical_url, summary,
            image_url, published_at, published_date, fetched_at, fingerprint, payload_json
        ) VALUES (
            :source_id, :source_name, :category, :title, :url, :canonical_url, :summary,
            :image_url, :published_at, :published_date, :fetched_at, :fingerprint, :payload_json
        )
        """,
        [item.to_dict() for item in items],
    )
    connection.commit()


def store_stories(connection: sqlite3.Connection, run_id: int, stories: list[Story]) -> None:
    connection.executemany(
        """
        INSERT INTO stories (
            run_id, source_id, source_name, category, title, url, summary,
            commentary, image_url, score, published_at, story_date
        ) VALUES (
            :run_id, :source_id, :source_name, :category, :title, :url, :summary,
            :commentary, :image_url, :score, :published_at, :story_date
        )
        """,
        [{"run_id": run_id, **story.to_dict()} for story in stories],
    )
    connection.commit()


def store_source_run(
    connection: sqlite3.Connection,
    *,
    run_id: int,
    source_id: str,
    source_name: str,
    status: str,
    items_fetched: int,
    error_message: str | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO source_runs (
            run_id, source_id, source_name, status, items_fetched, error_message, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, source_id, source_name, status, items_fetched, error_message, utc_now_iso()),
    )
    connection.commit()


def run_pipeline(project_root: Path) -> dict:
    config = load_config(project_root)
    sources = load_sources(config.source_config)
    enricher = build_enricher(config)
    llm_enabled = config.llm_enabled and bool(config.llm_api_key)
    connection = connect(config.database_path)
    init_db(connection)

    run_id = insert_run(connection, len(sources))
    raw_items_total = 0
    stories_total = 0
    source_statuses: list[dict] = []
    llm_errors: dict[str, int] = {}
    llm_degraded_items = 0

    try:
        collected = []
        for source in sources:
            try:
                fetch_result = _coerce_fetch_result(source, fetch_source(source))
                source_items = fetch_result.items
                raw_items_total += len(source_items)
                collected.extend((source, item) for item in source_items)
                store_raw_items(connection, source_items)
                source_status = {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "status": fetch_result.status,
                    "items_fetched": len(source_items),
                    "active_url": fetch_result.active_url,
                    "attempted_urls": fetch_result.attempted_urls,
                    "backup_urls": fetch_result.backup_urls,
                    "fallback_used": fetch_result.status in DEGRADED_STATUSES,
                    "error_message": None,
                }
                source_statuses.append(source_status)
                store_source_run(
                    connection,
                    run_id=run_id,
                    source_id=source_status["source_id"],
                    source_name=source_status["source_name"],
                    status=source_status["status"],
                    items_fetched=source_status["items_fetched"],
                    error_message=source_status["error_message"],
                )
            except Exception as exc:
                status = exc.status if isinstance(exc, SourceFetchError) else "unexpected_error"
                attempted_urls = exc.attempted_urls if isinstance(exc, SourceFetchError) else [source.get("url", "")]
                backup_urls = exc.backup_urls if isinstance(exc, SourceFetchError) else [str(url).strip() for url in source.get("backup_urls", []) if str(url).strip()]
                source_status = {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "status": status,
                    "items_fetched": 0,
                    "active_url": None,
                    "attempted_urls": attempted_urls,
                    "backup_urls": backup_urls,
                    "fallback_used": False,
                    "error_message": str(exc),
                }
                source_statuses.append(source_status)
                store_source_run(
                    connection,
                    run_id=run_id,
                    source_id=source_status["source_id"],
                    source_name=source_status["source_name"],
                    status=source_status["status"],
                    items_fetched=source_status["items_fetched"],
                    error_message=source_status["error_message"],
                )

        deduped_items = deduplicate([item for _, item in collected])

        source_priority = {source["id"]: source.get("priority", 50) for source in sources}
        stories: list[Story] = []
        noop_enricher = NoopEnricher()
        for item in deduped_items:
            try:
                stories.append(to_story(item, source_priority.get(item.source_id, 50), enricher))
            except Exception as exc:
                llm_degraded_items += 1
                reason = classify_llm_error(exc)
                llm_errors[reason] = llm_errors.get(reason, 0) + 1
                stories.append(to_story(item, source_priority.get(item.source_id, 50), noop_enricher))
        stories.sort(key=lambda story: (story.story_date, story.score), reverse=True)

        store_stories(connection, run_id, stories)
        publish(stories, config.publish_dir)

        stories_total = len(stories)
        finish_run(connection, run_id, "success", raw_items_total, stories_total)
        finished_at = utc_now_iso()
        if not llm_enabled:
            llm_status = "disabled"
        elif llm_degraded_items:
            llm_status = "degraded"
        else:
            llm_status = "success"

        llm_payload = {
            "enabled": llm_enabled,
            "provider": config.llm_provider,
            "model": config.llm_model,
            "base_urls": config.llm_base_urls,
            "status": llm_status,
            "degraded_items": llm_degraded_items,
            "error_counts": llm_errors,
        }
        result = {
            "run_id": run_id,
            "status": "success",
            "finished_at": finished_at,
            "sources": len(sources),
            "raw_items": raw_items_total,
            "stories": stories_total,
            "database": str(config.database_path),
            "publish_dir": str(config.publish_dir),
            "status_path": str(config.status_path),
            "source_health_path": str(config.source_health_path),
            "llm_enabled": llm_enabled,
            "llm": llm_payload,
            "source_statuses": source_statuses,
        }
        write_status(config.status_path, result)
        write_status(
            config.source_health_path,
            build_source_health_payload(
                config=config,
                run_id=run_id,
                finished_at=finished_at,
                source_statuses=source_statuses,
            ),
        )
        return result
    except Exception as exc:
        finish_run(connection, run_id, "failed", raw_items_total, stories_total, str(exc))
        failure_payload = {
            "run_id": run_id,
            "finished_at": utc_now_iso(),
            "sources": len(sources),
            "raw_items": raw_items_total,
            "stories": stories_total,
            "database": str(config.database_path),
            "publish_dir": str(config.publish_dir),
            "status_path": str(config.status_path),
            "source_health_path": str(config.source_health_path),
            "llm_enabled": llm_enabled,
            "llm": {
                "enabled": llm_enabled,
                "provider": config.llm_provider,
                "model": config.llm_model,
                "base_urls": config.llm_base_urls,
                "status": "failed" if llm_enabled else "disabled",
                "degraded_items": llm_degraded_items,
                "error_counts": llm_errors,
            },
            "status": "failed",
            "error_message": str(exc),
            "source_statuses": source_statuses,
        }
        write_status(config.status_path, failure_payload)
        write_status(
            config.source_health_path,
            build_source_health_payload(
                config=config,
                run_id=run_id,
                finished_at=failure_payload["finished_at"],
                source_statuses=source_statuses,
            ),
        )
        raise
    finally:
        connection.close()
