"""Optional MCP server stub for the Garmin integration.

This file shows how the service layer functions could be exposed as MCP tools.
It is NOT required for the CLI workflow — the CLI works independently.

To activate:
  1. Install the MCP Python SDK:  uv add mcp
  2. Replace the stub MCP tool definitions below with real @server.tool() handlers
  3. Run: uv run python -m integrations.garmin.mcp_server
  4. Register the server in your Claude Code MCP settings

See https://modelcontextprotocol.io/docs/concepts/servers for MCP server docs.
"""

from __future__ import annotations

# ── MCP Tool Definitions (stub) ────────────────────────────────────────────
#
# Each block below documents one MCP tool that maps directly to a service
# function. When you wire this up with the real MCP SDK, replace each block
# with a @server.tool() decorated async function.
#
# ─────────────────────────────────────────────────────────────────────────────
#
# MCP Tool: sync_garmin_data
#   Description: Sync Garmin health and activity data for the last N days.
#   Input schema:
#     days (integer, optional, default=30): Number of days to sync.
#   Returns: { date_from, date_to, records_synced, errors, success }
#   Service call: service.sync_garmin_data(days=days)
#
# MCP Tool: get_garmin_summary
#   Description: Return a structured health and activity summary for the last N days.
#   Input schema:
#     days (integer, optional, default=30): Number of days to summarise.
#   Returns: InsightReport JSON (period, summary, metrics, recommendations)
#   Service call: service.get_garmin_summary(days=days)
#
# MCP Tool: get_recent_activities
#   Description: Return a list of recent Garmin activities.
#   Input schema:
#     days (integer, optional, default=30): Number of days to include.
#   Returns: list[{ activity_id, date, name, type, duration_minutes, distance_km, avg_hr, calories, tss }]
#   Service call: service.get_recent_activities(days=days)
#
# MCP Tool: get_sleep_trends
#   Description: Return sleep trend analysis for the last N days.
#   Input schema:
#     days (integer, optional, default=30): Number of days to analyse.
#   Returns: { available, nights_recorded, avg_duration_hours, trend, ... }
#   Service call: service.get_sleep_trends(days=days)
#
# MCP Tool: get_recovery_signals
#   Description: Return recovery-focused signals including HRV, body battery, and risk flags.
#   Input schema:
#     days (integer, optional, default=30): Number of days to analyse.
#   Returns: { body_battery, hrv, sleep, risk_signals, recommendations }
#   Service call: service.get_recovery_signals(days=days)
#
# MCP Tool: get_training_recommendations
#   Description: Return training and lifestyle recommendations based on stored data.
#   Input schema:
#     days (integer, optional, default=30): Number of days to analyse.
#   Returns: list[{ title, reason, suggested_action, confidence, supporting_data }]
#   Service call: service.get_training_recommendations(days=days)
#
# MCP Tool: get_ai_context
#   Description: Return a compact AI-ready context block summarising health trends.
#   Input schema:
#     days (integer, optional, default=30): Number of days to include.
#     format (string, optional, default="text"): "text" or "json".
#   Returns: string (text) or dict (json)
#   Service call: service.get_ai_context(days=days, format=format)
#
# ─────────────────────────────────────────────────────────────────────────────
#
# Example skeleton using the MCP Python SDK (once installed):
#
# from mcp.server import Server
# from mcp.server.stdio import stdio_server
# from integrations.garmin import service
#
# server = Server("garmin-data")
#
# @server.tool()
# async def get_garmin_summary(days: int = 30) -> dict:
#     """Return a structured health and activity summary."""
#     return service.get_garmin_summary(days=days)
#
# @server.tool()
# async def get_ai_context(days: int = 30, format: str = "text") -> str | dict:
#     """Return an AI-ready context block from stored Garmin data."""
#     return service.get_ai_context(days=days, format=format)
#
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(stdio_server(server))
#
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(
        "MCP server stub — wire up the mcp SDK to activate.\n"
        "See the comments in this file for the tool definitions.\n"
        "For CLI usage, run: uv run garmin-sync --help"
    )
