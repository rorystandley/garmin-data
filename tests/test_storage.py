"""Tests for GarminStorage — idempotency, range queries, upserts."""

from __future__ import annotations

import pytest

from integrations.garmin.models import (
    Activity,
    ActivityDetail,
    BodyBatteryData,
    DailySummary,
    HRVData,
    SleepData,
    StressData,
    WeightEntry,
)
from integrations.garmin.storage import GarminStorage


def make_summary(calendar_date: str, steps: int = 8000) -> DailySummary:
    return DailySummary(calendar_date=calendar_date, steps=steps, resting_heart_rate=55)


def make_sleep(calendar_date: str, seconds: int = 25200) -> SleepData:
    return SleepData(calendar_date=calendar_date, sleep_time_seconds=seconds)


class TestDailySummaryUpsert:
    def test_insert(self, sample_storage):
        sample_storage.upsert_daily_summary(make_summary("2026-01-01"))
        rows = sample_storage.get_daily_summaries("2026-01-01", "2026-01-01")
        assert len(rows) == 1
        assert rows[0].calendar_date == "2026-01-01"
        assert rows[0].steps == 8000

    def test_upsert_no_duplicate(self, sample_storage):
        sample_storage.upsert_daily_summary(make_summary("2026-01-01", steps=8000))
        sample_storage.upsert_daily_summary(make_summary("2026-01-01", steps=9000))
        rows = sample_storage.get_daily_summaries("2026-01-01", "2026-01-01")
        assert len(rows) == 1
        assert rows[0].steps == 9000  # updated

    def test_range_query(self, sample_storage):
        for day in ["2026-01-01", "2026-01-02", "2026-01-03"]:
            sample_storage.upsert_daily_summary(make_summary(day))
        rows = sample_storage.get_daily_summaries("2026-01-01", "2026-01-02")
        assert len(rows) == 2
        assert rows[0].calendar_date == "2026-01-01"
        assert rows[1].calendar_date == "2026-01-02"

    def test_empty_range(self, sample_storage):
        rows = sample_storage.get_daily_summaries("2025-01-01", "2025-01-31")
        assert rows == []


class TestSleepUpsert:
    def test_insert(self, sample_storage):
        sample_storage.upsert_sleep(make_sleep("2026-01-01"))
        rows = sample_storage.get_sleep("2026-01-01", "2026-01-01")
        assert len(rows) == 1
        assert rows[0].sleep_time_seconds == 25200

    def test_upsert_no_duplicate(self, sample_storage):
        sample_storage.upsert_sleep(make_sleep("2026-01-01", seconds=25200))
        sample_storage.upsert_sleep(make_sleep("2026-01-01", seconds=28800))
        rows = sample_storage.get_sleep("2026-01-01", "2026-01-01")
        assert len(rows) == 1
        assert rows[0].sleep_time_seconds == 28800


class TestStressUpsert:
    def test_insert(self, sample_storage):
        sample_storage.upsert_stress(StressData(calendar_date="2026-01-01", avg_stress_level=42))
        rows = sample_storage.get_stress("2026-01-01", "2026-01-01")
        assert len(rows) == 1
        assert rows[0].avg_stress_level == 42

    def test_upsert_updates_value(self, sample_storage):
        sample_storage.upsert_stress(StressData(calendar_date="2026-01-01", avg_stress_level=42))
        sample_storage.upsert_stress(StressData(calendar_date="2026-01-01", avg_stress_level=55))
        rows = sample_storage.get_stress("2026-01-01", "2026-01-01")
        assert len(rows) == 1
        assert rows[0].avg_stress_level == 55


class TestBodyBatteryUpsert:
    def test_insert(self, sample_storage):
        sample_storage.upsert_body_battery(
            BodyBatteryData(calendar_date="2026-01-01", start_value=70, end_value=45)
        )
        rows = sample_storage.get_body_battery("2026-01-01", "2026-01-01")
        assert len(rows) == 1
        assert rows[0].start_value == 70

    def test_no_duplicate(self, sample_storage):
        sample_storage.upsert_body_battery(
            BodyBatteryData(calendar_date="2026-01-01", end_value=45)
        )
        sample_storage.upsert_body_battery(
            BodyBatteryData(calendar_date="2026-01-01", end_value=60)
        )
        rows = sample_storage.get_body_battery("2026-01-01", "2026-01-01")
        assert len(rows) == 1
        assert rows[0].end_value == 60


class TestHRVUpsert:
    def test_insert(self, sample_storage):
        sample_storage.upsert_hrv(HRVData(calendar_date="2026-01-01", last_night=65))
        rows = sample_storage.get_hrv("2026-01-01", "2026-01-01")
        assert len(rows) == 1
        assert rows[0].last_night == 65

    def test_no_duplicate(self, sample_storage):
        sample_storage.upsert_hrv(HRVData(calendar_date="2026-01-01", last_night=65))
        sample_storage.upsert_hrv(HRVData(calendar_date="2026-01-01", last_night=70))
        rows = sample_storage.get_hrv("2026-01-01", "2026-01-01")
        assert len(rows) == 1
        assert rows[0].last_night == 70


