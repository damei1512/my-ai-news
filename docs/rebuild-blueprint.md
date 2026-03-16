# Rebuild Blueprint

## Product Goal

Build a personal information station that refreshes automatically, stays readable, and fails gracefully.

The system should answer one question well:

`What changed today that is worth my attention?`

## Guiding Principles

1. Reliability over cleverness.
2. Data pipeline before UI polish.
3. Each stage has one responsibility.
4. Frontend consumes clean data, not raw feeds.
5. Every run should be inspectable and recoverable.

## System Layers

### 1. Collection

Purpose:

- fetch source content
- keep source-specific failure isolated
- store raw results before enrichment

Inputs:

- RSS / Atom
- official blogs
- GitHub releases
- optional APIs later

Outputs:

- `raw_items`

### 2. Processing

Purpose:

- normalize fields
- detect duplicates
- classify
- rank
- later call AI for rewrite and summary

Outputs:

- `stories`

### 3. Publishing

Purpose:

- write frontend-ready JSON
- write daily snapshots
- write latest aggregate output

Outputs:

- `public/data/latest.json`
- `public/data/daily/YYYY-MM-DD.json`

### 4. Presentation

Purpose:

- filter, search, browse
- display already-processed stories

The frontend should never need to fix source data.

## Recommended MVP Data Flow

1. load `config/sources.json`
2. fetch each feed
3. normalize title, summary, link, timestamp, image
4. persist raw items to SQLite
5. deduplicate by canonical URL and text fingerprint
6. assign category and score
7. publish clean JSON
8. log the run summary

## Data Model

### sources

- `id`
- `name`
- `category`
- `url`
- `enabled`
- `priority`

### raw_items

- `id`
- `source_id`
- `title`
- `url`
- `canonical_url`
- `summary`
- `published_at`
- `fetched_at`
- `fingerprint`
- `payload_json`

### stories

- `id`
- `run_id`
- `source_id`
- `category`
- `title`
- `url`
- `summary`
- `commentary`
- `image_url`
- `score`
- `published_at`
- `story_date`

### runs

- `id`
- `started_at`
- `finished_at`
- `status`
- `sources_total`
- `raw_items_total`
- `stories_total`
- `error_message`

## Delivery Plan

### Phase 1

- SQLite storage
- RSS-only collection
- deterministic deduplication
- JSON publishing
- run logging

### Phase 2

- AI title rewrite
- Chinese summary
- commentary generation
- tag extraction
- importance scoring

Implementation note:

- AI must be optional.
- If the provider fails, the run should degrade to deterministic fallback text instead of failing the whole pipeline.

### Phase 3

- source health dashboard
- Telegram alerts
- read/star state
- personalized ranking

## Why This Structure

The old project mixed source fetching, AI generation, publishing, and frontend compatibility in one place. That made failures hard to locate and fixes risky.

This rebuild separates concerns so we can test each part independently and migrate the frontend later without rebreaking the pipeline.
