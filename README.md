# my-ai-news

`my-ai-news` is a personal information station with a structured ingestion pipeline and a static frontend.

The product goals are:

- automated collection from curated sources
- filtering, deduplication, ranking, and summarization
- daily and latest publish outputs for a static frontend
- clear logs, storage, and recoverable runs

## Project Layout

The active project lives under:

- `config/`
- `docs/`
- `scripts/`
- `src/my_ai_news/`

## Pipeline

Phase 1 focuses on a reliable pipeline:

1. load source configuration
2. fetch RSS/Atom feeds
3. normalize and store raw items in SQLite
4. deduplicate and score stories
5. publish frontend-ready JSON files

AI enrichment is optional. The pipeline still runs in deterministic fallback mode if no model key is configured.

Sources can define `backup_urls` (or an explicit `urls` list) so the collector can fail over without building source-specific anti-bot scrapers. Each run also writes `public/data/source-health.json` for diagnostics.

## Quick Start

1. Create a virtualenv and install dependencies.
2. Copy `.env.example` to `.env` and fill values if needed.
3. Run the pipeline:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
python3 scripts/run_pipeline.py
```

To enable AI rewrite and commentary, set:

```bash
LLM_API_KEY=***
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

If you want to verify the frontend wiring without hitting live feeds first, run:

```bash
python3 scripts/write_sample_data.py
```

Use `--json` if you want machine-readable output:

```bash
python3 scripts/run_pipeline.py --json
```

Print the latest run status:

```bash
python3 scripts/run_pipeline.py --status
```

Outputs are written to:

- `data/app.db`
- `public/data/latest.json`
- `public/data/daily/YYYY-MM-DD.json`
- `public/data/x-digest.json`
- `public/data/status.json`
- `public/data/source-health.json`

Source config supports a primary URL plus optional backups:

```json
{
  "id": "example",
  "name": "Example Feed",
  "category": "ai",
  "type": "rss",
  "url": "https://primary.example/rss",
  "backup_urls": [
    "https://backup.example/rss"
  ]
}
```

X digest accounts live in `config/x_accounts.json`. Because X does not provide a simple public RSS feed, configure either:

- `X_RSS_BASE_URL`, for example your own RSSHub-compatible instance
- per-account `rss_url` or `rss_urls`

Each run writes bilingual X items to `public/data/x-digest.json`. If no X feed is configured, the file is still written with an empty list and the main news pipeline continues normally.

For local preview:

```bash
python3 scripts/serve_frontend.py --port 8000
```

Run a setup check before the first live run:

```bash
python3 scripts/check_setup.py
```

For development and tests:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

## Docs

- `docs/rebuild-blueprint.md`
- `docs/deployment.md`
- `docs/launch-checklist.md`

## Current Status

The old one-file generator flow has been removed. The project now has one active data path:

`config -> fetch -> process -> publish -> frontend`

## Automation

Automatic refresh is handled by:

- `.github/workflows/update-site-data.yml`

That workflow updates `public/data/` on a schedule and can also be run manually.
