"""SQLite storage layer for Garmin data.

All upserts are idempotent — re-syncing the same date range does not create
duplicates. Raw JSON is preserved alongside normalised columns for every row.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import (
    Activity,
    ActivityDetail,
    BodyBatteryData,
    DailySummary,
    HRVData,
    SleepData,
    StressData,
    WeightEntry,
)

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS garmin_sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    date_from TEXT NOT NULL,
    date_to TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    records_synced INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS garmin_daily_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calendar_date TEXT NOT NULL UNIQUE,
    steps INTEGER,
    step_goal INTEGER,
    total_kilocalories REAL,
    active_kilocalories REAL,
    resting_heart_rate INTEGER,
    average_heart_rate INTEGER,
    max_heart_rate INTEGER,
    min_heart_rate INTEGER,
    total_distance_meters REAL,
    highly_active_seconds INTEGER,
    active_seconds INTEGER,
    sedentary_seconds INTEGER,
    sleeping_seconds INTEGER,
    moderate_intensity_minutes INTEGER,
    vigorous_intensity_minutes INTEGER,
    body_battery_charged INTEGER,
    body_battery_drained INTEGER,
    body_battery_highest INTEGER,
    body_battery_lowest INTEGER,
    average_stress_level INTEGER,
    max_stress_level INTEGER,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS garmin_sleep (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calendar_date TEXT NOT NULL UNIQUE,
    sleep_time_seconds INTEGER,
    deep_sleep_seconds INTEGER,
    light_sleep_seconds INTEGER,
    rem_sleep_seconds INTEGER,
    awake_seconds INTEGER,
    sleep_score INTEGER,
    sleep_score_quality TEXT,
    average_respiration_value REAL,
    average_spo2_value REAL,
    resting_heart_rate INTEGER,
    average_stress INTEGER,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS garmin_stress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calendar_date TEXT NOT NULL UNIQUE,
    avg_stress_level INTEGER,
    max_stress_level INTEGER,
    stress_duration_seconds INTEGER,
    rest_duration_seconds INTEGER,
    activity_duration_seconds INTEGER,
    uncategorized_duration_seconds INTEGER,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS garmin_body_battery (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calendar_date TEXT NOT NULL UNIQUE,
    start_value INTEGER,
    end_value INTEGER,
    charged INTEGER,
    drained INTEGER,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS garmin_hrv (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calendar_date TEXT NOT NULL UNIQUE,
    weekly_avg INTEGER,
    last_night INTEGER,
    last_5_min INTEGER,
    baseline_low INTEGER,
    baseline_high INTEGER,
    status TEXT,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS garmin_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id TEXT NOT NULL UNIQUE,
    activity_name TEXT,
    activity_type TEXT,
    start_time_gmt TEXT,
    start_time_local TEXT,
    calendar_date TEXT,
    duration_seconds REAL,
    distance_meters REAL,
    average_hr INTEGER,
    max_hr INTEGER,
    calories REAL,
    average_speed REAL,
    max_speed REAL,
    aerobic_training_effect REAL,
    anaerobic_training_effect REAL,
    training_stress_score REAL,
    steps INTEGER,
    average_cadence REAL,
    elevation_gain REAL,
    elevation_loss REAL,
    average_power REAL,
    normalized_power REAL,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS garmin_activity_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id TEXT NOT NULL UNIQUE,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS garmin_metrics_raw (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calendar_date TEXT NOT NULL,
    metric_type TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(calendar_date, metric_type)
);

CREATE TABLE IF NOT EXISTS garmin_weigh_ins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calendar_date TEXT NOT NULL UNIQUE,
    weight_kg REAL,
    weight_lbs REAL,
    bmi REAL,
    body_fat_pct REAL,
    muscle_mass_kg REAL,
    bone_mass_kg REAL,
    body_water_pct REAL,
    source_type TEXT,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class GarminStorage:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    def initialize(self) -> None:
        """Create all tables if they do not exist."""
        conn = self._get_conn()
        conn.executescript(_DDL)
        conn.commit()
        logger.debug("Storage initialised at %s", self._db_path)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    # ── Sync runs ──────────────────────────────────────────────────────────

    def start_sync_run(self, date_from: str, date_to: str) -> int:
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO garmin_sync_runs (started_at, date_from, date_to, status) "
            "VALUES (?, ?, ?, 'running')",
            (_now(), date_from, date_to),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def finish_sync_run(
        self, run_id: int, records_synced: int, errors: list[str]
    ) -> None:
        status = "success" if not errors else "partial"
        error_message = "; ".join(errors) if errors else None
        conn = self._get_conn()
        conn.execute(
            "UPDATE garmin_sync_runs SET completed_at=?, status=?, "
            "records_synced=?, error_message=? WHERE id=?",
            (_now(), status, records_synced, error_message, run_id),
        )
        conn.commit()

    # ── Daily summaries ────────────────────────────────────────────────────

    def upsert_daily_summary(self, s: DailySummary) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO garmin_daily_summaries (
                calendar_date, steps, step_goal, total_kilocalories,
                active_kilocalories, resting_heart_rate, average_heart_rate,
                max_heart_rate, min_heart_rate, total_distance_meters,
                highly_active_seconds, active_seconds, sedentary_seconds,
                sleeping_seconds, moderate_intensity_minutes,
                vigorous_intensity_minutes, body_battery_charged,
                body_battery_drained, body_battery_highest, body_battery_lowest,
                average_stress_level, max_stress_level, raw_json, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(calendar_date) DO UPDATE SET
                steps=excluded.steps, step_goal=excluded.step_goal,
                total_kilocalories=excluded.total_kilocalories,
                active_kilocalories=excluded.active_kilocalories,
                resting_heart_rate=excluded.resting_heart_rate,
                average_heart_rate=excluded.average_heart_rate,
                max_heart_rate=excluded.max_heart_rate,
                min_heart_rate=excluded.min_heart_rate,
                total_distance_meters=excluded.total_distance_meters,
                highly_active_seconds=excluded.highly_active_seconds,
                active_seconds=excluded.active_seconds,
                sedentary_seconds=excluded.sedentary_seconds,
                sleeping_seconds=excluded.sleeping_seconds,
                moderate_intensity_minutes=excluded.moderate_intensity_minutes,
                vigorous_intensity_minutes=excluded.vigorous_intensity_minutes,
                body_battery_charged=excluded.body_battery_charged,
                body_battery_drained=excluded.body_battery_drained,
                body_battery_highest=excluded.body_battery_highest,
                body_battery_lowest=excluded.body_battery_lowest,
                average_stress_level=excluded.average_stress_level,
                max_stress_level=excluded.max_stress_level,
                raw_json=excluded.raw_json, updated_at=excluded.updated_at
            """,
            (
                s.calendar_date, s.steps, s.step_goal, s.total_kilocalories,
                s.active_kilocalories, s.resting_heart_rate, s.average_heart_rate,
                s.max_heart_rate, s.min_heart_rate, s.total_distance_meters,
                s.highly_active_seconds, s.active_seconds, s.sedentary_seconds,
                s.sleeping_seconds, s.moderate_intensity_minutes,
                s.vigorous_intensity_minutes, s.body_battery_charged,
                s.body_battery_drained, s.body_battery_highest, s.body_battery_lowest,
                s.average_stress_level, s.max_stress_level, s.raw_json, _now(),
            ),
        )
        conn.commit()

    def get_daily_summaries(
        self, date_from: str, date_to: str
    ) -> list[DailySummary]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM garmin_daily_summaries "
            "WHERE calendar_date >= ? AND calendar_date <= ? "
            "ORDER BY calendar_date",
            (date_from, date_to),
        ).fetchall()
        return [_row_to_daily_summary(r) for r in rows]

    # ── Sleep ──────────────────────────────────────────────────────────────

    def upsert_sleep(self, s: SleepData) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO garmin_sleep (
                calendar_date, sleep_time_seconds, deep_sleep_seconds,
                light_sleep_seconds, rem_sleep_seconds, awake_seconds,
                sleep_score, sleep_score_quality, average_respiration_value,
                average_spo2_value, resting_heart_rate, average_stress,
                raw_json, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(calendar_date) DO UPDATE SET
                sleep_time_seconds=excluded.sleep_time_seconds,
                deep_sleep_seconds=excluded.deep_sleep_seconds,
                light_sleep_seconds=excluded.light_sleep_seconds,
                rem_sleep_seconds=excluded.rem_sleep_seconds,
                awake_seconds=excluded.awake_seconds,
                sleep_score=excluded.sleep_score,
                sleep_score_quality=excluded.sleep_score_quality,
                average_respiration_value=excluded.average_respiration_value,
                average_spo2_value=excluded.average_spo2_value,
                resting_heart_rate=excluded.resting_heart_rate,
                average_stress=excluded.average_stress,
                raw_json=excluded.raw_json, updated_at=excluded.updated_at
            """,
            (
                s.calendar_date, s.sleep_time_seconds, s.deep_sleep_seconds,
                s.light_sleep_seconds, s.rem_sleep_seconds, s.awake_seconds,
                s.sleep_score, s.sleep_score_quality, s.average_respiration_value,
                s.average_spo2_value, s.resting_heart_rate, s.average_stress,
                s.raw_json, _now(),
            ),
        )
        conn.commit()

    def get_sleep(self, date_from: str, date_to: str) -> list[SleepData]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM garmin_sleep "
            "WHERE calendar_date >= ? AND calendar_date <= ? "
            "ORDER BY calendar_date",
            (date_from, date_to),
        ).fetchall()
        return [_row_to_sleep(r) for r in rows]

    # ── Stress ─────────────────────────────────────────────────────────────

    def upsert_stress(self, s: StressData) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO garmin_stress (
                calendar_date, avg_stress_level, max_stress_level,
                stress_duration_seconds, rest_duration_seconds,
                activity_duration_seconds, uncategorized_duration_seconds,
                raw_json, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(calendar_date) DO UPDATE SET
                avg_stress_level=excluded.avg_stress_level,
                max_stress_level=excluded.max_stress_level,
                stress_duration_seconds=excluded.stress_duration_seconds,
                rest_duration_seconds=excluded.rest_duration_seconds,
                activity_duration_seconds=excluded.activity_duration_seconds,
                uncategorized_duration_seconds=excluded.uncategorized_duration_seconds,
                raw_json=excluded.raw_json, updated_at=excluded.updated_at
            """,
            (
                s.calendar_date, s.avg_stress_level, s.max_stress_level,
                s.stress_duration_seconds, s.rest_duration_seconds,
                s.activity_duration_seconds, s.uncategorized_duration_seconds,
                s.raw_json, _now(),
            ),
        )
        conn.commit()

    def get_stress(self, date_from: str, date_to: str) -> list[StressData]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM garmin_stress "
            "WHERE calendar_date >= ? AND calendar_date <= ? "
            "ORDER BY calendar_date",
            (date_from, date_to),
        ).fetchall()
        return [_row_to_stress(r) for r in rows]

    # ── Body Battery ───────────────────────────────────────────────────────

    def upsert_body_battery(self, b: BodyBatteryData) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO garmin_body_battery (
                calendar_date, start_value, end_value, charged, drained,
                raw_json, updated_at
            ) VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(calendar_date) DO UPDATE SET
                start_value=excluded.start_value, end_value=excluded.end_value,
                charged=excluded.charged, drained=excluded.drained,
                raw_json=excluded.raw_json, updated_at=excluded.updated_at
            """,
            (
                b.calendar_date, b.start_value, b.end_value,
                b.charged, b.drained, b.raw_json, _now(),
            ),
        )
        conn.commit()

    def get_body_battery(
        self, date_from: str, date_to: str
    ) -> list[BodyBatteryData]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM garmin_body_battery "
            "WHERE calendar_date >= ? AND calendar_date <= ? "
            "ORDER BY calendar_date",
            (date_from, date_to),
        ).fetchall()
        return [_row_to_body_battery(r) for r in rows]

    # ── HRV ────────────────────────────────────────────────────────────────

    def upsert_hrv(self, h: HRVData) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO garmin_hrv (
                calendar_date, weekly_avg, last_night, last_5_min,
                baseline_low, baseline_high, status, raw_json, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(calendar_date) DO UPDATE SET
                weekly_avg=excluded.weekly_avg, last_night=excluded.last_night,
                last_5_min=excluded.last_5_min, baseline_low=excluded.baseline_low,
                baseline_high=excluded.baseline_high, status=excluded.status,
                raw_json=excluded.raw_json, updated_at=excluded.updated_at
            """,
            (
                h.calendar_date, h.weekly_avg, h.last_night, h.last_5_min,
                h.baseline_low, h.baseline_high, h.status, h.raw_json, _now(),
            ),
        )
        conn.commit()

    def get_hrv(self, date_from: str, date_to: str) -> list[HRVData]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM garmin_hrv "
            "WHERE calendar_date >= ? AND calendar_date <= ? "
            "ORDER BY calendar_date",
            (date_from, date_to),
        ).fetchall()
        return [_row_to_hrv(r) for r in rows]

    # ── Activities ─────────────────────────────────────────────────────────

    def upsert_activity(self, a: Activity) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO garmin_activities (
                activity_id, activity_name, activity_type, start_time_gmt,
                start_time_local, calendar_date, duration_seconds, distance_meters,
                average_hr, max_hr, calories, average_speed, max_speed,
                aerobic_training_effect, anaerobic_training_effect,
                training_stress_score, steps, average_cadence, elevation_gain,
                elevation_loss, average_power, normalized_power, raw_json, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(activity_id) DO UPDATE SET
                activity_name=excluded.activity_name,
                activity_type=excluded.activity_type,
                start_time_gmt=excluded.start_time_gmt,
                start_time_local=excluded.start_time_local,
                calendar_date=excluded.calendar_date,
                duration_seconds=excluded.duration_seconds,
                distance_meters=excluded.distance_meters,
                average_hr=excluded.average_hr, max_hr=excluded.max_hr,
                calories=excluded.calories,
                average_speed=excluded.average_speed, max_speed=excluded.max_speed,
                aerobic_training_effect=excluded.aerobic_training_effect,
                anaerobic_training_effect=excluded.anaerobic_training_effect,
                training_stress_score=excluded.training_stress_score,
                steps=excluded.steps, average_cadence=excluded.average_cadence,
                elevation_gain=excluded.elevation_gain,
                elevation_loss=excluded.elevation_loss,
                average_power=excluded.average_power,
                normalized_power=excluded.normalized_power,
                raw_json=excluded.raw_json, updated_at=excluded.updated_at
            """,
            (
                a.activity_id, a.activity_name, a.activity_type, a.start_time_gmt,
                a.start_time_local, a.calendar_date, a.duration_seconds,
                a.distance_meters, a.average_hr, a.max_hr, a.calories,
                a.average_speed, a.max_speed, a.aerobic_training_effect,
                a.anaerobic_training_effect, a.training_stress_score, a.steps,
                a.average_cadence, a.elevation_gain, a.elevation_loss,
                a.average_power, a.normalized_power, a.raw_json, _now(),
            ),
        )
        conn.commit()

    def get_activities(self, date_from: str, date_to: str) -> list[Activity]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM garmin_activities "
            "WHERE calendar_date >= ? AND calendar_date <= ? "
            "ORDER BY start_time_gmt",
            (date_from, date_to),
        ).fetchall()
        return [_row_to_activity(r) for r in rows]

    # ── Activity details ───────────────────────────────────────────────────

    def upsert_activity_details(self, d: ActivityDetail) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO garmin_activity_details (activity_id, raw_json, updated_at)
            VALUES (?,?,?)
            ON CONFLICT(activity_id) DO UPDATE SET
                raw_json=excluded.raw_json, updated_at=excluded.updated_at
            """,
            (d.activity_id, d.raw_json, _now()),
        )
        conn.commit()

    def get_activity_detail(self, activity_id: str) -> ActivityDetail | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM garmin_activity_details WHERE activity_id=?",
            (activity_id,),
        ).fetchone()
        if row is None:
            return None
        return ActivityDetail(
            activity_id=row["activity_id"], raw_json=row["raw_json"]
        )

    # ── Raw metrics ────────────────────────────────────────────────────────

    def upsert_metric_raw(
        self, calendar_date: str, metric_type: str, raw: dict[str, Any]
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO garmin_metrics_raw (calendar_date, metric_type, raw_json, updated_at)
            VALUES (?,?,?,?)
            ON CONFLICT(calendar_date, metric_type) DO UPDATE SET
                raw_json=excluded.raw_json, updated_at=excluded.updated_at
            """,
            (calendar_date, metric_type, json.dumps(raw), _now()),
        )
        conn.commit()

    def get_metrics_raw(
        self, date_from: str, date_to: str, metric_type: str
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT calendar_date, raw_json FROM garmin_metrics_raw "
            "WHERE calendar_date >= ? AND calendar_date <= ? AND metric_type=? "
            "ORDER BY calendar_date",
            (date_from, date_to, metric_type),
        ).fetchall()
        return [
            {"calendar_date": r["calendar_date"], **json.loads(r["raw_json"])}
            for r in rows
        ]

    # ── Weigh-ins ──────────────────────────────────────────────────────────

    def upsert_weigh_in(self, w: WeightEntry) -> None:
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO garmin_weigh_ins (
                calendar_date, weight_kg, weight_lbs, bmi, body_fat_pct,
                muscle_mass_kg, bone_mass_kg, body_water_pct, source_type,
                raw_json, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(calendar_date) DO UPDATE SET
                weight_kg=excluded.weight_kg,
                weight_lbs=excluded.weight_lbs,
                bmi=excluded.bmi,
                body_fat_pct=excluded.body_fat_pct,
                muscle_mass_kg=excluded.muscle_mass_kg,
                bone_mass_kg=excluded.bone_mass_kg,
                body_water_pct=excluded.body_water_pct,
                source_type=excluded.source_type,
                raw_json=excluded.raw_json,
                updated_at=excluded.updated_at
            """,
            (
                w.calendar_date, w.weight_kg, w.weight_lbs, w.bmi,
                w.body_fat_pct, w.muscle_mass_kg, w.bone_mass_kg,
                w.body_water_pct, w.source_type, w.raw_json, _now(),
            ),
        )
        conn.commit()

    def get_weigh_ins(self, date_from: str, date_to: str) -> list[WeightEntry]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM garmin_weigh_ins "
            "WHERE calendar_date >= ? AND calendar_date <= ? "
            "ORDER BY calendar_date",
            (date_from, date_to),
        ).fetchall()
        return [_row_to_weight_entry(r) for r in rows]

    def get_latest_weigh_in(self) -> WeightEntry | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM garmin_weigh_ins WHERE weight_kg IS NOT NULL "
            "ORDER BY calendar_date DESC LIMIT 1"
        ).fetchone()
        return _row_to_weight_entry(row) if row else None


