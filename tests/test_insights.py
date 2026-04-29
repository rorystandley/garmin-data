"""Tests for the deterministic insight engine."""

from __future__ import annotations

from datetime import date

import pytest

from integrations.garmin.insights import (
    _analyse_body_battery,
    _analyse_heart_rate,
    _analyse_sleep,
    _analyse_stress,
    _analyse_weight,
    _count_max_consecutive,
    _trend,
    compute_insights,
)
from integrations.garmin.models import (
    BodyBatteryData,
    DailySummary,
    HRVData,
    SleepData,
    StressData,
    WeightEntry,
)


class TestTrend:
    def test_improving(self):
        assert _trend([5, 5, 6, 6, 7, 7, 8, 8]) == "improving"

    def test_worsening(self):
        assert _trend([8, 8, 7, 7, 6, 6, 5, 5]) == "worsening"

    def test_stable(self):
        assert _trend([7, 7, 7, 7, 7, 7, 7, 7]) == "stable"

    def test_insufficient_data(self):
        assert _trend([7, 7]) == "insufficient_data"

    def test_handles_none_values(self):
        result = _trend([7, None, 7, None, 8, None, 8, None])
        assert result in ("improving", "stable", "worsening", "insufficient_data")


class TestAnalyseSleep:
    def make_sleep(self, hours: float, date: str = "2026-01-01") -> SleepData:
        return SleepData(
            calendar_date=date,
            sleep_time_seconds=int(hours * 3600),
            sleep_score=75,
        )

    def test_avg_duration(self):
        data = [self.make_sleep(7.0, "2026-01-01"), self.make_sleep(8.0, "2026-01-02")]
        result = _analyse_sleep(data, 2)
        assert result["avg_duration_hours"] == 7.5

    def test_nights_under_7h(self):
        data = [
            self.make_sleep(6.0, "2026-01-01"),
            self.make_sleep(7.5, "2026-01-02"),
            self.make_sleep(5.5, "2026-01-03"),
        ]
        result = _analyse_sleep(data, 3)
        assert result["nights_under_7h"] == 2

    def test_nights_under_6h(self):
        data = [
            self.make_sleep(5.5, "2026-01-01"),
            self.make_sleep(7.0, "2026-01-02"),
        ]
        result = _analyse_sleep(data, 2)
        assert result["nights_under_6h"] == 1

    def test_empty_returns_unavailable(self):
        result = _analyse_sleep([], 7)
        assert result["available"] is False

    def test_available_flag(self):
        result = _analyse_sleep([self.make_sleep(7.0)], 1)
        assert result["available"] is True

    def test_missing_sleep_seconds_ignored(self):
        data = [SleepData(calendar_date="2026-01-01", sleep_time_seconds=None)]
        result = _analyse_sleep(data, 1)
        assert result["avg_duration_hours"] is None


class TestAnalyseStress:
    def make_stress(self, avg: int, date: str = "2026-01-01") -> StressData:
        return StressData(calendar_date=date, avg_stress_level=avg, max_stress_level=80)

    def test_avg_stress(self):
        data = [self.make_stress(30), self.make_stress(50, "2026-01-02")]
        result = _analyse_stress(data, 2)
        assert result["avg_stress"] == 40.0

    def test_high_stress_days(self):
        data = [
            self.make_stress(60, "2026-01-01"),
            self.make_stress(30, "2026-01-02"),
            self.make_stress(55, "2026-01-03"),
        ]
        result = _analyse_stress(data, 3)
        assert result["high_stress_days"] == 2

    def test_empty_returns_unavailable(self):
        result = _analyse_stress([], 7)
        assert result["available"] is False


class TestAnalyseBodyBattery:
    def make_bb(self, end: int, start: int = 70, date: str = "2026-01-01") -> BodyBatteryData:
        return BodyBatteryData(
            calendar_date=date, start_value=start, end_value=end, charged=45, drained=40
        )

    def test_avg_end(self):
        data = [self.make_bb(60, date="2026-01-01"), self.make_bb(40, date="2026-01-02")]
        result = _analyse_body_battery(data)
        assert result["avg_end"] == 50.0

    def test_days_below_20(self):
        data = [
            self.make_bb(15, date="2026-01-01"),
            self.make_bb(50, date="2026-01-02"),
            self.make_bb(18, date="2026-01-03"),
        ]
        result = _analyse_body_battery(data)
        assert result["days_ending_below_20"] == 2

    def test_empty_returns_unavailable(self):
        result = _analyse_body_battery([])
        assert result["available"] is False


