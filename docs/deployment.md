# Deployment

## Recommended Flow

Use GitHub Actions to refresh data and commit the published JSON files back into the repository.

This project now treats `public/data/` as the published output directory for the static frontend.

## Workflow

The workflow file is:

- `.github/workflows/update-site-data.yml`

It does the following:

1. checks out the repo
2. installs Python dependencies
3. runs the pipeline
4. commits changed files under `public/data/`

## Required Repository Secrets

Optional:

- `LLM_API_KEY`
- `LLM_BASE_URL`
- `LLM_MODEL`

If `LLM_API_KEY` is not set, the pipeline will still run in fallback mode without AI rewrite.

## Safety Notes

- The workflow only runs on `main`.
- Concurrency is enabled so scheduled runs do not overlap.
- Published data is committed from `public/data/`.

## GitHub Pages

If you publish this repository as a static site, make sure the site serves:

- `index.html`
- `bg-new.png`
- `music/`
- `public/data/`

## Local Usage

Run a local preview server:

```bash
python3 scripts/serve_frontend.py --port 8000
```

Generate sample data first if needed:

```bash
python3 scripts/write_sample_data.py
```

Check local setup first:

```bash
python3 scripts/check_setup.py
```
