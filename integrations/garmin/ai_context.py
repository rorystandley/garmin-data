"""Convert an InsightReport into a compact context block for AI agents.

The output summarises trends and anomalies — never raw data arrays.
Both plain-text and JSON formats are available.
"""

from __future__ import annotations

import json
from typing import Any

from .models import InsightReport

_DISCLAIMER = (
    "IMPORTANT DISCLAIMER: This analysis is based on consumer fitness tracking "
    "data and is intended for training/lifestyle awareness only. It is NOT medical "
    "advice. Do not use this data to diagnose, treat, or manage any health condition. "
    "If you have any concerns about your health, consult a qualified healthcare "
    "professional."
)


def generate_ai_context(
    report: InsightReport, format: str = "text"
) -> str | dict[str, Any]:
    if format == "json":
        return _build_json(report)
    return _build_text(report)


def _v(value: Any, suffix: str = "", default: str = "n/a") -> str:
    """Format a possibly-None value for display, appending suffix only when present."""
    return f"{value}{suffix}" if value is not None else default


def _build_text(report: InsightReport) -> str:
    lines: list[str] = []
    m = report.metrics
    p = report.period_days

    lines.append("=== GARMIN HEALTH & ACTIVITY CONTEXT ===")
    lines.append(f"Period: {report.period_from} to {report.period_to} ({p} days)")
    lines.append("")
    lines.append(f"HEADLINE: {report.headline}")
    lines.append("")

    # Key findings
    if report.key_findings:
        lines.append("KEY FINDINGS:")
        for f in report.key_findings:
            lines.append(f"  • {f}")
        lines.append("")

    # Positive signals
    if report.positive_signals:
        lines.append("POSITIVE SIGNALS:")
        for s in report.positive_signals:
            lines.append(f"  ✓ {s}")
        lines.append("")

    # Risk signals
    if report.risk_signals:
        lines.append("RISK / CONCERN SIGNALS:")
        for s in report.risk_signals:
            lines.append(f"  ⚠ {s}")
        lines.append("")

    # Sleep
    sleep = m.get("sleep", {})
    lines.append("SLEEP:")
    if not sleep.get("available"):
        lines.append(f"  {sleep.get('note', 'No data — watch not worn at night for this period.')}")
    else:
        avg_h = sleep.get("avg_duration_hours")
        if avg_h is not None:
            lines.append(f"  Avg duration: {avg_h}h/night over {sleep.get('nights_recorded')} nights")
            lines.append(f"  Range: {_v(sleep.get('min_duration_hours'), 'h')} – {_v(sleep.get('max_duration_hours'), 'h')}")
            lines.append(f"  Nights < 7h: {sleep.get('nights_under_7h')}  |  Nights < 6h: {sleep.get('nights_under_6h')}")
        else:
            lines.append(f"  {sleep.get('nights_recorded')} nights recorded but no duration data — watch may not have been worn to bed.")
        if sleep.get("avg_sleep_score"):
            lines.append(f"  Avg sleep score: {sleep.get('avg_sleep_score')}")
        lines.append(f"  Trend: {sleep.get('trend')}")
    lines.append("")

    # Stress
    stress = m.get("stress", {})
    lines.append("STRESS:")
    if not stress.get("available"):
        lines.append(f"  {stress.get('note', 'No data available.')}")
    else:
        lines.append(f"  Avg stress: {_v(stress.get('avg_stress'))}  |  High-stress days: {stress.get('high_stress_days')} ({_v(stress.get('high_stress_pct'), '%')})")
        lines.append(f"  Trend: {stress.get('trend')}")
    lines.append("")

    # Body Battery
    bb = m.get("body_battery", {})
    lines.append("BODY BATTERY:")
    if not bb.get("available"):
        lines.append(f"  {bb.get('note', 'No data — watch not worn consistently this period.')}")
    else:
        lines.append(f"  Avg start: {_v(bb.get('avg_start'))}  |  Avg end: {_v(bb.get('avg_end'))}")
        lines.append(f"  Avg charged: {_v(bb.get('avg_charged'))}  |  Avg drained: {_v(bb.get('avg_drained'))}")
        lines.append(f"  Days ending below 20: {bb.get('days_ending_below_20')}")
        lines.append(f"  End-value trend: {bb.get('trend_end_value')}")
    lines.append("")

    # Heart Rate
    hr = m.get("heart_rate", {})
    lines.append("HEART RATE:")
    if not hr.get("available"):
        lines.append(f"  {hr.get('note', 'No data available.')}")
    else:
        lines.append(f"  Avg resting HR: {_v(hr.get('avg_resting_hr'), ' bpm')}  (range: {_v(hr.get('min_resting_hr'))}–{_v(hr.get('max_resting_hr'), ' bpm')})")
        lines.append(f"  Resting HR trend: {hr.get('rhr_trend')}")
    lines.append("")

    # Activity
    act = m.get("activity", {})
    lines.append("ACTIVITY:")
    if not act.get("available") or act.get("workout_count", 0) == 0:
        lines.append("  No workouts recorded this period.")
    else:
        lines.append(f"  Workouts: {act.get('workout_count')}  |  Active days: {act.get('active_days')}  |  Rest days: {act.get('rest_days')}")
        types = act.get("workout_types", {})
        if types:
            type_str = ", ".join(f"{k}: {v}" for k, v in sorted(types.items(), key=lambda x: -x[1]))
            lines.append(f"  Types: {type_str}")
        lines.append(f"  Total duration: {_v(act.get('total_duration_hours'), 'h')}  |  Total distance: {_v(act.get('total_distance_km'), 'km')}")
    lines.append("")

    # Training
    training = m.get("training", {})
    lines.append("TRAINING LOAD:")
    lines.append(f"  Total intensity minutes: {_v(training.get('total_intensity_minutes'))} (moderate: {_v(training.get('total_moderate_intensity_minutes'))}, vigorous: {_v(training.get('total_vigorous_intensity_minutes'))})")
    spikes = training.get("load_spike_dates", [])
    if spikes:
        lines.append(f"  Load spikes detected on: {', '.join(spikes)}")
    consec = training.get("max_consecutive_hard_days", 0)
    if consec >= 2:
        lines.append(f"  Max consecutive hard days: {consec}")
    lines.append("")

    # HRV
    hrv = m.get("hrv", {})
    lines.append("HRV:")
    if not hrv.get("available"):
        lines.append(f"  {hrv.get('note', 'No data available.')}")
    else:
        lines.append(f"  Avg weekly HRV: {_v(hrv.get('avg_weekly_hrv'))}  |  Avg overnight HRV: {_v(hrv.get('avg_last_night_hrv'))}")
        lines.append(f"  Trend: {hrv.get('trend')}")
        dist = hrv.get("status_distribution", {})
        if dist:
            lines.append(f"  Status distribution: {dist}")
    lines.append("")

    # Weight
    wt = m.get("weight", {})
    lines.append("WEIGHT:")
    if not wt.get("available"):
        lines.append(f"  {wt.get('note', 'No weigh-ins recorded yet.')}")
    else:
        lines.append(f"  Latest: {_v(wt.get('latest_weight_lbs'), ' lbs')} / {_v(wt.get('latest_weight_kg'), ' kg')}  (logged {wt.get('latest_date', 'unknown')})")
        if wt.get("latest_bmi"):
            lines.append(f"  BMI: {wt.get('latest_bmi')}")
        if wt.get("entries_in_period", 0) > 1:
            change = wt.get("change_lbs")
            if change is not None:
                sign = "+" if change > 0 else ""
                lines.append(f"  Change this period: {sign}{change} lbs  |  Trend: {wt.get('trend')}")
        else:
            lines.append(f"  Only {wt.get('entries_in_period', 0)} weigh-in(s) this period — log weekly for trend tracking.")
    lines.append("")

    # Recommendations
    if report.recommendations:
        lines.append("RECOMMENDATIONS:")
        for r in report.recommendations:
            lines.append(f"  [{r.confidence.upper()}] {r.title}")
            lines.append(f"    Reason: {r.reason}")
            lines.append(f"    Action: {r.suggested_action}")
        lines.append("")

    lines.append("---")
    lines.append(_DISCLAIMER)

    return "\n".join(lines)


def _build_json(report: InsightReport) -> dict[str, Any]:
    d = report.to_dict()
    d["disclaimer"] = _DISCLAIMER
    return d
