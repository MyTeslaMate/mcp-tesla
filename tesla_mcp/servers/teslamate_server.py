"""TeslaMate data sub-server.

Mounted on the main FastMCP server with ``namespace="teslamate"`` so each tool
exposed here is reachable as ``teslamate_<name>`` from the parent. Keeps the
TeslaMate surface self-contained and free of inline boilerplate.
"""

from __future__ import annotations

from typing import Any, Optional

from fastmcp import Context, FastMCP

from ..auth_context import execute, make_tesla_tool, teslamate_auth_kwargs
from ..modules.teslamateapi import TeslaMateAPIModule


_TM_TAGS = {"teslamate"}


def build_teslamate_server(
    teslamate_module: TeslaMateAPIModule,
    *,
    app_csp: dict[str, Any],
) -> FastMCP:
    """Build the TeslaMate data sub-server bound to a TeslaMate API module."""
    mcp = FastMCP("MyTeslaMate – Data")
    tesla_tool = make_tesla_tool(mcp, app_csp)

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS)
    def get_cars(ctx: Context):
        """List all cars from TeslaMate (id, name, model, basic info)."""
        return execute(teslamate_module.get_cars, **teslamate_auth_kwargs(ctx))

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS)
    def get_car(car_id: int, ctx: Context):
        """Detailed info for a specific car.

        Args:
            car_id: The TeslaMate car ID
        """
        return execute(teslamate_module.get_car, car_id=car_id, **teslamate_auth_kwargs(ctx))

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS)
    def get_car_battery_health(car_id: int, ctx: Context):
        """Battery degradation data and health metrics for a specific car.

        Args:
            car_id: The TeslaMate car ID
        """
        return execute(
            teslamate_module.get_car_battery_health,
            car_id=car_id,
            **teslamate_auth_kwargs(ctx),
        )

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS)
    def get_car_charges(
        car_id: int,
        ctx: Context,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ):
        """Charging sessions for a specific car.

        Args:
            car_id: The TeslaMate car ID
            start_date: Optional start date in RFC3339 format (e.g., 2006-01-02T15:04:05Z)
            end_date: Optional end date in RFC3339 format
            limit: Optional max number of sessions to return
            offset: Optional offset for pagination
        """
        return execute(
            teslamate_module.get_car_charges,
            car_id=car_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
            **teslamate_auth_kwargs(ctx),
        )

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS)
    def get_car_charge(car_id: int, charge_id: int, ctx: Context):
        """Detailed info about a specific charging session.

        Args:
            car_id: The TeslaMate car ID
            charge_id: The charging session ID
        """
        return execute(
            teslamate_module.get_car_charge,
            car_id=car_id,
            charge_id=charge_id,
            **teslamate_auth_kwargs(ctx),
        )

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS)
    def get_car_charges_current(car_id: int, ctx: Context):
        """Currently active charging session, or empty if not charging.

        Args:
            car_id: The TeslaMate car ID
        """
        return execute(
            teslamate_module.get_car_charges_current,
            car_id=car_id,
            **teslamate_auth_kwargs(ctx),
        )

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS)
    def get_car_drives(
        car_id: int,
        ctx: Context,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_distance: Optional[float] = None,
        max_distance: Optional[float] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ):
        """Driving sessions for a specific car.

        Args:
            car_id: The TeslaMate car ID
            start_date: Optional start date in RFC3339 format
            end_date: Optional end date in RFC3339 format
            min_distance: Optional minimum trip distance (TeslaMate units)
            max_distance: Optional maximum trip distance (TeslaMate units)
            limit: Optional max number of drives to return
            offset: Optional offset for pagination
        """
        return execute(
            teslamate_module.get_car_drives,
            car_id=car_id,
            start_date=start_date,
            end_date=end_date,
            min_distance=min_distance,
            max_distance=max_distance,
            limit=limit,
            offset=offset,
            **teslamate_auth_kwargs(ctx),
        )

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS)
    def get_car_drive(car_id: int, drive_id: int, ctx: Context):
        """Detailed info about a specific driving session.

        Args:
            car_id: The TeslaMate car ID
            drive_id: The driving session ID
        """
        return execute(
            teslamate_module.get_car_drive,
            car_id=car_id,
            drive_id=drive_id,
            **teslamate_auth_kwargs(ctx),
        )

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS)
    def get_car_status(car_id: int, ctx: Context):
        """Current status of a specific car (location, charge state, etc.).

        Args:
            car_id: The TeslaMate car ID
        """
        return execute(
            teslamate_module.get_car_status,
            car_id=car_id,
            **teslamate_auth_kwargs(ctx),
        )

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TM_TAGS)
    def get_car_updates(car_id: int, ctx: Context):
        """Software updates information for a specific car (available + installed).

        Args:
            car_id: The TeslaMate car ID
        """
        return execute(
            teslamate_module.get_car_updates,
            car_id=car_id,
            **teslamate_auth_kwargs(ctx),
        )

    # === Prompts ===

    @mcp.prompt(tags=_TM_TAGS)
    def charge_review(car_id: int, period: str = "last 30 days") -> str:
        """Pre-framed prompt for reviewing a car's charging behavior over a period.

        Args:
            car_id: The TeslaMate car ID
            period: Free-text period (default: "last 30 days")
        """
        return (
            f"You are reviewing the charging behavior of TeslaMate car #{car_id} for {period}.\n"
            f"1. Call `teslamate_get_car_charges` for that car and period to gather sessions.\n"
            f"2. Summarize: total kWh charged, average session length, share of supercharger vs home, "
            f"estimated cost if available.\n"
            f"3. Flag anomalies: sessions interrupted, abnormally low power, sudden cost spikes.\n"
            f"4. Suggest 1–2 actionable optimizations (e.g., scheduled charging, better off-peak windows)."
        )

    @mcp.prompt(tags=_TM_TAGS)
    def battery_health_report(car_id: int) -> str:
        """Pre-framed prompt for assessing battery degradation.

        Args:
            car_id: The TeslaMate car ID
        """
        return (
            f"Assess the battery health of TeslaMate car #{car_id}.\n"
            f"1. Call `teslamate_get_car_battery_health` and `teslamate_get_car` to get current SoH and odometer.\n"
            f"2. Compare current usable capacity vs. nominal/new — express degradation in % and kWh lost.\n"
            f"3. Contextualize against typical Tesla degradation curves at this odometer.\n"
            f"4. Recommend: any habits to slow degradation, or whether SoH warrants a service visit."
        )

    return mcp
