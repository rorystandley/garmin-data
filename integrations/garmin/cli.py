"""CLI entry points for the Garmin integration.

All commands delegate to the service layer — no business logic here.
"""

from __future__ import annotations

import json
import sys
from datetime import date

import click

from .config import ConfigError, configure_logging, load_config


def _handle_error(exc: Exception) -> None:
    click.echo(f"Error: {exc}", err=True)
    sys.exit(1)


def _load_cfg():
    try:
        return load_config()
    except ConfigError as exc:
        _handle_error(exc)


@click.command("garmin-sync")
@click.option("--days", default=None, type=int, help="Sync last N days (default: GARMIN_SYNC_DAYS_DEFAULT).")
@click.option("--from", "date_from", default=None, help="Start date YYYY-MM-DD.")
@click.option("--to", "date_to", default=None, help="End date YYYY-MM-DD (default: today).")
def sync(days: int | None, date_from: str | None, date_to: str | None) -> None:
    """Sync Garmin data to local storage."""
    cfg = _load_cfg()
    configure_logging(cfg.log_level)

    from .service import sync_garmin_data

    parsed_from = None
    parsed_to = None
    if date_from:
        try:
            parsed_from = date.fromisoformat(date_from)
        except ValueError:
            _handle_error(ValueError(f"Invalid --from date: {date_from!r}. Use YYYY-MM-DD."))
    if date_to:
        try:
            parsed_to = date.fromisoformat(date_to)
        except ValueError:
            _handle_error(ValueError(f"Invalid --to date: {date_to!r}. Use YYYY-MM-DD."))

    try:
        result = sync_garmin_data(
            days=days,
            date_from=parsed_from,
            date_to=parsed_to,
            config=cfg,
        )
    except Exception as exc:
        _handle_error(exc)
        return  # unreachable but helps type checkers

    click.echo(f"Sync complete: {result.records_synced} records, {len(result.errors)} errors.")
    click.echo(f"Period: {result.date_from} → {result.date_to}")
    if result.errors:
        click.echo("\nEndpoint errors (non-fatal):")
        for err in result.errors:
            click.echo(f"  • {err}", err=True)


@click.command("garmin-summary")
@click.option("--days", default=30, show_default=True, help="Number of days to summarise.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", show_default=True)
def summary(days: int, fmt: str) -> None:
    """Show a summary of Garmin health and activity data."""
    cfg = _load_cfg()
    configure_logging(cfg.log_level)

    from .service import get_garmin_summary

    try:
        result = get_garmin_summary(days=days, config=cfg)
    except Exception as exc:
        _handle_error(exc)
        return

    if fmt == "json":
        click.echo(json.dumps(result, indent=2))
    else:
        _print_summary_text(result)


@click.command("garmin-activities")
@click.option("--days", default=30, show_default=True, help="Number of days to include.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", show_default=True)
def activities(days: int, fmt: str) -> None:
    """List recent Garmin activities."""
    cfg = _load_cfg()
    configure_logging(cfg.log_level)

    from .service import get_recent_activities

    try:
        result = get_recent_activities(days=days, config=cfg)
    except Exception as exc:
        _handle_error(exc)
        return

    if fmt == "json":
        click.echo(json.dumps(result, indent=2))
    else:
        if not result:
            click.echo(f"No activities found in the last {days} days.")
            return
        click.echo(f"{'Date':<12} {'Type':<20} {'Name':<30} {'Dur(min)':>8} {'Dist(km)':>9} {'AvgHR':>6}")
        click.echo("-" * 90)
        for a in result:
            click.echo(
                f"{a['date'] or '':12} "
                f"{(a['type'] or ''):20} "
                f"{(a['name'] or '')[:29]:30} "
                f"{str(a['duration_minutes'] or ''):>8} "
                f"{str(a['distance_km'] or ''):>9} "
                f"{str(a['avg_hr'] or ''):>6}"
            )
        click.echo(f"\nTotal: {len(result)} activities")


@click.command("garmin-insights")
@click.option("--days", default=30, show_default=True, help="Number of days to analyse.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", show_default=True)
def insights(days: int, fmt: str) -> None:
    """Show deterministic health and training insights."""
    cfg = _load_cfg()
    configure_logging(cfg.log_level)

    from .service import get_garmin_summary

    try:
        result = get_garmin_summary(days=days, config=cfg)
    except Exception as exc:
        _handle_error(exc)
        return

    if fmt == "json":
        click.echo(json.dumps(result, indent=2))
    else:
        _print_insights_text(result)


@click.command("garmin-ai-context")
@click.option("--days", default=30, show_default=True, help="Number of days to include.")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", show_default=True)
def ai_context(days: int, fmt: str) -> None:
    """Generate an AI-ready context block from stored Garmin data."""
    cfg = _load_cfg()
    configure_logging(cfg.log_level)

    from .service import get_ai_context

    try:
        result = get_ai_context(days=days, format=fmt, config=cfg)
    except Exception as exc:
        _handle_error(exc)
        return

    if fmt == "json":
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(result)


# ── Text formatters ────────────────────────────────────────────────────────

def _print_summary_text(d: dict) -> None:
    period = d.get("period", {})
    summary = d.get("summary", {})
    metrics = d.get("metrics", {})

    click.echo(f"\n{'='*60}")
    click.echo(f"GARMIN SUMMARY: {period.get('from')} → {period.get('to')} ({period.get('days')} days)")
    click.echo(f"{'='*60}")
    click.echo(f"\n{summary.get('headline', '')}\n")

    if summary.get("key_findings"):
        click.echo("Key Findings:")
        for f in summary["key_findings"]:
            click.echo(f"  • {f}")

    if summary.get("positive_signals"):
        click.echo("\nPositive Signals:")
        for s in summary["positive_signals"]:
            click.echo(f"  ✓ {s}")

    if summary.get("risk_signals"):
        click.echo("\nRisk Signals:")
        for s in summary["risk_signals"]:
            click.echo(f"  ⚠ {s}")

    if summary.get("recommended_focus"):
        click.echo("\nRecommended Focus:")
        for f in summary["recommended_focus"]:
            click.echo(f"  → {f}")

    click.echo("")


def _print_insights_text(d: dict) -> None:
    _print_summary_text(d)
    recs = d.get("recommendations", [])
    if recs:
        click.echo("Recommendations:")
        for r in recs:
            click.echo(f"\n  [{r['confidence'].upper()}] {r['title']}")
            click.echo(f"    Why: {r['reason']}")
            click.echo(f"    Action: {r['suggested_action']}")
    click.echo("")
