"""Configuration loaded from environment variables and .env file."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class ConfigError(ValueError):
    pass


@dataclass
class GarminConfig:
    email: str
    password: str
    token_dir: Path
    db_path: Path
    sync_days_default: int
    log_level: str


def load_config() -> GarminConfig:
    """Load and validate configuration from environment variables."""
    email = os.environ.get("GARMIN_EMAIL", "").strip()
    password = os.environ.get("GARMIN_PASSWORD", "").strip()

    if not email:
        raise ConfigError(
            "GARMIN_EMAIL is not set. "
            "Copy .env.example to .env and add your Garmin Connect email address."
        )
    if not password:
        raise ConfigError(
            "GARMIN_PASSWORD is not set. "
            "Copy .env.example to .env and add your Garmin Connect password."
        )

    token_dir = Path(
        os.environ.get("GARMIN_TOKEN_DIR", "~/.garmin_tokens")
    ).expanduser()

    db_path = Path(
        os.environ.get("GARMIN_DB_PATH", "~/garmin_data.db")
    ).expanduser()

    try:
        sync_days_default = int(os.environ.get("GARMIN_SYNC_DAYS_DEFAULT", "30"))
    except ValueError:
        raise ConfigError("GARMIN_SYNC_DAYS_DEFAULT must be an integer, e.g. 30")

    log_level_str = os.environ.get("GARMIN_LOG_LEVEL", "INFO").upper()
    valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if log_level_str not in valid_levels:
        raise ConfigError(
            f"GARMIN_LOG_LEVEL must be one of {sorted(valid_levels)}, "
            f"got: {log_level_str!r}"
        )

    return GarminConfig(
        email=email,
        password=password,
        token_dir=token_dir,
        db_path=db_path,
        sync_days_default=sync_days_default,
        log_level=log_level_str,
    )


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
