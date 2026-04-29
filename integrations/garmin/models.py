"""Typed dataclass models for Garmin data.

All optional fields may be None when the Garmin device or account does not
expose them. from_dict() methods are lenient — missing keys produce None, not
KeyError.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _get(d: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if d and key in d:
            return d[key]
    return default


@dataclass
class DailySummary:
    calendar_date: str
    steps: int | None = None
    step_goal: int | None = None
    total_kilocalories: float | None = None
    active_kilocalories: float | None = None
    resting_heart_rate: int | None = None
    average_heart_rate: int | None = None
    max_heart_rate: int | None = None
    min_heart_rate: int | None = None
    total_distance_meters: float | None = None
    highly_active_seconds: int | None = None
    active_seconds: int | None = None
    sedentary_seconds: int | None = None
    sleeping_seconds: int | None = None
    moderate_intensity_minutes: int | None = None
    vigorous_intensity_minutes: int | None = None
    body_battery_charged: int | None = None
    body_battery_drained: int | None = None
    body_battery_highest: int | None = None
    body_battery_lowest: int | None = None
    average_stress_level: int | None = None
    max_stress_level: int | None = None
    raw_json: str = "{}"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DailySummary":
        return cls(
            calendar_date=d.get("calendarDate", ""),
            steps=_get(d, "totalSteps"),
            step_goal=_get(d, "dailyStepGoal"),
            total_kilocalories=_get(d, "totalKilocalories"),
            active_kilocalories=_get(d, "activeKilocalories"),
            resting_heart_rate=_get(d, "restingHeartRate"),
            average_heart_rate=_get(d, "averageHeartRate"),
            max_heart_rate=_get(d, "maxHeartRate"),
            min_heart_rate=_get(d, "minHeartRate"),
            total_distance_meters=_get(d, "totalDistanceMeters"),
            highly_active_seconds=_get(d, "highlyActiveSeconds"),
            active_seconds=_get(d, "activeSeconds"),
            sedentary_seconds=_get(d, "sedentarySeconds"),
            sleeping_seconds=_get(d, "sleepingSeconds"),
            moderate_intensity_minutes=_get(d, "moderateIntensityMinutes"),
            vigorous_intensity_minutes=_get(d, "vigorousIntensityMinutes"),
            body_battery_charged=_get(d, "bodyBatteryChargedValue"),
            body_battery_drained=_get(d, "bodyBatteryDrainedValue"),
            body_battery_highest=_get(d, "bodyBatteryHighestValue"),
            body_battery_lowest=_get(d, "bodyBatteryLowestValue"),
            average_stress_level=_get(d, "averageStressLevel"),
            max_stress_level=_get(d, "maxStressLevel"),
            raw_json=json.dumps(d),
        )


@dataclass
class SleepData:
    calendar_date: str
    sleep_time_seconds: int | None = None
    deep_sleep_seconds: int | None = None
    light_sleep_seconds: int | None = None
    rem_sleep_seconds: int | None = None
    awake_seconds: int | None = None
    sleep_score: int | None = None
    sleep_score_quality: str | None = None
    average_respiration_value: float | None = None
    average_spo2_value: float | None = None
    resting_heart_rate: int | None = None
    average_stress: int | None = None
    raw_json: str = "{}"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SleepData":
        daily = _get(d, "dailySleepDTO") or {}
        scores = (daily.get("sleepScores") or {})
        overall = (scores.get("overall") or {})
        return cls(
            calendar_date=_get(daily, "calendarDate") or d.get("calendarDate", ""),
            sleep_time_seconds=_get(daily, "sleepTimeSeconds"),
            deep_sleep_seconds=_get(daily, "deepSleepSeconds"),
            light_sleep_seconds=_get(daily, "lightSleepSeconds"),
            rem_sleep_seconds=_get(daily, "remSleepSeconds"),
            awake_seconds=_get(daily, "awakeSleepSeconds"),
            sleep_score=overall.get("value"),
            sleep_score_quality=overall.get("qualifierKey"),
            average_respiration_value=_get(daily, "avgSleepBreathingRate"),
            average_spo2_value=_get(d, "averageSpO2Value"),
            resting_heart_rate=_get(daily, "restingHeartRate"),
            average_stress=_get(daily, "avgOvernightHrv"),
            raw_json=json.dumps(d),
        )


@dataclass
class StressData:
    calendar_date: str
    avg_stress_level: int | None = None
    max_stress_level: int | None = None
    stress_duration_seconds: int | None = None
    rest_duration_seconds: int | None = None
    activity_duration_seconds: int | None = None
    uncategorized_duration_seconds: int | None = None
    raw_json: str = "{}"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StressData":
        return cls(
            calendar_date=d.get("calendarDate", ""),
            avg_stress_level=_get(d, "avgStressLevel"),
            max_stress_level=_get(d, "maxStressLevel"),
            stress_duration_seconds=_get(d, "stressDuration"),
            rest_duration_seconds=_get(d, "restDuration"),
            activity_duration_seconds=_get(d, "activityDuration"),
            uncategorized_duration_seconds=_get(d, "uncategorizedDuration"),
            raw_json=json.dumps(d),
        )


@dataclass
class BodyBatteryData:
    calendar_date: str
    start_value: int | None = None
    end_value: int | None = None
    charged: int | None = None
    drained: int | None = None
    raw_json: str = "{}"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BodyBatteryData":
        charged = _get(d, "charged")
        drained = _get(d, "drained")
        start_value = _get(d, "startValue")
        end_value = _get(d, "endValue")

        # Many devices omit startValue/endValue; derive them from the values array
        if start_value is None or end_value is None:
            values_array = d.get("bodyBatteryValuesArray") or []
            levels = [
                v[1] for v in values_array
                if isinstance(v, list) and len(v) > 1 and v[1] is not None
            ]
            if levels:
                if start_value is None:
                    start_value = levels[0]
                if end_value is None:
                    end_value = levels[-1]

        return cls(
            calendar_date=d.get("date", ""),
            start_value=start_value,
            end_value=end_value,
            charged=charged,
            drained=drained,
            raw_json=json.dumps(d),
        )


@dataclass
class HRVData:
    calendar_date: str
    weekly_avg: int | None = None
    last_night: int | None = None
    last_5_min: int | None = None
    baseline_low: int | None = None
    baseline_high: int | None = None
    status: str | None = None
    raw_json: str = "{}"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HRVData":
        summary = _get(d, "hrvSummary") or {}
        baseline = _get(summary, "baseline") or {}
        return cls(
            calendar_date=_get(summary, "calendarDate") or d.get("calendarDate", ""),
            weekly_avg=_get(summary, "weeklyAvg"),
            last_night=_get(summary, "lastNight"),
            last_5_min=_get(summary, "lastNight5MinHigh"),
            baseline_low=_get(baseline, "lowUpper"),
            baseline_high=_get(baseline, "balancedLow"),
            status=_get(summary, "status"),
            raw_json=json.dumps(d),
        )


@dataclass
class Activity:
    activity_id: str
    activity_name: str | None = None
    activity_type: str | None = None
    start_time_gmt: str | None = None
    start_time_local: str | None = None
    calendar_date: str | None = None
    duration_seconds: float | None = None
    distance_meters: float | None = None
    average_hr: int | None = None
    max_hr: int | None = None
    calories: float | None = None
    average_speed: float | None = None
    max_speed: float | None = None
    aerobic_training_effect: float | None = None
    anaerobic_training_effect: float | None = None
    training_stress_score: float | None = None
    steps: int | None = None
    average_cadence: float | None = None
    elevation_gain: float | None = None
    elevation_loss: float | None = None
    average_power: float | None = None
    normalized_power: float | None = None
    raw_json: str = "{}"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Activity":
        start_gmt = _get(d, "startTimeGMT")
        calendar_date = start_gmt[:10] if start_gmt else None
        activity_type_raw = d.get("activityType")
        if isinstance(activity_type_raw, dict):
            activity_type = activity_type_raw.get("typeKey")
        else:
            activity_type = activity_type_raw
        return cls(
            activity_id=str(_get(d, "activityId", default="")),
            activity_name=_get(d, "activityName"),
            activity_type=activity_type,
            start_time_gmt=start_gmt,
            start_time_local=_get(d, "startTimeLocal"),
            calendar_date=calendar_date,
            duration_seconds=_get(d, "duration"),
            distance_meters=_get(d, "distance"),
            average_hr=_get(d, "averageHR"),
            max_hr=_get(d, "maxHR"),
            calories=_get(d, "calories"),
            average_speed=_get(d, "averageSpeed"),
            max_speed=_get(d, "maxSpeed"),
            aerobic_training_effect=_get(d, "aerobicTrainingEffect"),
            anaerobic_training_effect=_get(d, "anaerobicTrainingEffect"),
            training_stress_score=_get(d, "trainingStressScore"),
            steps=_get(d, "steps"),
            average_cadence=_get(d, "averageBikingCadenceInRevPerMinute")
                or _get(d, "averageRunningCadenceInStepsPerMinute"),
            elevation_gain=_get(d, "elevationGain"),
            elevation_loss=_get(d, "elevationLoss"),
            average_power=_get(d, "avgPower"),
            normalized_power=_get(d, "normPower"),
            raw_json=json.dumps(d),
        )


@dataclass
class WeightEntry:
    calendar_date: str
    weight_kg: float | None = None
    weight_lbs: float | None = None
    bmi: float | None = None
    body_fat_pct: float | None = None
    muscle_mass_kg: float | None = None
    bone_mass_kg: float | None = None
    body_water_pct: float | None = None
    source_type: str | None = None
    raw_json: str = "{}"

    @classmethod
    def from_dict(cls, d: dict[str, Any], calendar_date: str = "") -> "WeightEntry":
        # Garmin stores weight in grams
        weight_grams = _get(d, "weight")
        weight_kg = round(weight_grams / 1000, 2) if weight_grams else None
        weight_lbs = round(weight_kg * 2.20462, 1) if weight_kg else None

        muscle_grams = _get(d, "muscleMass")
        bone_grams = _get(d, "boneMass")

        return cls(
            calendar_date=calendar_date or (_get(d, "calendarDate") or ""),
            weight_kg=weight_kg,
            weight_lbs=weight_lbs,
            bmi=_get(d, "bmi"),
            body_fat_pct=_get(d, "bodyFat"),
            muscle_mass_kg=round(muscle_grams / 1000, 2) if muscle_grams else None,
            bone_mass_kg=round(bone_grams / 1000, 2) if bone_grams else None,
            body_water_pct=_get(d, "bodyWater"),
            source_type=_get(d, "sourceType"),
            raw_json=json.dumps(d),
        )


@dataclass
class ActivityDetail:
    activity_id: str
    raw_json: str = "{}"

    @classmethod
    def from_dict(cls, activity_id: str, d: dict[str, Any]) -> "ActivityDetail":
        return cls(activity_id=activity_id, raw_json=json.dumps(d))


@dataclass
class SyncResult:
    date_from: str
    date_to: str
    records_synced: int = 0
    errors: list[str] = field(default_factory=list)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)

    def to_dict(self) -> dict[str, Any]:
        return {
            "date_from": self.date_from,
            "date_to": self.date_to,
            "records_synced": self.records_synced,
            "errors": self.errors,
            "success": len(self.errors) == 0,
        }


@dataclass
class Recommendation:
    title: str
    reason: str
    suggested_action: str
    confidence: str  # "low" | "medium" | "high"
    supporting_data: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "reason": self.reason,
            "suggested_action": self.suggested_action,
            "confidence": self.confidence,
            "supporting_data": self.supporting_data,
        }


@dataclass
class InsightReport:
    period_from: str
    period_to: str
    period_days: int
    headline: str = ""
    key_findings: list[str] = field(default_factory=list)
    positive_signals: list[str] = field(default_factory=list)
    risk_signals: list[str] = field(default_factory=list)
    recommended_focus: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    recommendations: list[Recommendation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": {
                "from": self.period_from,
                "to": self.period_to,
                "days": self.period_days,
            },
            "summary": {
                "headline": self.headline,
                "key_findings": self.key_findings,
                "positive_signals": self.positive_signals,
                "risk_signals": self.risk_signals,
                "recommended_focus": self.recommended_focus,
            },
            "metrics": self.metrics,
            "recommendations": [r.to_dict() for r in self.recommendations],
        }
