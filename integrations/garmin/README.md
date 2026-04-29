# Garmin Integration

Personal Garmin Connect data pipeline — sync health and activity data locally, analyse it, and generate AI-ready insights.

> **Disclaimer:** This is not medical advice. All data, summaries, and recommendations are for personal training and lifestyle awareness only. Consult a qualified healthcare professional for any health concerns.

---

## What it does

- Pulls personal Garmin Connect data (sleep, stress, body battery, HRV, daily summary, activities, weight) via the unofficial `garminconnect` Python library
- Stores data locally in SQLite — your data never leaves your machine by default
- Computes deterministic health and training insights without involving any LLM
- Generates compact AI-ready context blocks that an AI agent can use to give practical recommendations
- Exposes everything through simple CLI commands

---

## Configuration

Copy `.env.example` to `.env` in the project root and fill in your values:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `GARMIN_EMAIL` | Yes | — | Your Garmin Connect account email |
| `GARMIN_PASSWORD` | Yes | — | Your Garmin Connect password |
| `GARMIN_TOKEN_DIR` | No | `~/.garmin_tokens` | Directory for persisted auth tokens |
| `GARMIN_DB_PATH` | No | `~/garmin_data.db` | Path to the SQLite database |
| `GARMIN_SYNC_DAYS_DEFAULT` | No | `30` | Default sync window in days |
| `GARMIN_LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

---

## First run

```bash
# Install dependencies
uv sync

# Sync the last 30 days
uv run garmin-sync --days 30
```

On first run you will be prompted for credentials (or MFA if your account has 2FA enabled). Tokens are saved to `GARMIN_TOKEN_DIR` — subsequent runs use the saved tokens without prompting.

---

## CLI reference

### `garmin-sync` — pull data from Garmin

```bash
# Last 30 days (default)
uv run garmin-sync

# Last N days
uv run garmin-sync --days 7

# Specific date range
uv run garmin-sync --from 2026-01-01 --to 2026-01-31
```

### `garmin-summary` — readable overview

```bash
uv run garmin-summary --days 7
uv run garmin-summary --days 30 --format json
```

### `garmin-activities` — list workouts

```bash
uv run garmin-activities --days 30
uv run garmin-activities --days 30 --format json
```

### `garmin-insights` — full insight report with recommendations

```bash
uv run garmin-insights --days 30
uv run garmin-insights --days 30 --format json
```

### `garmin-ai-context` — generate AI-ready context

```bash
uv run garmin-ai-context --days 30
uv run garmin-ai-context --days 30 --format json
```

---

## Typical agent workflow

An AI agent pointed at this project can run:

```bash
# 1. Sync latest data
uv run garmin-sync --days 30

# 2. Generate AI context
uv run garmin-ai-context --days 30

# 3. Feed the output to Claude/another LLM for recommendations
uv run garmin-ai-context --days 30 | claude "Analyse this Garmin data and give me specific training and recovery recommendations"
```

---

## How data is stored

All data is stored in a local SQLite database at `GARMIN_DB_PATH` (`~/garmin_data.db` by default).

| Table | Key | Contents |
|---|---|---|
| `garmin_sync_runs` | id | History of sync runs with status/errors |
| `garmin_daily_summaries` | `calendar_date` | Steps, HR, calories, stress, body battery, intensity minutes |
| `garmin_sleep` | `calendar_date` | Sleep duration by stage, score, SpO2, breathing rate |
| `garmin_stress` | `calendar_date` | Avg/max stress, time in each stress zone |
| `garmin_body_battery` | `calendar_date` | Start/end values, charged/drained |
| `garmin_hrv` | `calendar_date` | Weekly avg, last night, baseline, status |
| `garmin_activities` | `activity_id` | Duration, distance, HR, calories, TSS, training effect |
| `garmin_activity_details` | `activity_id` | Full raw activity JSON |
| `garmin_weigh_ins` | `calendar_date` | Weight (kg/lbs), BMI, body fat %, muscle mass |
| `garmin_metrics_raw` | `(calendar_date, metric_type)` | Training readiness, training status |

Every row keeps the original `raw_json` response alongside normalised columns. Re-syncing the same date range is **idempotent** — no duplicates are created.

---

## What each module does

| File | Purpose |
|---|---|
| `config.py` | Load and validate env vars |
| `auth.py` | Login, token persistence, MFA handling |
| `client.py` | `GarminClientProtocol` interface + `GarminConnectAdapter` |
| `models.py` | Typed dataclasses for all data types |
| `sync.py` | Fetch all endpoints for a date range |
| `storage.py` | SQLite upserts and queries |
| `insights.py` | Deterministic insight calculations |
| `ai_context.py` | Convert insights to AI-ready context |
| `service.py` | Clean service layer (called by CLI + MCP) |
| `cli.py` | Click CLI commands |
| `mcp_server.py` | Optional MCP server stub |

---

## Known limitations

- Uses the **unofficial** `garminconnect` library — Garmin can break the API at any time
- Not all fields are available on all devices (e.g. HRV requires a compatible watch)
- Garmin rate-limits aggressive syncing — avoid syncing the same period repeatedly in quick succession
- Activity details (laps, GPS data) are stored as raw JSON but not fully normalised
- Body battery data is fetched as a range; the library returns daily aggregates
- Training readiness and training status require a supported Garmin device (Forerunner, Fenix, etc.)

---

## Replacing the Garmin connector

The application depends on `GarminClientProtocol` (in `client.py`), not directly on `garminconnect`. To replace the underlying library:

1. Implement the `GarminClientProtocol` interface in a new adapter class
2. Update `auth.py` to instantiate your new adapter instead of `GarminConnectAdapter`
3. No other code needs to change

To switch to the official Garmin Health API:
- Obtain API access through the [Garmin Health API Developer Program](https://developer.garmin.com/health-api/overview/)
- Implement a new `GarminHealthAPIAdapter` that wraps the official API client and satisfies `GarminClientProtocol`
- Update `auth.py` to use OAuth tokens instead of username/password

---

## Future MCP server

`mcp_server.py` is a documented stub showing how every service function maps to an MCP tool. To activate:

1. `uv add mcp`
2. Follow the skeleton in `mcp_server.py` to create real `@server.tool()` handlers
3. Register the server in your Claude Code MCP settings

The service layer is already designed to be called from both CLI and MCP without modification.

---

## Running tests

```bash
# All tests (no Garmin account required)
uv run pytest

# With coverage
uv run pytest --cov=integrations --cov-report=term-missing
```

---

## Safety note

Your Garmin credentials are read from environment variables and are never logged, printed, or sent anywhere outside the official Garmin Connect API. Tokens are stored locally in `GARMIN_TOKEN_DIR`.

The `.gitignore` excludes `.env`, `*.db`, and the token directory. **Never commit your `.env` file.**
