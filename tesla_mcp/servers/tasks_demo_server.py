"""Tasks demo sub-server.

Single long-running task to validate FastMCP Tasks plumbing (Docket worker,
progress reporting, task ID tracking) without touching a Powerwall or sending
any vehicle command. Mounted under ``namespace="demo"`` so the tool is
reachable as ``demo_list_cars``.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Progress

from ..auth_context import make_tesla_tool, teslamate_auth_kwargs
from ..modules.teslamateapi import TeslaMateAPIModule


_TAGS = {"teslamate", "demo"}


def build_tasks_demo_server(
    *,
    teslamate_module: TeslaMateAPIModule,
    app_csp: dict[str, Any],
) -> FastMCP:
    """Build the tasks-demo sub-server with one long-running task."""
    mcp = FastMCP("MyTeslaMate – Tasks Demo", tasks=True)
    tesla_tool = make_tesla_tool(mcp, app_csp)

    @tesla_tool(read_only=True, destructive=False, open_world=True, task=True, tags=_TAGS)
    async def list_cars(
        ctx: Context,
        per_car_delay_s: float = 0.5,
        progress: Progress = Progress(),
    ) -> dict:
        """List TeslaMate cars as a long-running background task.

        Reads the cars from the TeslaMate API and emits one progress tick per
        car. Used to validate the FastMCP Tasks plumbing end-to-end (task_id
        handoff, Docket worker, progress reporting, structured result).

        Args:
            per_car_delay_s: Artificial delay between cars so progress is
                observable in clients. Set to 0 for a real-speed run.
        """
        auth_kwargs = teslamate_auth_kwargs(ctx)
        payload = teslamate_module.get_cars(**auth_kwargs)
        cars = _coerce_cars(payload)

        await progress.set_total(max(1, len(cars)))

        for idx, car in enumerate(cars, start=1):
            car_id = car.get("car_id") or car.get("id") if isinstance(car, dict) else None
            name = car.get("name") or car.get("display_name") if isinstance(car, dict) else None
            await progress.set_message(f"car {idx}/{len(cars)}: id={car_id} name={name}")
            await progress.increment()
            if per_car_delay_s > 0 and idx < len(cars):
                await asyncio.sleep(per_car_delay_s)

        if not cars:
            await progress.set_message(
                f"no cars in payload (type={type(payload).__name__})"
            )

        return {
            "count": len(cars),
            "cars": cars,
            "payload_type": type(payload).__name__,
            "payload_keys": list(payload.keys()) if isinstance(payload, dict) else None,
            "raw": payload,
        }

    return mcp


def _coerce_cars(payload: Any, _depth: int = 0) -> list[dict[str, Any]]:
    """Best-effort extraction of the cars list from a TeslaMate response.

    The API has been seen wrapping the list under several layers, e.g.
    ``{"data": {"cars": [...]}}`` or just ``{"data": [...]}`` or ``[...]``
    directly. Recurse through known envelope keys up to a small depth, and
    fall back to the first list-of-dicts found in a dict's values.
    """
    if isinstance(payload, list):
        return [c for c in payload if isinstance(c, dict)]
    if isinstance(payload, dict) and _depth < 4:
        for key in ("cars", "data", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list) and (not value or isinstance(value[0], dict)):
                return [c for c in value if isinstance(c, dict)]
            if isinstance(value, dict):
                nested = _coerce_cars(value, _depth + 1)
                if nested:
                    return nested
        for value in payload.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value
    return []
