"""GarminClientProtocol and GarminConnectAdapter.

The Protocol defines the interface the rest of the application depends on.
GarminConnectAdapter wraps the third-party garminconnect library.
Swap the adapter here to replace the underlying Garmin client without touching
any other module.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class GarminClientProtocol(Protocol):
    def get_user_summary(self, cdate: str) -> dict[str, Any]: ...
    def get_steps_data(self, cdate: str) -> list[dict[str, Any]]: ...
    def get_heart_rates(self, cdate: str) -> dict[str, Any]: ...
    def get_rhr_day(self, cdate: str) -> dict[str, Any]: ...
    def get_sleep_data(self, cdate: str) -> dict[str, Any]: ...
    def get_stress_data(self, cdate: str) -> dict[str, Any]: ...
    def get_body_battery(self, startdate: str, enddate: str) -> list[dict[str, Any]]: ...
    def get_hrv_data(self, cdate: str) -> dict[str, Any] | None: ...
    def get_training_readiness(self, cdate: str) -> dict[str, Any]: ...
    def get_training_status(self, cdate: str) -> dict[str, Any]: ...
    def get_activities_by_date(self, startdate: str, enddate: str) -> list[dict[str, Any]]: ...
    def get_activity_details(self, activity_id: str) -> dict[str, Any]: ...
    def get_body_composition(self, startdate: str, enddate: str) -> dict[str, Any]: ...
    def get_daily_weigh_ins(self, cdate: str) -> dict[str, Any]: ...
    def get_user_profile(self) -> dict[str, Any]: ...


class GarminConnectAdapter:
    """Thin adapter wrapping garminconnect.Garmin.

    All application code should depend on GarminClientProtocol, not this class.
    """

    def __init__(self, garmin_client: Any) -> None:
        self._client = garmin_client

    def get_user_summary(self, cdate: str) -> dict[str, Any]:
        return self._client.get_user_summary(cdate)

    def get_steps_data(self, cdate: str) -> list[dict[str, Any]]:
        return self._client.get_steps_data(cdate) or []

    def get_heart_rates(self, cdate: str) -> dict[str, Any]:
        return self._client.get_heart_rates(cdate) or {}

    def get_rhr_day(self, cdate: str) -> dict[str, Any]:
        return self._client.get_rhr_day(cdate) or {}

    def get_sleep_data(self, cdate: str) -> dict[str, Any]:
        return self._client.get_sleep_data(cdate) or {}

    def get_stress_data(self, cdate: str) -> dict[str, Any]:
        return self._client.get_stress_data(cdate) or {}

    def get_body_battery(self, startdate: str, enddate: str) -> list[dict[str, Any]]:
        return self._client.get_body_battery(startdate, enddate) or []

    def get_hrv_data(self, cdate: str) -> dict[str, Any] | None:
        return self._client.get_hrv_data(cdate)

    def get_training_readiness(self, cdate: str) -> dict[str, Any]:
        return self._client.get_training_readiness(cdate) or {}

    def get_training_status(self, cdate: str) -> dict[str, Any]:
        return self._client.get_training_status(cdate) or {}

    def get_activities_by_date(self, startdate: str, enddate: str) -> list[dict[str, Any]]:
        return self._client.get_activities_by_date(startdate, enddate) or []

    def get_activity_details(self, activity_id: str) -> dict[str, Any]:
        return self._client.get_activity_details(activity_id) or {}

    def get_body_composition(self, startdate: str, enddate: str) -> dict[str, Any]:
        return self._client.get_body_composition(startdate, enddate) or {}

    def get_daily_weigh_ins(self, cdate: str) -> dict[str, Any]:
        return self._client.get_daily_weigh_ins(cdate) or {}

    def get_user_profile(self) -> dict[str, Any]:
        return self._client.get_user_profile() or {}
