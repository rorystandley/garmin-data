"""Tests for CLI commands using Click's test runner."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from integrations.garmin.cli import (
    activities,
    ai_context,
    insights,
    summary,
    sync,
)
from integrations.garmin.models import SyncResult


@pytest.fixture
def runner():
    return CliRunner()


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
def env_vars():
    return {"GARMIN_EMAIL": "test@example.com", "GARMIN_PASSWORD": "testpass"}


class TestSyncCommand:
    def test_success(self, runner, env_vars):
        fake_result = SyncResult(date_from="2026-01-01", date_to="2026-01-07", records_synced=42)
        with patch("integrations.garmin.cli.load_config") as mock_cfg, \
             patch("integrations.garmin.service.sync_garmin_data", return_value=fake_result):
            from integrations.garmin.config import GarminConfig
            from pathlib import Path
            mock_cfg.return_value = GarminConfig(
                email="t@t.com", password="p",
                token_dir=Path("/tmp/tokens"), db_path=Path("/tmp/test.db"),
                sync_days_default=7, log_level="WARNING"
            )
            result = runner.invoke(sync, ["--days", "7"])
        assert result.exit_code == 0
        assert "42 records" in result.output

    def test_missing_credentials_exits_1(self, runner):
        with patch("integrations.garmin.cli.load_config") as mock_cfg:
            from integrations.garmin.config import ConfigError
            mock_cfg.side_effect = ConfigError("GARMIN_EMAIL is not set")
            result = runner.invoke(sync, ["--days", "7"])
        assert result.exit_code == 1

    def test_invalid_from_date_exits_1(self, runner, env_vars):
        with patch("integrations.garmin.cli.load_config") as mock_cfg:
            from integrations.garmin.config import GarminConfig
            from pathlib import Path
            mock_cfg.return_value = GarminConfig(
                email="t@t.com", password="p",
                token_dir=Path("/tmp/tokens"), db_path=Path("/tmp/test.db"),
                sync_days_default=7, log_level="WARNING"
            )
            result = runner.invoke(sync, ["--from", "not-a-date"])
        assert result.exit_code == 1

    def test_errors_reported(self, runner):
        fake_result = SyncResult(
            date_from="2026-01-01", date_to="2026-01-07",
            records_synced=10, errors=["hrv/2026-01-01: 404"]
        )
        with patch("integrations.garmin.cli.load_config") as mock_cfg, \
             patch("integrations.garmin.service.sync_garmin_data", return_value=fake_result):
            from integrations.garmin.config import GarminConfig
            from pathlib import Path
            mock_cfg.return_value = GarminConfig(
                email="t@t.com", password="p",
                token_dir=Path("/tmp/tokens"), db_path=Path("/tmp/test.db"),
                sync_days_default=7, log_level="WARNING"
            )
            result = runner.invoke(sync, ["--days", "7"])
        assert result.exit_code == 0
        assert "hrv" in result.output


class TestSummaryCommand:
    def _fake_cfg(self, tmp_path=None):
        from integrations.garmin.config import GarminConfig
        from pathlib import Path
        return GarminConfig(
            email="t@t.com", password="p",
            token_dir=Path("/tmp/tokens"), db_path=Path("/tmp/test.db"),
            sync_days_default=7, log_level="WARNING"
        )

    def test_text_format(self, runner):
        fake_summary = {
            "period": {"from": "2026-01-01", "to": "2026-01-07", "days": 7},
            "summary": {
                "headline": "Test headline",
                "key_findings": [],
                "positive_signals": [],
                "risk_signals": [],
                "recommended_focus": [],
            },
            "metrics": {},
            "recommendations": [],
        }
        with patch("integrations.garmin.cli.load_config", return_value=self._fake_cfg()), \
             patch("integrations.garmin.service.get_garmin_summary", return_value=fake_summary):
            result = runner.invoke(summary, ["--days", "7", "--format", "text"])
        assert result.exit_code == 0
        assert "Test headline" in result.output

    def test_json_format(self, runner):
        fake_summary = {
            "period": {"from": "2026-01-01", "to": "2026-01-07", "days": 7},
            "summary": {"headline": "x", "key_findings": [], "positive_signals": [], "risk_signals": [], "recommended_focus": []},
            "metrics": {},
            "recommendations": [],
        }
        with patch("integrations.garmin.cli.load_config", return_value=self._fake_cfg()), \
             patch("integrations.garmin.service.get_garmin_summary", return_value=fake_summary):
            result = runner.invoke(summary, ["--days", "7", "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["period"]["days"] == 7


class TestActivitiesCommand:
    def _fake_cfg(self):
        from integrations.garmin.config import GarminConfig
        from pathlib import Path
        return GarminConfig(
            email="t@t.com", password="p",
            token_dir=Path("/tmp/tokens"), db_path=Path("/tmp/test.db"),
            sync_days_default=7, log_level="WARNING"
        )

    def test_no_activities(self, runner):
        with patch("integrations.garmin.cli.load_config", return_value=self._fake_cfg()), \
             patch("integrations.garmin.service.get_recent_activities", return_value=[]):
            result = runner.invoke(activities, ["--days", "7"])
        assert result.exit_code == 0
        assert "No activities" in result.output

    def test_with_activities_text(self, runner):
        acts = [
            {
                "activity_id": "123",
                "date": "2026-01-15",
                "name": "Morning Run",
                "type": "running",
                "duration_minutes": 60.0,
                "distance_km": 10.0,
                "avg_hr": 155,
                "max_hr": 178,
                "calories": 620.0,
                "tss": 65.0,
            }
        ]
        with patch("integrations.garmin.cli.load_config", return_value=self._fake_cfg()), \
             patch("integrations.garmin.service.get_recent_activities", return_value=acts):
            result = runner.invoke(activities, ["--days", "7"])
        assert result.exit_code == 0
        assert "Morning Run" in result.output

    def test_json_format(self, runner):
        acts = [
            {
                "activity_id": "123", "date": "2026-01-15", "name": "Run",
                "type": "running", "duration_minutes": 60.0,
                "distance_km": 10.0, "avg_hr": 155, "max_hr": 178,
                "calories": 620.0, "tss": 65.0,
            }
        ]
        with patch("integrations.garmin.cli.load_config", return_value=self._fake_cfg()), \
             patch("integrations.garmin.service.get_recent_activities", return_value=acts):
            result = runner.invoke(activities, ["--days", "7", "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed) == 1


class TestAiContextCommand:
    def _fake_cfg(self):
        from integrations.garmin.config import GarminConfig
        from pathlib import Path
        return GarminConfig(
            email="t@t.com", password="p",
            token_dir=Path("/tmp/tokens"), db_path=Path("/tmp/test.db"),
            sync_days_default=7, log_level="WARNING"
        )

    def test_text_output(self, runner):
        with patch("integrations.garmin.cli.load_config", return_value=self._fake_cfg()), \
             patch("integrations.garmin.service.get_ai_context", return_value="AI context text here"):
            result = runner.invoke(ai_context, ["--days", "7", "--format", "text"])
        assert result.exit_code == 0
        assert "AI context text here" in result.output

    def test_json_output(self, runner):
        fake_json = {"period": {"days": 7}, "disclaimer": "Not medical advice."}
        with patch("integrations.garmin.cli.load_config", return_value=self._fake_cfg()), \
             patch("integrations.garmin.service.get_ai_context", return_value=fake_json):
            result = runner.invoke(ai_context, ["--days", "7", "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "disclaimer" in parsed


class TestInsightsCommand:
    def _fake_cfg(self):
        from integrations.garmin.config import GarminConfig
        from pathlib import Path
        return GarminConfig(
            email="t@t.com", password="p",
            token_dir=Path("/tmp/tokens"), db_path=Path("/tmp/test.db"),
            sync_days_default=7, log_level="WARNING"
        )

    def test_text_with_recommendations(self, runner):
        fake_summary = {
            "period": {"from": "2026-01-01", "to": "2026-01-07", "days": 7},
            "summary": {
                "headline": "All good",
                "key_findings": [],
                "positive_signals": ["Great sleep"],
                "risk_signals": [],
                "recommended_focus": [],
            },
            "metrics": {},
            "recommendations": [
                {
                    "title": "Sleep more",
                    "reason": "Short nights",
                    "suggested_action": "Bed by 10pm",
                    "confidence": "high",
                    "supporting_data": [],
                }
            ],
        }
        with patch("integrations.garmin.cli.load_config", return_value=self._fake_cfg()), \
             patch("integrations.garmin.service.get_garmin_summary", return_value=fake_summary):
            result = runner.invoke(insights, ["--days", "7"])
        assert result.exit_code == 0
        assert "Sleep more" in result.output
        assert "HIGH" in result.output
