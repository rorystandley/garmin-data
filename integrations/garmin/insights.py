"""Deterministic insight engine.

Computes structured summaries and recommendations from locally stored data.
No external calls — pure analysis of what's in the database.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from statistics import mean, stdev
from typing import Any

from .models import (
    Activity,
    BodyBatteryData,
    DailySummary,
    HRVData,
    InsightReport,
    Recommendation,
    SleepData,
    StressData,
    WeightEntry,
)
from .storage import GarminStorage

logger = logging.getLogger(__name__)

_HIGH_STRESS_THRESHOLD = 50
_LOW_SLEEP_HOURS_WARN = 7.0
_LOW_SLEEP_HOURS_CRITICAL = 6.0
_LOW_BODY_BATTERY_END = 20
_HIGH_HR_WORKOUT = 160
_CONSECUTIVE_HARD_DAYS = 3
_LOAD_SPIKE_FACTOR = 1.5


def _avg(values: list[float | int | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(mean(vals), 1) if vals else None


def _trend(values: list[float | int | None]) -> str:
    """Return 'improving', 'worsening', 'stable', or 'insufficient_data'."""
    vals = [v for v in values if v is not None]
    if len(vals) < 4:
        return "insufficient_data"
    half = len(vals) // 2
    first_half = mean(vals[:half])
    second_half = mean(vals[half:])
    diff = second_half - first_half
    threshold = 0.05 * (abs(first_half) or 1)
    if diff > threshold:
        return "improving"
    if diff < -threshold:
        return "worsening"
    return "stable"


def _sleep_trend(values: list[float | int | None]) -> str:
    """Higher sleep = better, so invert the generic trend for display."""
    t = _trend(values)
    if t == "improving":
        return "improving"
    if t == "worsening":
        return "worsening"
    return t


def _windows(storage: GarminStorage, date_to: date) -> dict[str, tuple[str, str]]:
    """Return date-from strings for standard analysis windows."""
    return {
        "7d": ((date_to - timedelta(days=6)).isoformat(), date_to.isoformat()),
        "14d": ((date_to - timedelta(days=13)).isoformat(), date_to.isoformat()),
        "30d": ((date_to - timedelta(days=29)).isoformat(), date_to.isoformat()),
    }


def compute_insights(
    storage: GarminStorage,
    date_from: date,
    date_to: date,
) -> InsightReport:
    from_str = date_from.isoformat()
    to_str = date_to.isoformat()
    days = (date_to - date_from).days + 1

    report = InsightReport(
        period_from=from_str,
        period_to=to_str,
        period_days=days,
    )

    summaries = storage.get_daily_summaries(from_str, to_str)
    sleep_data = storage.get_sleep(from_str, to_str)
    stress_data = storage.get_stress(from_str, to_str)
    bb_data = storage.get_body_battery(from_str, to_str)
    hrv_data = storage.get_hrv(from_str, to_str)
    activities = storage.get_activities(from_str, to_str)
    weigh_ins = storage.get_weigh_ins(from_str, to_str)
    latest_weigh_in = storage.get_latest_weigh_in()

    sleep_metrics = _analyse_sleep(sleep_data, days)
    stress_metrics = _analyse_stress(stress_data, days)
    bb_metrics = _analyse_body_battery(bb_data)
    hr_metrics = _analyse_heart_rate(summaries)
    activity_metrics = _analyse_activity(activities, days)
    training_metrics = _analyse_training(activities, summaries)
    hrv_metrics = _analyse_hrv(hrv_data)
    weight_metrics = _analyse_weight(weigh_ins, latest_weigh_in)

    report.metrics = {
        "sleep": sleep_metrics,
        "stress": stress_metrics,
        "body_battery": bb_metrics,
        "heart_rate": hr_metrics,
        "activity": activity_metrics,
        "training": training_metrics,
        "hrv": hrv_metrics,
        "weight": weight_metrics,
    }

    _detect_correlations(
        report, sleep_data, stress_data, bb_data, activities, summaries
    )
    _generate_recommendations(report, sleep_metrics, stress_metrics, bb_metrics, hr_metrics, activity_metrics, training_metrics, hrv_metrics)
    _build_summary(report)

    return report


def _analyse_sleep(sleep_data: list[SleepData], total_days: int) -> dict[str, Any]:
    if not sleep_data:
        return {"available": False, "note": "No sleep data in this period."}

    hours = [
        s.sleep_time_seconds / 3600
        for s in sleep_data
        if s.sleep_time_seconds is not None
    ]
    scores = [s.sleep_score for s in sleep_data if s.sleep_score is not None]

    nights_under_7 = sum(1 for h in hours if h < _LOW_SLEEP_HOURS_WARN)
    nights_under_6 = sum(1 for h in hours if h < _LOW_SLEEP_HOURS_CRITICAL)

    return {
        "available": True,
        "nights_recorded": len(sleep_data),
        "avg_duration_hours": _avg(hours),
        "min_duration_hours": round(min(hours), 1) if hours else None,
        "max_duration_hours": round(max(hours), 1) if hours else None,
        "nights_under_7h": nights_under_7,
        "nights_under_6h": nights_under_6,
        "avg_sleep_score": _avg(scores),
        "trend": _sleep_trend(hours),
    }


def _analyse_stress(stress_data: list[StressData], total_days: int) -> dict[str, Any]:
    if not stress_data:
        return {"available": False, "note": "No stress data in this period."}

    avg_levels = [s.avg_stress_level for s in stress_data if s.avg_stress_level is not None]
    max_levels = [s.max_stress_level for s in stress_data if s.max_stress_level is not None]

    high_stress_days = sum(
        1 for v in avg_levels if v > _HIGH_STRESS_THRESHOLD
    )

    return {
        "available": True,
        "days_recorded": len(stress_data),
        "avg_stress": _avg(avg_levels),
        "avg_max_stress": _avg(max_levels),
        "high_stress_days": high_stress_days,
        "high_stress_pct": round(high_stress_days / len(stress_data) * 100, 1) if stress_data else None,
        "trend": _trend(avg_levels),
    }


def _analyse_body_battery(bb_data: list[BodyBatteryData]) -> dict[str, Any]:
    if not bb_data:
        return {"available": False, "note": "No body battery data in this period."}

    end_values = [b.end_value for b in bb_data if b.end_value is not None]
    start_values = [b.start_value for b in bb_data if b.start_value is not None]
    charged = [b.charged for b in bb_data if b.charged is not None]
    drained = [b.drained for b in bb_data if b.drained is not None]

    low_days = sum(1 for v in end_values if v < _LOW_BODY_BATTERY_END)

    return {
        "available": True,
        "days_recorded": len(bb_data),
        "avg_start": _avg(start_values),
        "avg_end": _avg(end_values),
        "avg_charged": _avg(charged),
        "avg_drained": _avg(drained),
        "days_ending_below_20": low_days,
        "trend_end_value": _trend(end_values),
    }


def _analyse_heart_rate(summaries: list[DailySummary]) -> dict[str, Any]:
    rhr = [s.resting_heart_rate for s in summaries if s.resting_heart_rate is not None]
    avg_hr = [s.average_heart_rate for s in summaries if s.average_heart_rate is not None]

    if not rhr and not avg_hr:
        return {"available": False, "note": "No heart rate data in this period."}

    return {
        "available": True,
        "avg_resting_hr": _avg(rhr),
        "min_resting_hr": min(rhr) if rhr else None,
        "max_resting_hr": max(rhr) if rhr else None,
        "avg_daily_hr": _avg(avg_hr),
        "rhr_trend": _trend(rhr),
    }


def _analyse_activity(activities: list[Activity], total_days: int) -> dict[str, Any]:
    if not activities:
        return {
            "available": False,
            "note": "No activities in this period.",
            "workout_count": 0,
            "rest_days": total_days,
        }

    by_type: dict[str, int] = {}
    for a in activities:
        t = a.activity_type or "unknown"
        by_type[t] = by_type.get(t, 0) + 1

    durations = [a.duration_seconds for a in activities if a.duration_seconds is not None]
    distances = [a.distance_meters for a in activities if a.distance_meters is not None]
    calories = [a.calories for a in activities if a.calories is not None]

    active_dates = {a.calendar_date for a in activities if a.calendar_date}
    rest_days = total_days - len(active_dates)

    total_duration_hours = round(sum(durations) / 3600, 1) if durations else 0
    total_distance_km = round(sum(distances) / 1000, 1) if distances else 0

    return {
        "available": True,
        "workout_count": len(activities),
        "workout_types": by_type,
        "active_days": len(active_dates),
        "rest_days": max(0, rest_days),
        "total_duration_hours": total_duration_hours,
        "total_distance_km": total_distance_km,
        "total_calories": round(sum(calories), 0) if calories else None,
        "avg_duration_minutes": round(mean(durations) / 60, 1) if durations else None,
    }


def _analyse_training(
    activities: list[Activity], summaries: list[DailySummary]
) -> dict[str, Any]:
    tss_values = [
        a.training_stress_score
        for a in activities
        if a.training_stress_score is not None
    ]
    aero_effects = [
        a.aerobic_training_effect
        for a in activities
        if a.aerobic_training_effect is not None
    ]

    # Detect load spikes: day TSS vs 7-day rolling average
    load_spikes: list[str] = []
    if tss_values and len(tss_values) >= 3:
        activities_sorted = sorted(
            [a for a in activities if a.training_stress_score is not None],
            key=lambda a: a.start_time_gmt or "",
        )
        for i in range(1, len(activities_sorted)):
            window = activities_sorted[max(0, i - 7) : i]
            window_avg = mean(a.training_stress_score for a in window)  # type: ignore[arg-type]
            current = activities_sorted[i].training_stress_score
            if current and window_avg and current > window_avg * _LOAD_SPIKE_FACTOR:
                load_spikes.append(
                    activities_sorted[i].calendar_date or activities_sorted[i].start_time_gmt or ""
                )

    # Consecutive high-HR days
    high_hr_dates = sorted(
        {a.calendar_date for a in activities if a.average_hr and a.average_hr > _HIGH_HR_WORKOUT and a.calendar_date}
    )
    consecutive_hard_days = _count_max_consecutive(high_hr_dates)

    # Intensity minutes from summaries
    moderate = sum(s.moderate_intensity_minutes or 0 for s in summaries)
    vigorous = sum(s.vigorous_intensity_minutes or 0 for s in summaries)

    return {
        "avg_tss": _avg(tss_values),
        "avg_aerobic_training_effect": _avg(aero_effects),
        "load_spike_dates": load_spikes,
        "max_consecutive_hard_days": consecutive_hard_days,
        "total_moderate_intensity_minutes": moderate,
        "total_vigorous_intensity_minutes": vigorous,
        "total_intensity_minutes": moderate + vigorous,
    }


def _analyse_hrv(hrv_data: list[HRVData]) -> dict[str, Any]:
    if not hrv_data:
        return {"available": False, "note": "No HRV data in this period."}

    weekly_avgs = [h.weekly_avg for h in hrv_data if h.weekly_avg is not None]
    last_nights = [h.last_night for h in hrv_data if h.last_night is not None]
    statuses = [h.status for h in hrv_data if h.status]

    return {
        "available": True,
        "days_recorded": len(hrv_data),
        "avg_weekly_hrv": _avg(weekly_avgs),
        "avg_last_night_hrv": _avg(last_nights),
        "trend": _trend(last_nights),
        "status_distribution": _count_values(statuses),
    }


def _analyse_weight(
    weigh_ins: list[WeightEntry],
    latest: WeightEntry | None,
) -> dict[str, Any]:
    if not weigh_ins and latest is None:
        return {"available": False, "note": "No weigh-ins recorded yet. Log your weight in the Garmin Connect app weekly."}

    entries_with_kg = [w for w in weigh_ins if w.weight_kg is not None]

    first = entries_with_kg[0] if entries_with_kg else None
    last = entries_with_kg[-1] if entries_with_kg else None

    change_kg: float | None = None
    change_lbs: float | None = None
    if first and last and first.calendar_date != last.calendar_date:
        change_kg = round(last.weight_kg - first.weight_kg, 2)  # type: ignore[operator]
        change_lbs = round(change_kg * 2.20462, 1)

    weights_kg = [w.weight_kg for w in entries_with_kg]

    return {
        "available": True,
        "entries_in_period": len(entries_with_kg),
        "latest_weight_kg": latest.weight_kg if latest else None,
        "latest_weight_lbs": latest.weight_lbs if latest else None,
        "latest_bmi": latest.bmi if latest else None,
        "latest_date": latest.calendar_date if latest else None,
        "period_start_weight_kg": first.weight_kg if first else None,
        "period_start_weight_lbs": first.weight_lbs if first else None,
        "period_end_weight_kg": last.weight_kg if last else None,
        "period_end_weight_lbs": last.weight_lbs if last else None,
        "change_kg": change_kg,
        "change_lbs": change_lbs,
        "trend": _trend(weights_kg),
    }


def _count_values(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    return counts


def _count_max_consecutive(sorted_dates: list[str]) -> int:
    if not sorted_dates:
        return 0
    max_run = 1
    run = 1
    for i in range(1, len(sorted_dates)):
        try:
            prev = date.fromisoformat(sorted_dates[i - 1])
            curr = date.fromisoformat(sorted_dates[i])
            if (curr - prev).days == 1:
                run += 1
                max_run = max(max_run, run)
            else:
                run = 1
        except ValueError:
            run = 1
    return max_run


def _detect_correlations(
    report: InsightReport,
    sleep_data: list[SleepData],
    stress_data: list[StressData],
    bb_data: list[BodyBatteryData],
    activities: list[Activity],
    summaries: list[DailySummary],
) -> None:
    # High stress + poor sleep overlap
    sleep_by_date = {s.calendar_date: s for s in sleep_data}
    stress_by_date = {s.calendar_date: s for s in stress_data}
    bb_by_date = {b.calendar_date: b for b in bb_data}
    activity_dates = {a.calendar_date for a in activities if a.calendar_date}

    high_stress_poor_sleep = 0
    hard_workout_bad_recovery = 0

    all_dates = sorted(
        {s.calendar_date for s in summaries if s.calendar_date}
    )

    for d in all_dates:
        stress = stress_by_date.get(d)
        sleep = sleep_by_date.get(d)
        bb = bb_by_date.get(d)

        if (
            stress and stress.avg_stress_level and stress.avg_stress_level > _HIGH_STRESS_THRESHOLD
            and sleep and sleep.sleep_time_seconds and sleep.sleep_time_seconds < _LOW_SLEEP_HOURS_WARN * 3600
        ):
            high_stress_poor_sleep += 1

    # Hard workout followed by poor next-day sleep
    hard_workout_days = sorted(
        {
            a.calendar_date
            for a in activities
            if a.average_hr and a.average_hr > _HIGH_HR_WORKOUT and a.calendar_date
        }
    )
    for workout_date in hard_workout_days:
        try:
            next_day = (date.fromisoformat(workout_date) + timedelta(days=1)).isoformat()
        except ValueError:
            continue
        next_sleep = sleep_by_date.get(next_day)
        if (
            next_sleep
            and next_sleep.sleep_time_seconds
            and next_sleep.sleep_time_seconds < _LOW_SLEEP_HOURS_WARN * 3600
        ):
            hard_workout_bad_recovery += 1

    if high_stress_poor_sleep > 0:
        report.risk_signals.append(
            f"High stress and poor sleep occurred together on {high_stress_poor_sleep} day(s)."
        )
    if hard_workout_bad_recovery > 0:
        report.risk_signals.append(
            f"Hard workout followed by sub-7h sleep on {hard_workout_bad_recovery} occasion(s) — "
            "potential under-recovery."
        )


def _generate_recommendations(
    report: InsightReport,
    sleep: dict[str, Any],
    stress: dict[str, Any],
    bb: dict[str, Any],
    hr: dict[str, Any],
    activity: dict[str, Any],
    training: dict[str, Any],
    hrv: dict[str, Any],
) -> None:
    recs = report.recommendations

    # Sleep recommendations
    if sleep.get("available"):
        avg_h = sleep.get("avg_duration_hours")
        nights_under_7 = sleep.get("nights_under_7h", 0)
        if avg_h and avg_h < _LOW_SLEEP_HOURS_WARN:
            recs.append(Recommendation(
                title="Prioritise sleep duration",
                reason=f"Average sleep is {avg_h}h — below the recommended 7–9h.",
                suggested_action="Target a consistent 10pm–6am window. Avoid screens 1h before bed.",
                confidence="high",
                supporting_data=[f"avg_sleep={avg_h}h", f"nights_under_7h={nights_under_7}"],
            ))
        if sleep.get("trend") == "worsening":
            recs.append(Recommendation(
                title="Sleep quality declining",
                reason="Sleep duration has trended downward over this period.",
                suggested_action="Review recent stressors, training load, or caffeine timing.",
                confidence="medium",
                supporting_data=["sleep_trend=worsening"],
            ))

    # Stress recommendations
    if stress.get("available"):
        avg_s = stress.get("avg_stress")
        high_pct = stress.get("high_stress_pct", 0)
        if avg_s and avg_s > _HIGH_STRESS_THRESHOLD:
            recs.append(Recommendation(
                title="Elevated chronic stress",
                reason=f"Average stress level is {avg_s} — above the high-stress threshold of {_HIGH_STRESS_THRESHOLD}.",
                suggested_action="Incorporate active recovery, meditation, or stress-management strategies.",
                confidence="medium",
                supporting_data=[f"avg_stress={avg_s}", f"high_stress_pct={high_pct}%"],
            ))

    # Body Battery recommendations
    if bb.get("available"):
        avg_end = bb.get("avg_end")
        low_days = bb.get("days_ending_below_20", 0)
        if avg_end and avg_end < 30:
            recs.append(Recommendation(
                title="Consistently low body battery",
                reason=f"Average end-of-day body battery is {avg_end} — indicating accumulated fatigue.",
                suggested_action="Schedule 1–2 lighter days or active recovery sessions this week.",
                confidence="medium",
                supporting_data=[f"avg_bb_end={avg_end}", f"days_ending_below_20={low_days}"],
            ))

    # Training load spike
    spikes = training.get("load_spike_dates", [])
    if spikes:
        recs.append(Recommendation(
            title="Training load spike detected",
            reason=f"Training stress exceeded 1.5× the 7-day rolling average on {len(spikes)} occasion(s).",
            suggested_action="Follow each hard session with at least one easy or rest day.",
            confidence="medium",
            supporting_data=[f"spike_dates={spikes}"],
        ))

    # Consecutive hard days
    consec = training.get("max_consecutive_hard_days", 0)
    if consec >= _CONSECUTIVE_HARD_DAYS:
        recs.append(Recommendation(
            title="Consecutive high-intensity days",
            reason=f"Up to {consec} consecutive days with high average heart rate detected.",
            suggested_action="Insert a recovery day between hard sessions to allow adaptation.",
            confidence="medium",
            supporting_data=[f"max_consecutive_hard_days={consec}"],
        ))

    # HRV declining
    if hrv.get("available") and hrv.get("trend") == "worsening":
        recs.append(Recommendation(
            title="HRV trending downward",
            reason="HRV has declined over this period, which can indicate accumulated fatigue or illness.",
            suggested_action="Prioritise sleep and reduce training intensity until HRV stabilises.",
            confidence="medium",
            supporting_data=["hrv_trend=worsening"],
        ))

    # Activity consistency
    wc = activity.get("workout_count", 0)
    days = report.period_days
    if days >= 14 and wc < days // 7 * 2:
        recs.append(Recommendation(
            title="Below target training consistency",
            reason=f"Only {wc} workouts recorded over {days} days.",
            suggested_action="Aim for at least 3–4 sessions per week. Even short walks count.",
            confidence="low",
            supporting_data=[f"workouts={wc}", f"period_days={days}"],
        ))


def _build_summary(report: InsightReport) -> None:
    """Derive headline, key findings, and positive signals from computed metrics."""
    m = report.metrics
    findings: list[str] = []
    positives: list[str] = []
    focus: list[str] = []

    # Sleep
    sleep = m.get("sleep", {})
    if sleep.get("available"):
        avg_h = sleep.get("avg_duration_hours")
        if avg_h:
            findings.append(f"Average sleep: {avg_h}h per night.")
            if avg_h >= 7.5:
                positives.append(f"Good sleep duration — averaging {avg_h}h.")
            elif avg_h < _LOW_SLEEP_HOURS_WARN:
                focus.append("Improve sleep duration.")

    # Stress
    stress = m.get("stress", {})
    if stress.get("available"):
        avg_s = stress.get("avg_stress")
        if avg_s:
            if avg_s > _HIGH_STRESS_THRESHOLD:
                focus.append("Manage stress levels.")
            else:
                positives.append(f"Stress is within a manageable range (avg {avg_s}).")

    # Body battery
    bb = m.get("body_battery", {})
    if bb.get("available"):
        avg_end = bb.get("avg_end")
        if avg_end:
            if avg_end >= 40:
                positives.append(f"Body battery ending well (avg {avg_end}).")
            else:
                focus.append("Allow more recovery to rebuild body battery.")

    # Activity
    activity = m.get("activity", {})
    wc = activity.get("workout_count", 0)
    if wc > 0:
        total_h = activity.get("total_duration_hours", 0)
        findings.append(f"{wc} workouts logged, totalling {total_h}h.")
        if wc >= 4:
            positives.append(f"Strong training consistency: {wc} sessions this period.")

    # HRV
    hrv = m.get("hrv", {})
    if hrv.get("available"):
        avg_hrv = hrv.get("avg_last_night_hrv")
        if avg_hrv:
            findings.append(f"Average overnight HRV: {avg_hrv}.")

    # Weight
    weight = m.get("weight", {})
    if weight.get("available"):
        lbs = weight.get("latest_weight_lbs")
        kg = weight.get("latest_weight_kg")
        date = weight.get("latest_date", "")
        if lbs and kg:
            findings.append(f"Latest weight: {lbs} lbs ({kg} kg) on {date}.")
        change = weight.get("change_lbs")
        if change is not None:
            direction = "down" if change < 0 else "up"
            findings.append(f"Weight {direction} {abs(change)} lbs over this period.")
            if change < 0:
                positives.append(f"Weight trending down ({change:+.1f} lbs this period).")
            elif change > 2:
                focus.append("Review nutrition — weight trending up.")

    # Risk signals from correlations (already added)
    risk_count = len(report.risk_signals)

    # Headline
    if not findings:
        report.headline = "Insufficient data for a full assessment of this period."
    elif risk_count > 0:
        report.headline = f"Mixed signals: {wc} workouts recorded with {risk_count} recovery concern(s) flagged."
    elif positives:
        report.headline = "Positive trends across training and recovery this period."
    else:
        report.headline = f"{wc} workouts recorded. Continue monitoring recovery metrics."

    report.key_findings = findings
    report.positive_signals = positives
    if not report.risk_signals:
        report.risk_signals = []
    report.recommended_focus = focus
