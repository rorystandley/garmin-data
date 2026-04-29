"""Sync Garmin data for a date range into local storage.

Each endpoint call is wrapped individually so a single failure does not stop
the rest of the sync. Missing or unsupported endpoints are logged clearly.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from .client import GarminClientProtocol
from .models import (
    Activity,
    ActivityDetail,
    BodyBatteryData,
    DailySummary,
    HRVData,
    SleepData,
    WeightEntry,
    StressData,
    SyncResult,
)
from .storage import GarminStorage

logger = logging.getLogger(__name__)


def _date_range(date_from: date, date_to: date) -> list[date]:
    days = (date_to - date_from).days
    return [date_from + timedelta(days=i) for i in range(days + 1)]


def _safe_fetch(
    result: SyncResult,
    label: str,
    fn: Any,
    *args: Any,
) -> Any:
    """Call fn(*args), catch all exceptions, log them, return None on failure."""
    try:
        return fn(*args)
    except Exception as exc:
        msg = f"{label}: {type(exc).__name__}: {exc}"
        logger.warning("Fetch failed — %s", msg)
        result.add_error(msg)
        return None


def sync_date_range(
    client: GarminClientProtocol,
    date_from: date,
    date_to: date,
    storage: GarminStorage,
) -> SyncResult:
    """Sync all Garmin data for the given date range into storage."""
    from_str = date_from.isoformat()
    to_str = date_to.isoformat()
    result = SyncResult(date_from=from_str, date_to=to_str)

    logger.info("Syncing %s → %s", from_str, to_str)

    run_id = storage.start_sync_run(from_str, to_str)

    # ── Per-day data ──────────────────────────────────────────────────────
    for d in _date_range(date_from, date_to):
        cdate = d.isoformat()
        logger.debug("Fetching data for %s", cdate)

        # Daily summary
        raw = _safe_fetch(result, f"daily_summary/{cdate}", client.get_user_summary, cdate)
        if raw:
            storage.upsert_daily_summary(DailySummary.from_dict(raw))
            result.records_synced += 1

        # Sleep
        raw = _safe_fetch(result, f"sleep/{cdate}", client.get_sleep_data, cdate)
        if raw:
            s = SleepData.from_dict(raw)
            if s.calendar_date:
                storage.upsert_sleep(s)
                result.records_synced += 1

        # Stress
        raw = _safe_fetch(result, f"stress/{cdate}", client.get_stress_data, cdate)
        if raw:
            storage.upsert_stress(StressData.from_dict(raw))
            result.records_synced += 1

        # HRV
        raw = _safe_fetch(result, f"hrv/{cdate}", client.get_hrv_data, cdate)
        if raw:
            h = HRVData.from_dict(raw)
            if h.calendar_date:
                storage.upsert_hrv(h)
                result.records_synced += 1

        # Training readiness
        raw = _safe_fetch(result, f"training_readiness/{cdate}", client.get_training_readiness, cdate)
        if raw:
            storage.upsert_metric_raw(cdate, "training_readiness", raw)
            result.records_synced += 1

        # Training status
        raw = _safe_fetch(result, f"training_status/{cdate}", client.get_training_status, cdate)
        if raw:
            storage.upsert_metric_raw(cdate, "training_status", raw)
            result.records_synced += 1

        # Daily weigh-ins
        raw = _safe_fetch(result, f"weigh_ins/{cdate}", client.get_daily_weigh_ins, cdate)
        if raw:
            entries = raw.get("dateWeightList") or []
            for entry in entries:
                w = WeightEntry.from_dict(entry, calendar_date=cdate)
                if w.weight_kg is not None:
                    storage.upsert_weigh_in(w)
                    result.records_synced += 1

    # ── Body Battery (range call) ─────────────────────────────────────────
    bb_list = _safe_fetch(
        result, "body_battery", client.get_body_battery, from_str, to_str
    )
    if bb_list:
        for bb_entry in bb_list:
            b = BodyBatteryData.from_dict(bb_entry)
            if b.calendar_date:
                storage.upsert_body_battery(b)
                result.records_synced += 1

    # ── Body composition / weight (range call) ────────────────────────────
    bcomp = _safe_fetch(
        result, "body_composition", client.get_body_composition, from_str, to_str
    )
    if bcomp:
        entries = bcomp.get("dateWeightList") or []
        for entry in entries:
            cdate = (entry.get("calendarDate") or "")[:10]
            if cdate:
                storage.upsert_metric_raw(cdate, "weight", entry)
                result.records_synced += 1

    # ── Activities (range call) ───────────────────────────────────────────
    activities = _safe_fetch(
        result, "activities", client.get_activities_by_date, from_str, to_str
    )
    if activities:
        for raw_act in activities:
            act = Activity.from_dict(raw_act)
            if act.activity_id:
                storage.upsert_activity(act)
                result.records_synced += 1

                # Activity details (individual call per activity)
                details_raw = _safe_fetch(
                    result,
                    f"activity_details/{act.activity_id}",
                    client.get_activity_details,
                    act.activity_id,
                )
                if details_raw:
                    storage.upsert_activity_details(
                        ActivityDetail.from_dict(act.activity_id, details_raw)
                    )
                    result.records_synced += 1

    storage.finish_sync_run(run_id, result.records_synced, result.errors)
    logger.info(
        "Sync complete: %d records, %d errors",
        result.records_synced,
        len(result.errors),
    )
    return result
