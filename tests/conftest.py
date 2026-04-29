"""Shared test fixtures. No live Garmin credentials required."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from integrations.garmin.models import (
    BodyBatteryData,
    DailySummary,
    HRVData,
    SleepData,
    StressData,
    WeightEntry,
)
from integrations.garmin.storage import GarminStorage

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "garmin"


def load_fixture(name: str) -> dict | list:
    return json.loads((FIXTURES_DIR / f"{name}.json").read_text())


@pytest.fixture
def sample_storage(tmp_path):
    """In-memory-like storage backed by a temp file (avoids :memory: connection-sharing issues)."""
    db_path = tmp_path / "test_garmin.db"
    storage = GarminStorage(db_path)
    storage.initialize()
    yield storage
    storage.close()


@pytest.fixture
def mock_garmin_client():
    """Mock GarminClientProtocol using fixture data."""
    client = MagicMock()

    daily = load_fixture("daily_summary")
    sleep_f = load_fixture("sleep")
    stress_f = load_fixture("stress")
    bb_list = load_fixture("body_battery")
    hrv_f = load_fixture("hrv")
    acts = load_fixture("activities")

    client.get_user_summary.return_value = daily
    client.get_sleep_data.return_value = sleep_f
    client.get_stress_data.return_value = stress_f
    client.get_body_battery.return_value = bb_list
    client.get_hrv_data.return_value = hrv_f
    client.get_training_readiness.return_value = {"trainingReadiness": 72, "calendarDate": "2026-01-15"}
    client.get_training_status.return_value = {"trainingStatusPhrase": "PRODUCTIVE", "calendarDate": "2026-01-15"}
    client.get_activities_by_date.return_value = acts
    client.get_activity_details.return_value = {"activityId": "12345001", "summaryDTO": {}}
    client.get_body_composition.return_value = {"dateWeightList": [
        {"calendarDate": "2026-01-15", "weight": 75000, "bmi": 22.5}
    ]}
    client.get_steps_data.return_value = []
    client.get_heart_rates.return_value = {}
    client.get_rhr_day.return_value = {"value": 54, "calendarDate": "2026-01-15"}
    client.get_stress_data.return_value = stress_f
    client.get_daily_weigh_ins.return_value = {"dateWeightList": [
        {"weight": 88000, "bmi": 28.6, "sourceType": "manual"}
    ]}
    client.get_user_profile.return_value = {
        "displayName": "testuser",
        "userProfileId": 12345,
    }

    return client


@pytest.fixture
def populated_storage(sample_storage):
    """Storage pre-populated with 7 days ending today so service date-range queries find data."""
    from datetime import date, timedelta

    base = date.today() - timedelta(days=6)

    # Insert 7 days of data with slight variation
    for i in range(7):
        d = (base + timedelta(days=i)).isoformat()

        sample_storage.upsert_daily_summary(DailySummary(
            calendar_date=d,
            steps=8000 + i * 200,
            step_goal=10000,
            resting_heart_rate=54 + i,
            average_heart_rate=68,
            total_kilocalories=2300.0,
            active_kilocalories=400.0,
            moderate_intensity_minutes=20,
            vigorous_intensity_minutes=10,
            average_stress_level=35 + i * 2,
            body_battery_highest=80,
            body_battery_lowest=30,
        ))

        sample_storage.upsert_sleep(SleepData(
            calendar_date=d,
            sleep_time_seconds=25200 + i * 600,  # 7h + variations
            deep_sleep_seconds=5400,
            light_sleep_seconds=12600,
            rem_sleep_seconds=5400,
            awake_seconds=1800,
            sleep_score=75 + i,
        ))

        sample_storage.upsert_stress(StressData(
            calendar_date=d,
            avg_stress_level=35 + i * 2,
            max_stress_level=70,
            stress_duration_seconds=18000,
            rest_duration_seconds=28800,
        ))

        sample_storage.upsert_body_battery(BodyBatteryData(
            calendar_date=d,
            start_value=70 - i * 2,
            end_value=75 - i * 2,
            charged=45,
            drained=40,
        ))

        sample_storage.upsert_hrv(HRVData(
            calendar_date=d,
            weekly_avg=60 + i,
            last_night=62 + i,
            status="BALANCED",
        ))

    # Two weigh-ins spaced across the period (weekly cadence)
    sample_storage.upsert_weigh_in(WeightEntry(
        calendar_date=base.isoformat(),
        weight_kg=88.5,
        weight_lbs=195.1,
        bmi=29.0,
        source_type="manual",
    ))
    sample_storage.upsert_weigh_in(WeightEntry(
        calendar_date=(base + timedelta(days=6)).isoformat(),
        weight_kg=88.0,
        weight_lbs=194.0,
        bmi=28.9,
        source_type="manual",
    ))

    return sample_storage
