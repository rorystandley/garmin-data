"""Tests for the AI context generator."""

from __future__ import annotations

from datetime import date

import pytest

from integrations.garmin.ai_context import generate_ai_context, _DISCLAIMER
from integrations.garmin.insights import compute_insights
from integrations.garmin.models import InsightReport


def make_minimal_report() -> InsightReport:
    return InsightReport(
        period_from="2026-01-01",
        period_to="2026-01-07",
        period_days=7,
        headline="Test headline",
        key_findings=["Finding one", "Finding two"],
        positive_signals=["All good"],
        risk_signals=["One concern"],
        recommended_focus=["Sleep more"],
        metrics={
            "sleep": {"available": False, "note": "No data."},
            "stress": {"available": False, "note": "No data."},
            "body_battery": {"available": False, "note": "No data."},
            "heart_rate": {"available": False, "note": "No data."},
            "activity": {"available": False, "workout_count": 0},
            "training": {
                "total_intensity_minutes": 0,
                "total_moderate_intensity_minutes": 0,
                "total_vigorous_intensity_minutes": 0,
                "load_spike_dates": [],
                "max_consecutive_hard_days": 0,
            },
            "hrv": {"available": False, "note": "No data."},
        },
        recommendations=[],
    )


class TestTextOutput:
    def test_returns_string(self):
        report = make_minimal_report()
        result = generate_ai_context(report, format="text")
        assert isinstance(result, str)

    def test_contains_headline(self):
        report = make_minimal_report()
        result = generate_ai_context(report, format="text")
        assert "Test headline" in result

    def test_contains_period(self):
        report = make_minimal_report()
        result = generate_ai_context(report, format="text")
        assert "2026-01-01" in result
        assert "2026-01-07" in result

    def test_contains_disclaimer(self):
        report = make_minimal_report()
        result = generate_ai_context(report, format="text")
        assert _DISCLAIMER in result

    def test_no_raw_data_dumps(self):
        """Context must not contain enormous raw JSON arrays."""
        report = make_minimal_report()
        result = generate_ai_context(report, format="text")
        # Should not contain raw data keys that dump everything
        assert '"dailySleepDTO"' not in result
        assert '"bodyBatteryValues"' not in result

    def test_unavailable_data_noted(self):
        report = make_minimal_report()
        result = generate_ai_context(report, format="text")
        assert "No data" in result or "not available" in result.lower() or "No data." in result

    def test_risk_signals_shown(self):
        report = make_minimal_report()
        result = generate_ai_context(report, format="text")
        assert "One concern" in result

    def test_positive_signals_shown(self):
        report = make_minimal_report()
        result = generate_ai_context(report, format="text")
        assert "All good" in result


class TestJsonOutput:
    def test_returns_dict(self):
        report = make_minimal_report()
        result = generate_ai_context(report, format="json")
        assert isinstance(result, dict)

    def test_contains_disclaimer_key(self):
        report = make_minimal_report()
        result = generate_ai_context(report, format="json")
        assert "disclaimer" in result
        assert _DISCLAIMER in result["disclaimer"]

    def test_contains_period(self):
        report = make_minimal_report()
        result = generate_ai_context(report, format="json")
        assert result["period"]["from"] == "2026-01-01"

    def test_contains_recommendations(self):
        report = make_minimal_report()
        result = generate_ai_context(report, format="json")
        assert "recommendations" in result

    def test_contains_metrics(self):
        report = make_minimal_report()
        result = generate_ai_context(report, format="json")
        assert "metrics" in result


class TestWithRealInsights:
    def test_full_pipeline(self, populated_storage):
        from datetime import date, timedelta
        date_to = date.today()
        date_from = date_to - timedelta(days=6)
        report = compute_insights(populated_storage, date_from, date_to)
        text = generate_ai_context(report, format="text")
        assert len(text) > 100
        assert _DISCLAIMER in text
        assert date_from.isoformat() in text

        json_out = generate_ai_context(report, format="json")
        assert isinstance(json_out, dict)
        assert "disclaimer" in json_out