# ── Row mappers ────────────────────────────────────────────────────────────

def _row_to_daily_summary(r: sqlite3.Row) -> DailySummary:
    return DailySummary(
        calendar_date=r["calendar_date"],
        steps=r["steps"],
        step_goal=r["step_goal"],
        total_kilocalories=r["total_kilocalories"],
        active_kilocalories=r["active_kilocalories"],
        resting_heart_rate=r["resting_heart_rate"],
        average_heart_rate=r["average_heart_rate"],
        max_heart_rate=r["max_heart_rate"],
        min_heart_rate=r["min_heart_rate"],
        total_distance_meters=r["total_distance_meters"],
        highly_active_seconds=r["highly_active_seconds"],
        active_seconds=r["active_seconds"],
        sedentary_seconds=r["sedentary_seconds"],
        sleeping_seconds=r["sleeping_seconds"],
        moderate_intensity_minutes=r["moderate_intensity_minutes"],
        vigorous_intensity_minutes=r["vigorous_intensity_minutes"],
        body_battery_charged=r["body_battery_charged"],
        body_battery_drained=r["body_battery_drained"],
        body_battery_highest=r["body_battery_highest"],
        body_battery_lowest=r["body_battery_lowest"],
        average_stress_level=r["average_stress_level"],
        max_stress_level=r["max_stress_level"],
        raw_json=r["raw_json"],
    )


