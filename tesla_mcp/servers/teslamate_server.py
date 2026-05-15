"""TeslaMate data sub-server.

Mounted on the main FastMCP server with ``namespace="teslamate"`` so each tool
exposed here is reachable as ``teslamate_<name>`` from the parent. Keeps the
TeslaMate surface self-contained and free of inline boilerplate.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Optional

from fastmcp import Context, FastMCP

from ..auth_context import execute, make_tesla_tool, teslamate_auth_kwargs
from ..modules.teslamateapi import TeslaMateAPIModule


_TM_TAGS = {"teslamate"}

# Safety cap when `fetch_all=True`: prevent runaway loops if the TeslaMate
# API misbehaves. 20 pages × `show` per page (default 100) → 2 000 entries.
_FETCH_ALL_MAX_PAGES = int(os.environ.get("TESLAMATE_MAX_PAGES", "20"))


def _fetch_all_pages(
    fn: Callable[..., dict[str, Any]],
    *,
    list_key: str,
    id_key: str,
    show: int,
) -> dict[str, Any]:
    """Page through `fn(page=N, show=S)` until a page returns fewer than
    `show` entries. Dedupes on `id_key` (TeslaMate sometimes overlaps across
    pages when records are inserted mid-pagination). Caps at
    `_FETCH_ALL_MAX_PAGES`; sets `data.truncated=True` if the cap is hit
    while the last page was still full.

    `fn` must accept `page=` and `show=` kwargs and return the same envelope
    as `teslamate_module.get_car_drives` / `_charges` —
    ``{"data": {"car": …, "<list_key>": [...], "units": …}}``.
    """
    seen: set[Any] = set()
    aggregated: list[Any] = []
    car: dict[str, Any] = {}
    units: dict[str, Any] = {}
    last_page = 0
    last_items_len = 0
    for p in range(1, _FETCH_ALL_MAX_PAGES + 1):
        last_page = p
        chunk = fn(page=p, show=show)
        data = chunk.get("data") if isinstance(chunk, dict) else None
        if not isinstance(data, dict):
            break
        if not car:
            car = data.get("car", {}) or {}
        if not units:
            units = data.get("units", {}) or {}
        items = data.get(list_key, []) or []
        last_items_len = len(items)
        for item in items:
            uid = item.get(id_key) if isinstance(item, dict) else None
            if uid is None or uid in seen:
                continue
            seen.add(uid)
            aggregated.append(item)
        if last_items_len < show:
            break
    truncated = last_page == _FETCH_ALL_MAX_PAGES and last_items_len >= show
    return {
        "data": {
            "car": car,
            list_key: aggregated,
            "units": units,
            "pages_fetched": last_page,
            "truncated": truncated,
        }
    }


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
        page: int = 1,
        show: int = 100,
        fetch_all: bool = False,
    ):
        """Charging sessions for a specific car. Filter by date range.

        TeslaMate paginates at 100 entries per call by default. Use `page`
        / `show` to walk through manually, or `fetch_all=True` to let the
        server auto-paginate (capped at ~20 pages of safety). Set
        `fetch_all=True` for year-long counts or averages.

        Args:
            car_id: The TeslaMate car ID
            start_date: Optional start date in RFC3339 format (e.g., 2006-01-02T15:04:05Z)
            end_date: Optional end date in RFC3339 format
            page: TeslaMate pagination — which page to fetch (default 1).
            show: TeslaMate pagination — entries per page (default 100).
            fetch_all: When True, auto-paginate from page 1 until
                exhausted. Aggregated payload contains
                `data.pages_fetched` and `data.truncated`.
        """
        auth = teslamate_auth_kwargs(ctx)
        if not fetch_all:
            return execute(
                teslamate_module.get_car_charges,
                car_id=car_id,
                start_date=start_date,
                end_date=end_date,
                page=page,
                show=show,
                **auth,
            )
        return _fetch_all_pages(
            lambda *, page, show: execute(
                teslamate_module.get_car_charges,
                car_id=car_id,
                start_date=start_date,
                end_date=end_date,
                page=page,
                show=show,
                **auth,
            ),
            list_key="charges",
            id_key="charge_id",
            show=show,
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
        page: int = 1,
        show: int = 100,
        fetch_all: bool = False,
    ):
        """Driving sessions for a specific car. Filter by date range or distance.

        TeslaMate paginates at 100 entries per call by default. Use `page`
        / `show` to walk through manually, or `fetch_all=True` to let the
        server auto-paginate (capped at ~20 pages of safety). Set
        `fetch_all=True` whenever the user asks for a count or average
        across a long period (e.g. "combien de trajets en 2026").

        Args:
            car_id: The TeslaMate car ID
            start_date: Optional start date in RFC3339 format
            end_date: Optional end date in RFC3339 format
            min_distance: Optional minimum trip distance (TeslaMate units)
            max_distance: Optional maximum trip distance (TeslaMate units)
            page: TeslaMate pagination — which page to fetch (default 1).
            show: TeslaMate pagination — entries per page (default 100).
            fetch_all: When True, auto-paginate from page 1 until
                exhausted. Aggregated payload contains
                `data.pages_fetched` and `data.truncated`.
        """
        auth = teslamate_auth_kwargs(ctx)
        if not fetch_all:
            return execute(
                teslamate_module.get_car_drives,
                car_id=car_id,
                start_date=start_date,
                end_date=end_date,
                min_distance=min_distance,
                max_distance=max_distance,
                page=page,
                show=show,
                **auth,
            )
        return _fetch_all_pages(
            lambda *, page, show: execute(
                teslamate_module.get_car_drives,
                car_id=car_id,
                start_date=start_date,
                end_date=end_date,
                min_distance=min_distance,
                max_distance=max_distance,
                page=page,
                show=show,
                **auth,
            ),
            list_key="drives",
            id_key="drive_id",
            show=show,
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
