from __future__ import annotations

import sqlite3
from pathlib import Path

from .ai import build_enricher
from .config import load_config, load_sources
from .db import connect, init_db
from .fetchers import fetch_source
from .models import Story, utc_now_iso
from .processing import deduplicate, to_story
from .publish import publish
from .status import write_status


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
    connection = connect(config.database_path)
    init_db(connection)

    run_id = insert_run(connection, len(sources))
    raw_items_total = 0
    stories_total = 0
    source_statuses: list[dict] = []

    try:
        collected = []
        for source in sources:
            try:
                source_items = fetch_source(source)
                raw_items_total += len(source_items)
                collected.extend((source, item) for item in source_items)
                store_raw_items(connection, source_items)
                source_status = {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "status": "success" if source_items else "empty",
                    "items_fetched": len(source_items),
                    "error_message": None,
                }
                source_statuses.append(source_status)
                store_source_run(connection, run_id=run_id, **source_status)
            except Exception as exc:
                source_status = {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "status": "failed",
                    "items_fetched": 0,
                    "error_message": str(exc),
                }
                source_statuses.append(source_status)
                store_source_run(connection, run_id=run_id, **source_status)

        deduped_items = deduplicate([item for _, item in collected])

        source_priority = {source["id"]: source.get("priority", 50) for source in sources}
        stories = [
            to_story(item, source_priority.get(item.source_id, 50), enricher)
            for item in deduped_items
        ]
        stories.sort(key=lambda story: (story.story_date, story.score), reverse=True)

        store_stories(connection, run_id, stories)
        publish(stories, config.publish_dir)

        stories_total = len(stories)
        finish_run(connection, run_id, "success", raw_items_total, stories_total)
        finished_at = utc_now_iso()
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
            "llm_enabled": config.llm_enabled and bool(config.llm_api_key),
            "source_statuses": source_statuses,
        }
        write_status(config.status_path, result)
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
            "llm_enabled": config.llm_enabled and bool(config.llm_api_key),
            "status": "failed",
            "error_message": str(exc),
            "source_statuses": source_statuses,
        }
        write_status(config.status_path, failure_payload)
        raise
    finally:
        connection.close()