def _row_to_sleep(r: sqlite3.Row) -> SleepData:
    return SleepData(
        calendar_date=r["calendar_date"],
        sleep_time_seconds=r["sleep_time_seconds"],
        deep_sleep_seconds=r["deep_sleep_seconds"],
        light_sleep_seconds=r["light_sleep_seconds"],
        rem_sleep_seconds=r["rem_sleep_seconds"],
        awake_seconds=r["awake_seconds"],
        sleep_score=r["sleep_score"],
        sleep_score_quality=r["sleep_score_quality"],
        average_respiration_value=r["average_respiration_value"],
        average_spo2_value=r["average_spo2_value"],
        resting_heart_rate=r["resting_heart_rate"],
        average_stress=r["average_stress"],
        raw_json=r["raw_json"],
    )


def _row_to_stress(r: sqlite3.Row) -> StressData:
    return StressData(
        calendar_date=r["calendar_date"],
        avg_stress_level=r["avg_stress_level"],
        max_stress_level=r["max_stress_level"],
        stress_duration_seconds=r["stress_duration_seconds"],
        rest_duration_seconds=r["rest_duration_seconds"],
        activity_duration_seconds=r["activity_duration_seconds"],
        uncategorized_duration_seconds=r["uncategorized_duration_seconds"],
        raw_json=r["raw_json"],
    )


