# garmin-data

A personal Garmin Connect data pipeline. Syncs your health and activity data to a local SQLite database, runs a deterministic insight engine over it, and generates compact AI-ready context blocks — all from the command line with no cloud dependencies.

> **Not medical advice.** All data, summaries, and recommendations are for personal training and lifestyle awareness only. Consult a qualified healthcare professional for any health concerns.

---

## Features

- **Local-first** — data is stored in a SQLite file on your machine; nothing is sent to any third-party service
- **Full sync** — sleep, stress, body battery, HRV, daily summary, activities, weight
- **Deterministic insights** — averages, trends, load spikes, and recovery signals computed without an LLM
- **AI-ready context** — `garmin-ai-context` produces a compact structured block you can paste straight into Claude, ChatGPT, or any other AI assistant
- **Idempotent** — re-syncing the same date range never creates duplicates
- **Zero ORM** — plain `sqlite3` from the standard library; the schema is transparent and queryable directly

---

## Requirements

- Python 3.13+
- [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip`
- A [Garmin Connect](https://connect.garmin.com/) account

---

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/YOUR_USERNAME/garmin-data.git
cd garmin-data
uv sync

# 2. Add your credentials
cp .env.example .env
# Edit .env and set GARMIN_EMAIL and GARMIN_PASSWORD

# 3. Sync the last 30 days
uv run garmin-sync --days 30

# 4. View an insight summary
uv run garmin-summary --days 30

# 5. Generate AI-ready context
uv run garmin-ai-context --days 30
```

On first run you will be prompted for MFA if your account has 2FA enabled. Auth tokens are saved locally and reused on subsequent runs.

---

## CLI commands

| Command | What it does |
|---|---|
| `garmin-sync` | Pull data from Garmin Connect into local storage |
| `garmin-summary` | Human-readable health overview |
| `garmin-activities` | List recent workouts |
| `garmin-insights` | Full insight report with recommendations |
| `garmin-ai-context` | Generate a compact AI-ready context block |

All commands accept `--days N` (default: 30) and most accept `--format text\|json`.

```bash
# Sync a specific date range
uv run garmin-sync --from 2026-01-01 --to 2026-01-31

# JSON output (pipe to jq, save to file, etc.)
uv run garmin-insights --days 7 --format json | jq .metrics.sleep

# Feed directly to an AI assistant
uv run garmin-ai-context --days 30 | pbcopy   # macOS clipboard
```

---

## Configuration

Copy `.env.example` to `.env` and fill in your values:

| Variable | Required | Default | Description |
|---|---|---|---|
| `GARMIN_EMAIL` | Yes | — | Garmin Connect account email |
| `GARMIN_PASSWORD` | Yes | — | Garmin Connect password |
| `GARMIN_TOKEN_DIR` | No | `~/.garmin_tokens` | Directory for persisted auth tokens |
| `GARMIN_DB_PATH` | No | `~/garmin_data.db` | Path to the SQLite database |
| `GARMIN_SYNC_DAYS_DEFAULT` | No | `30` | Default sync window when `--days` is omitted |
| `GARMIN_LOG_LEVEL` | No | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |

---

## Running tests

No Garmin account required — all tests use fixture data and mocked clients.

```bash
uv run pytest

# With coverage
uv run pytest --cov=integrations --cov-report=term-missing
```

---

## Architecture

See [`integrations/garmin/README.md`](integrations/garmin/README.md) for full documentation covering:

- Module breakdown and responsibilities
- Storage schema (all 9 tables)
- How the insight engine works
- Replacing the Garmin connector (adapter pattern)
- Wiring up the optional MCP server stub

---

## Disclaimer

This project uses the **unofficial** [`garminconnect`](https://github.com/cyberjunky/python-garminconnect) library. Garmin does not provide an official public API for personal data access. Use this tool responsibly and in accordance with Garmin's terms of service.

---

## License

MIT — see [LICENSE](LICENSE).
