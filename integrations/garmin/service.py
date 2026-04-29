"""Service layer for Garmin data.

All business logic lives here. CLI commands and the future MCP server call
these functions — neither puts logic in the transport layer.

Every function resolves dates from `days` and wires up config/storage/client.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from .ai_context import generate_ai_context
from .auth import get_authenticated_client
from .config import GarminConfig, load_config
from .insights import compute_insights
from .models import SyncResult
from .storage import GarminStorage
from .sync import sync_date_range

logger = logging.getLogger(__name__)


def _date_range_from_days(days: int) -> tuple[date, date]:
    date_to = date.today()
    date_from = date_to - timedelta(days=days - 1)
    return date_from, date_to


def _make_storage(config: GarminConfig) -> GarminStorage:
    storage = GarminStorage(config.db_path)
    storage.initialize()
    return storage


# ── Public service functions ───────────────────────────────────────────────


def sync_garmin_data(
    days: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    config: GarminConfig | None = None,
) -> SyncResult:
    """Sync Garmin data for the given period into local storage."""
    cfg = config or load_config()
    effective_days = days or cfg.sync_days_default

    if date_from is None or date_to is None:
        date_from, date_to = _date_range_from_days(effective_days)

    storage = _make_storage(cfg)
    client = get_authenticated_client(cfg)
    return sync_date_range(client, date_from, date_to, storage)


def get_garmin_summary(
    days: int = 30,
    config: GarminConfig | None = None,
) -> dict[str, Any]:
    """Return a full serialised InsightReport for the last N days."""
    cfg = config or load_config()
    date_from, date_to = _date_range_from_days(days)
    storage = _make_storage(cfg)
    report = compute_insights(storage, date_from, date_to)
    return report.to_dict()


def get_recent_activities(
    days: int = 30,
    config: GarminConfig | None = None,
) -> list[dict[str, Any]]:
    """Return a list of activity summaries for the last N days."""
    cfg = config or load_config()
    date_from, date_to = _date_range_from_days(days)
    storage = _make_storage(cfg)
    activities = storage.get_activities(date_from.isoformat(), date_to.isoformat())
    return [
        {
            "activity_id": a.activity_id,
            "date": a.calendar_date,
            "name": a.activity_name,
            "type": a.activity_type,
            "duration_minutes": round(a.duration_seconds / 60, 1) if a.duration_seconds else None,
            "distance_km": round(a.distance_meters / 1000, 2) if a.distance_meters else None,
            "avg_hr": a.average_hr,
            "max_hr": a.max_hr,
            "calories": a.calories,
            "tss": a.training_stress_score,
        }
        for a in activities
    ]


def get_sleep_trends(
    days: int = 30,
    config: GarminConfig | None = None,
) -> dict[str, Any]:
    """Return sleep trend data for the last N days."""
    cfg = config or load_config()
    date_from, date_to = _date_range_from_days(days)
    storage = _make_storage(cfg)
    sleep_data = storage.get_sleep(date_from.isoformat(), date_to.isoformat())

    from .insights import _analyse_sleep
    return _analyse_sleep(sleep_data, days)


def get_recovery_signals(
    days: int = 30,
    config: GarminConfig | None = None,
) -> dict[str, Any]:
    """Return recovery-focused signals for the last N days."""
    cfg = config or load_config()
    date_from, date_to = _date_range_from_days(days)
    storage = _make_storage(cfg)
    report = compute_insights(storage, date_from, date_to)
    return {
        "period": {"from": report.period_from, "to": report.period_to, "days": days},
        "body_battery": report.metrics.get("body_battery", {}),
        "hrv": report.metrics.get("hrv", {}),
        "sleep": report.metrics.get("sleep", {}),
        "risk_signals": report.risk_signals,
        "recommendations": [
            r.to_dict()
            for r in report.recommendations
            if any(
                kw in r.title.lower()
                for kw in ("recovery", "sleep", "hrv", "battery", "consecutive", "load")
            )
        ],
    }


def get_training_recommendations(
    days: int = 30,
    config: GarminConfig | None = None,
) -> list[dict[str, Any]]:
    """Return training-focused recommendations for the last N days."""
    cfg = config or load_config()
    date_from, date_to = _date_range_from_days(days)
    storage = _make_storage(cfg)
    report = compute_insights(storage, date_from, date_to)
    return [r.to_dict() for r in report.recommendations]


def get_ai_context(
    days: int = 30,
    format: str = "text",
    config: GarminConfig | None = None,
) -> str | dict[str, Any]:
    """Return a compact AI-ready context block for the last N days.

    Args:
        days: Number of days to analyse.
        format: "text" for plain text, "json" for structured dict.
        config: Optional pre-loaded config (injected in tests).
    """
    cfg = config or load_config()
    date_from, date_to = _date_range_from_days(days)
    storage = _make_storage(cfg)
    report = compute_insights(storage, date_from, date_to)
    return generate_ai_context(report, format=format)
