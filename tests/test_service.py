"""Tests for the service layer — verifies wiring without live Garmin credentials."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from integrations.garmin.models import DailySummary, SleepData, StressData
from integrations.garmin.service import (
    get_ai_context,
    get_garmin_summary,
    get_recent_activities,
    get_recovery_signals,
    get_sleep_trends,
    get_training_recommendations,
    sync_garmin_data,
)


@pytest.fixture
def mock_config(tmp_path):
    from integrations.garmin.config import GarminConfig
    return GarminConfig(
        email="test@example.com",
        password="testpass",
        token_dir=tmp_path / "tokens",
        db_path=tmp_path / "test.db",
        sync_days_default=7,
        log_level="WARNING",
    )


@pytest.fixture
def patched_auth(mock_garmin_client):
    """Patch get_authenticated_client to return the mock client."""
    with patch(
        "integrations.garmin.service.get_authenticated_client",
        return_value=mock_garmin_client,
    ) as p:
        yield p


class TestSyncGarminData:
    def test_returns_sync_result(self, mock_config, patched_auth):
        result = sync_garmin_data(days=3, config=mock_config)
        assert result.date_from is not None
        assert result.date_to is not None

    def test_records_synced_positive(self, mock_config, patched_auth):
        result = sync_garmin_data(days=3, config=mock_config)
        assert result.records_synced >= 0

    def test_uses_default_days_from_config(self, mock_config, patched_auth):
        result = sync_garmin_data(config=mock_config)
        from_date = date.fromisoformat(result.date_from)
        to_date = date.fromisoformat(result.date_to)
        delta = (to_date - from_date).days + 1
        assert delta == mock_config.sync_days_default

    def test_explicit_date_range(self, mock_config, patched_auth):
        result = sync_garmin_data(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 7),
            config=mock_config,
        )
        assert result.date_from == "2026-01-01"
        assert result.date_to == "2026-01-07"

    def test_partial_garmin_failures_dont_crash(self, mock_config, patched_auth, mock_garmin_client):
        mock_garmin_client.get_hrv_data.side_effect = Exception("HRV not available")
        mock_garmin_client.get_training_readiness.side_effect = Exception("404 Not Found")
        result = sync_garmin_data(days=2, config=mock_config)
        # Should still complete without raising
        assert result is not None
        # Errors should be recorded
        assert len(result.errors) >= 2


class TestGetGarminSummary:
    def test_returns_dict(self, mock_config, populated_storage):
        with patch("integrations.garmin.service._make_storage", return_value=populated_storage):
            result = get_garmin_summary(days=7, config=mock_config)
        assert isinstance(result, dict)
        assert "period" in result
        assert "metrics" in result

    def test_period_matches_days(self, mock_config, populated_storage):
        with patch("integrations.garmin.service._make_storage", return_value=populated_storage):
            result = get_garmin_summary(days=7, config=mock_config)
        assert result["period"]["days"] == 7


class TestGetRecentActivities:
    def test_returns_list(self, mock_config, sample_storage):
        from datetime import date
        from integrations.garmin.models import Activity
        today = date.today().isoformat()
        sample_storage.upsert_activity(Activity(
            activity_id="test_act",
            activity_name="Test Run",
            activity_type="running",
            calendar_date=today,
            duration_seconds=3600.0,
            distance_meters=10000.0,
        ))
        with patch("integrations.garmin.service._make_storage", return_value=sample_storage):
            result = get_recent_activities(days=30, config=mock_config)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["activity_id"] == "test_act"

    def test_empty_returns_list(self, mock_config, sample_storage):
        with patch("integrations.garmin.service._make_storage", return_value=sample_storage):
            result = get_recent_activities(days=7, config=mock_config)
        assert result == []


class TestGetSleepTrends:
    def test_returns_dict(self, mock_config, populated_storage):
        with patch("integrations.garmin.service._make_storage", return_value=populated_storage):
            result = get_sleep_trends(days=7, config=mock_config)
        assert isinstance(result, dict)
        assert result["available"] is True

    def test_empty_storage(self, mock_config, sample_storage):
        with patch("integrations.garmin.service._make_storage", return_value=sample_storage):
            result = get_sleep_trends(days=7, config=mock_config)
        assert result["available"] is False


class TestGetRecoverySignals:
    def test_returns_dict_with_expected_keys(self, mock_config, populated_storage):
        with patch("integrations.garmin.service._make_storage", return_value=populated_storage):
            result = get_recovery_signals(days=7, config=mock_config)
        assert "body_battery" in result
        assert "hrv" in result
        assert "sleep" in result
        assert "risk_signals" in result


class TestGetTrainingRecommendations:
    def test_returns_list(self, mock_config, populated_storage):
        with patch("integrations.garmin.service._make_storage", return_value=populated_storage):
            result = get_training_recommendations(days=7, config=mock_config)
        assert isinstance(result, list)


class TestGetAiContext:
    def test_text_format(self, mock_config, populated_storage):
        with patch("integrations.garmin.service._make_storage", return_value=populated_storage):
            result = get_ai_context(days=7, format="text", config=mock_config)
        assert isinstance(result, str)
        assert "GARMIN" in result

    def test_json_format(self, mock_config, populated_storage):
        with patch("integrations.garmin.service._make_storage", return_value=populated_storage):
            result = get_ai_context(days=7, format="json", config=mock_config)
        assert isinstance(result, dict)
        assert "disclaimer" in result
