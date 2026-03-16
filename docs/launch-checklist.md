# Launch Checklist

## Repository Setup

1. Push the rebuilt project to the `main` branch.
2. Make sure GitHub Actions is enabled.
3. Make sure your static hosting serves the repository root.

## Secrets

Minimum setup:

- no secrets required for fallback mode

Optional AI setup:

- `LLM_ENABLED=true`
- `LLM_API_KEY=...`
- `LLM_BASE_URL=https://api.deepseek.com`
- `LLM_MODEL=deepseek-chat`

## First Local Check

Run:

```bash
python3 scripts/check_setup.py
python3 scripts/write_sample_data.py
python3 scripts/serve_frontend.py --port 8000
```

Then open:

- `http://127.0.0.1:8000`

Confirm:

- the homepage loads
- cards render
- the status area shows a healthy run
- background and music assets load

## First Live Check

1. Open the Actions tab.
2. Run `Update Site Data` manually.
3. Confirm `public/data/latest.json` changed.
4. Confirm `public/data/status.json` contains source statuses.
5. Open the deployed site and hard refresh.

## If Something Breaks

Check in this order:

1. GitHub Actions logs
2. `public/data/status.json`
3. source failures listed in the status payload
4. local run with `python3 scripts/run_pipeline.py --json`