class TestAnalyseHeartRate:
    def make_summary(self, rhr: int, date: str = "2026-01-01") -> DailySummary:
        return DailySummary(calendar_date=date, resting_heart_rate=rhr)

    def test_avg_rhr(self):
        data = [self.make_summary(52, "2026-01-01"), self.make_summary(58, "2026-01-02")]
        result = _analyse_heart_rate(data)
        assert result["avg_resting_hr"] == 55.0

    def test_empty_returns_unavailable(self):
        result = _analyse_heart_rate([])
        assert result["available"] is False

    def test_all_none_returns_unavailable(self):
        data = [DailySummary(calendar_date="2026-01-01", resting_heart_rate=None)]
        result = _analyse_heart_rate(data)
        assert result["available"] is False


class TestAnalyseWeight:
    def make_entry(self, date: str, kg: float) -> WeightEntry:
        return WeightEntry(
            calendar_date=date,
            weight_kg=kg,
            weight_lbs=round(kg * 2.20462, 1),
            bmi=round(kg / (1.75 ** 2), 1),
        )

    def test_no_data_returns_unavailable(self):
        result = _analyse_weight([], None)
        assert result["available"] is False

    def test_single_entry_available(self):
        entry = self.make_entry("2026-01-15", 88.0)
        result = _analyse_weight([entry], entry)
        assert result["available"] is True
        assert result["latest_weight_kg"] == 88.0
        assert result["entries_in_period"] == 1

    def test_change_calculation(self):
        first = self.make_entry("2026-01-01", 90.0)
        last = self.make_entry("2026-01-08", 89.0)
        result = _analyse_weight([first, last], last)
        assert result["change_kg"] == -1.0
        assert result["change_lbs"] is not None
        assert result["change_lbs"] < 0

    def test_no_change_when_single_entry(self):
        entry = self.make_entry("2026-01-01", 88.0)
        result = _analyse_weight([entry], entry)
        assert result["change_kg"] is None
        assert result["change_lbs"] is None

    def test_latest_from_latest_param(self):
        in_period = self.make_entry("2026-01-01", 90.0)
        outside_latest = self.make_entry("2025-12-01", 91.0)
        result = _analyse_weight([in_period], outside_latest)
        assert result["latest_weight_kg"] == 91.0
        assert result["latest_date"] == "2025-12-01"


class TestCountMaxConsecutive:
    def test_consecutive_dates(self):
        dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
        assert _count_max_consecutive(dates) == 3

    def test_gap_in_dates(self):
        dates = ["2026-01-01", "2026-01-02", "2026-01-05", "2026-01-06"]
        assert _count_max_consecutive(dates) == 2

    def test_single_date(self):
        assert _count_max_consecutive(["2026-01-01"]) == 1

    def test_empty(self):
        assert _count_max_consecutive([]) == 0


class TestComputeInsights:
    def _week_range(self):
        from datetime import date, timedelta
        date_to = date.today()
        date_from = date_to - timedelta(days=6)
        return date_from, date_to

    def test_returns_insight_report(self, populated_storage):
        date_from, date_to = self._week_range()
        report = compute_insights(populated_storage, date_from, date_to)
        assert report.period_from == date_from.isoformat()
        assert report.period_to == date_to.isoformat()
        assert report.period_days == 7

    def test_metrics_populated(self, populated_storage):
        date_from, date_to = self._week_range()
        report = compute_insights(populated_storage, date_from, date_to)
        assert report.metrics["sleep"]["available"] is True
        assert report.metrics["stress"]["available"] is True
        assert report.metrics["body_battery"]["available"] is True
        assert report.metrics["heart_rate"]["available"] is True
        assert report.metrics["weight"]["available"] is True

    def test_empty_storage_does_not_crash(self, sample_storage):
        report = compute_insights(
            sample_storage,
            date(2026, 1, 1),
            date(2026, 1, 7),
        )
        assert report.metrics["sleep"]["available"] is False
        assert report.metrics["stress"]["available"] is False
        assert report.recommendations == []

    def test_to_dict_structure(self, populated_storage):
        date_from, date_to = self._week_range()
        report = compute_insights(populated_storage, date_from, date_to)
        d = report.to_dict()
        assert "period" in d
        assert "summary" in d
        assert "metrics" in d
        assert "recommendations" in d
        assert d["period"]["days"] == 7

    def test_headline_set(self, populated_storage):
        date_from, date_to = self._week_range()
        report = compute_insights(populated_storage, date_from, date_to)
        assert len(report.headline) > 0