class TestActivityUpsert:
    def make_activity(self, activity_id: str = "act_001") -> Activity:
        return Activity(
            activity_id=activity_id,
            activity_name="Morning Run",
            activity_type="running",
            calendar_date="2026-01-15",
            duration_seconds=3600.0,
            distance_meters=10000.0,
            average_hr=155,
        )

    def test_insert(self, sample_storage):
        sample_storage.upsert_activity(self.make_activity())
        rows = sample_storage.get_activities("2026-01-01", "2026-01-31")
        assert len(rows) == 1
        assert rows[0].activity_id == "act_001"

    def test_no_duplicate(self, sample_storage):
        sample_storage.upsert_activity(self.make_activity())
        a2 = self.make_activity()
        a2.activity_name = "Updated Run"
        sample_storage.upsert_activity(a2)
        rows = sample_storage.get_activities("2026-01-01", "2026-01-31")
        assert len(rows) == 1
        assert rows[0].activity_name == "Updated Run"

    def test_multiple_activities(self, sample_storage):
        sample_storage.upsert_activity(self.make_activity("act_001"))
        sample_storage.upsert_activity(self.make_activity("act_002"))
        rows = sample_storage.get_activities("2026-01-01", "2026-01-31")
        assert len(rows) == 2


class TestActivityDetails:
    def test_upsert_and_fetch(self, sample_storage):
        sample_storage.upsert_activity_details(
            ActivityDetail(activity_id="act_001", raw_json='{"laps": []}')
        )
        detail = sample_storage.get_activity_detail("act_001")
        assert detail is not None
        assert detail.activity_id == "act_001"

    def test_missing_returns_none(self, sample_storage):
        assert sample_storage.get_activity_detail("does_not_exist") is None


class TestMetricsRaw:
    def test_upsert_and_query(self, sample_storage):
        sample_storage.upsert_metric_raw("2026-01-01", "training_status", {"status": "PRODUCTIVE"})
        rows = sample_storage.get_metrics_raw("2026-01-01", "2026-01-01", "training_status")
        assert len(rows) == 1
        assert rows[0]["status"] == "PRODUCTIVE"

    def test_no_duplicate(self, sample_storage):
        sample_storage.upsert_metric_raw("2026-01-01", "weight", {"weight": 75000})
        sample_storage.upsert_metric_raw("2026-01-01", "weight", {"weight": 74800})
        rows = sample_storage.get_metrics_raw("2026-01-01", "2026-01-01", "weight")
        assert len(rows) == 1
        assert rows[0]["weight"] == 74800

    def test_different_metric_types(self, sample_storage):
        sample_storage.upsert_metric_raw("2026-01-01", "weight", {"weight": 75000})
        sample_storage.upsert_metric_raw("2026-01-01", "training_status", {"status": "PRODUCTIVE"})
        weight_rows = sample_storage.get_metrics_raw("2026-01-01", "2026-01-01", "weight")
        status_rows = sample_storage.get_metrics_raw("2026-01-01", "2026-01-01", "training_status")
        assert len(weight_rows) == 1
        assert len(status_rows) == 1


class TestWeighInsUpsert:
    def make_entry(self, calendar_date: str = "2026-01-15", kg: float = 88.0) -> WeightEntry:
        return WeightEntry(
            calendar_date=calendar_date,
            weight_kg=kg,
            weight_lbs=round(kg * 2.20462, 1),
            bmi=28.5,
            source_type="manual",
        )

    def test_insert(self, sample_storage):
        sample_storage.upsert_weigh_in(self.make_entry())
        rows = sample_storage.get_weigh_ins("2026-01-01", "2026-01-31")
        assert len(rows) == 1
        assert rows[0].weight_kg == 88.0
        assert rows[0].calendar_date == "2026-01-15"

    def test_upsert_no_duplicate(self, sample_storage):
        sample_storage.upsert_weigh_in(self.make_entry(kg=88.0))
        sample_storage.upsert_weigh_in(self.make_entry(kg=87.5))
        rows = sample_storage.get_weigh_ins("2026-01-01", "2026-01-31")
        assert len(rows) == 1
        assert rows[0].weight_kg == 87.5

    def test_range_query(self, sample_storage):
        sample_storage.upsert_weigh_in(self.make_entry("2026-01-01", kg=90.0))
        sample_storage.upsert_weigh_in(self.make_entry("2026-01-08", kg=89.5))
        sample_storage.upsert_weigh_in(self.make_entry("2026-01-15", kg=89.0))
        rows = sample_storage.get_weigh_ins("2026-01-01", "2026-01-08")
        assert len(rows) == 2

    def test_get_latest(self, sample_storage):
        sample_storage.upsert_weigh_in(self.make_entry("2026-01-01", kg=90.0))
        sample_storage.upsert_weigh_in(self.make_entry("2026-01-08", kg=89.0))
        latest = sample_storage.get_latest_weigh_in()
        assert latest is not None
        assert latest.calendar_date == "2026-01-08"
        assert latest.weight_kg == 89.0

    def test_get_latest_empty(self, sample_storage):
        assert sample_storage.get_latest_weigh_in() is None


class TestSyncRunTracking:
    def test_start_and_finish(self, sample_storage):
        run_id = sample_storage.start_sync_run("2026-01-01", "2026-01-07")
        assert run_id > 0
        sample_storage.finish_sync_run(run_id, records_synced=42, errors=[])
        # Verify by checking the DB directly
        conn = sample_storage._get_conn()
        row = conn.execute(
            "SELECT status, records_synced FROM garmin_sync_runs WHERE id=?", (run_id,)
        ).fetchone()
        assert row["status"] == "success"
        assert row["records_synced"] == 42

    def test_partial_with_errors(self, sample_storage):
        run_id = sample_storage.start_sync_run("2026-01-01", "2026-01-07")
        sample_storage.finish_sync_run(run_id, records_synced=10, errors=["hrv: 404"])
        conn = sample_storage._get_conn()
        row = conn.execute(
            "SELECT status, error_message FROM garmin_sync_runs WHERE id=?", (run_id,)
        ).fetchone()
        assert row["status"] == "partial"
        assert "hrv" in row["error_message"]