def _row_to_body_battery(r: sqlite3.Row) -> BodyBatteryData:
    return BodyBatteryData(
        calendar_date=r["calendar_date"],
        start_value=r["start_value"],
        end_value=r["end_value"],
        charged=r["charged"],
        drained=r["drained"],
        raw_json=r["raw_json"],
    )


def _row_to_hrv(r: sqlite3.Row) -> HRVData:
    return HRVData(
        calendar_date=r["calendar_date"],
        weekly_avg=r["weekly_avg"],
        last_night=r["last_night"],
        last_5_min=r["last_5_min"],
        baseline_low=r["baseline_low"],
        baseline_high=r["baseline_high"],
        status=r["status"],
        raw_json=r["raw_json"],
    )


def _row_to_activity(r: sqlite3.Row) -> Activity:
    return Activity(
        activity_id=r["activity_id"],
        activity_name=r["activity_name"],
        activity_type=r["activity_type"],
        start_time_gmt=r["start_time_gmt"],
        start_time_local=r["start_time_local"],
        calendar_date=r["calendar_date"],
        duration_seconds=r["duration_seconds"],
        distance_meters=r["distance_meters"],
        average_hr=r["average_hr"],
        max_hr=r["max_hr"],
        calories=r["calories"],
        average_speed=r["average_speed"],
        max_speed=r["max_speed"],
        aerobic_training_effect=r["aerobic_training_effect"],
        anaerobic_training_effect=r["anaerobic_training_effect"],
        training_stress_score=r["training_stress_score"],
        steps=r["steps"],
        average_cadence=r["average_cadence"],
        elevation_gain=r["elevation_gain"],
        elevation_loss=r["elevation_loss"],
        average_power=r["average_power"],
        normalized_power=r["normalized_power"],
        raw_json=r["raw_json"],
    )


def _row_to_weight_entry(r: sqlite3.Row) -> WeightEntry:
    return WeightEntry(
        calendar_date=r["calendar_date"],
        weight_kg=r["weight_kg"],
        weight_lbs=r["weight_lbs"],
        bmi=r["bmi"],
        body_fat_pct=r["body_fat_pct"],
        muscle_mass_kg=r["muscle_mass_kg"],
        bone_mass_kg=r["bone_mass_kg"],
        body_water_pct=r["body_water_pct"],
        source_type=r["source_type"],
        raw_json=r["raw_json"],
    )
