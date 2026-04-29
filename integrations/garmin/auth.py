"""Garmin Connect authentication with token persistence."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import garminconnect
from garminconnect import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from .client import GarminConnectAdapter
from .config import GarminConfig

logger = logging.getLogger(__name__)


class AuthError(RuntimeError):
    pass


class RateLimitError(RuntimeError):
    pass


def _prompt_mfa() -> str:
    """Prompt for MFA code. Returns empty string in non-interactive environments."""
    if not sys.stdin.isatty():
        raise AuthError(
            "Garmin requires MFA but stdin is not a TTY. "
            "Run the command interactively to complete MFA, or ensure your "
            "tokens are already saved in GARMIN_TOKEN_DIR."
        )
    return input("Enter Garmin MFA/2FA code: ").strip()


def get_authenticated_client(config: GarminConfig) -> GarminConnectAdapter:
    """Return an authenticated GarminConnectAdapter.

    Tries token-based login first; falls back to credential login.
    Saves new tokens after a successful credential login.
    """
    token_dir: Path = config.token_dir
    token_dir_str = str(token_dir)

    garmin = garminconnect.Garmin(
        email=config.email,
        password=config.password,
        prompt_mfa=_prompt_mfa,
    )

    if token_dir.exists() and any(token_dir.iterdir()):
        logger.debug("Attempting token-based login from %s", token_dir_str)
        try:
            result = garmin.login(tokenstore=token_dir_str)
            if result and result[0]:
                logger.info("MFA required during token refresh; prompting.")
                garmin.resume_login(result[1], _prompt_mfa())
            _save_tokens(garmin, token_dir)
            logger.info("Logged in via stored tokens.")
            return GarminConnectAdapter(garmin)
        except GarminConnectAuthenticationError as exc:
            logger.warning("Token login failed (%s); retrying with credentials.", exc)
        except Exception as exc:
            logger.warning("Token login error (%s); retrying with credentials.", exc)

    logger.info("Logging in with credentials.")
    try:
        result = garmin.login()
        if result and result[0]:
            logger.info("MFA required; prompting.")
            garmin.resume_login(result[1], _prompt_mfa())
        token_dir.mkdir(parents=True, exist_ok=True)
        _save_tokens(garmin, token_dir)
        logger.info("Login successful; tokens saved to %s", token_dir_str)
        return GarminConnectAdapter(garmin)

    except GarminConnectAuthenticationError as exc:
        raise AuthError(
            f"Garmin Connect authentication failed: {exc}\n"
            "Check GARMIN_EMAIL and GARMIN_PASSWORD in your .env file."
        ) from exc
    except GarminConnectTooManyRequestsError as exc:
        raise RateLimitError(
            "Garmin Connect rate limit reached. "
            "Wait a few minutes before retrying."
        ) from exc
    except GarminConnectConnectionError as exc:
        raise AuthError(
            f"Could not connect to Garmin Connect: {exc}\n"
            "Check your internet connection and try again."
        ) from exc


def _save_tokens(garmin: garminconnect.Garmin, token_dir: Path) -> None:
    try:
        garmin.garth.dump(str(token_dir))
    except Exception as exc:
        logger.debug("Token save skipped: %s", exc)
