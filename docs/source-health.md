# Source Health

`public/data/source-health.json` is the pipeline's diagnostic report for source collection.

## Purpose

This file answers three operational questions quickly:

1. which source is healthy right now?
2. which source only succeeded by using a backup URL?
3. which source is broken, and why?

## Status meanings

Healthy:

- `success` — primary URL fetched items
- `empty` — primary URL responded but produced no items

Degraded:

- `fallback_success` — primary URL failed, backup URL fetched items
- `fallback_empty` — primary URL failed, backup URL responded but produced no items

Unhealthy:

- `timeout`
- `http_error`
- `parse_error`
- `invalid_feed`
- `unexpected_error`

## Fields per source

- `source_id`
- `source_name`
- `status`
- `items_fetched`
- `active_url`
- `attempted_urls`
- `backup_urls`
- `fallback_used`
- `error_message`

## Configuration

Each source can keep a primary URL and optional backups:

```json
{
  "id": "example",
  "name": "Example Feed",
  "category": "ai",
  "type": "rss",
  "url": "https://primary.example/rss",
  "backup_urls": [
    "https://backup.example/rss",
    "https://mirror.example/rss"
  ]
}
```

You can also provide a fully expanded `urls` array. The first URL is treated as primary.

## LLM degradation

LLM rewrite failures should not break collection. Check `public/data/status.json` for the `llm` block:

- `status=success` — enrichment worked
- `status=degraded` — at least one item fell back to deterministic text
- `status=disabled` — LLM was intentionally off
