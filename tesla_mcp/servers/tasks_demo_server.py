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

        cars = payload.get("data") if isinstance(payload, dict) else payload
        if not isinstance(cars, list):
            cars = []

        await progress.set_total(max(1, len(cars)))

        for idx, car in enumerate(cars, start=1):
            car_id = car.get("car_id") or car.get("id")
            name = car.get("name") or car.get("display_name")
            await progress.set_message(f"car {idx}/{len(cars)}: id={car_id} name={name}")
            await progress.increment()
            if per_car_delay_s > 0 and idx < len(cars):
                await asyncio.sleep(per_car_delay_s)

        if not cars:
            await progress.set_message("no cars returned by TeslaMate API")

        return {"count": len(cars), "cars": cars}

    return mcp
