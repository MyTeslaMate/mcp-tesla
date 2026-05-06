"""Tasks demo sub-server.

Single long-running task to validate FastMCP Tasks plumbing (Docket worker,
progress reporting, task ID tracking) without touching a Powerwall or sending
any vehicle command. Mounted under ``namespace="demo"`` so the tool is
reachable as ``demo_list_cars``.
"""

from __future__ import annotations

import asyncio
import time
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
    async def poll_cars(
        ctx: Context,
        iterations: int = 10,
        interval_s: float = 3.0,
        progress: Progress = Progress(),
    ) -> dict:
        """Periodically poll TeslaMate cars to exercise the Tasks scheduler.

        Re-fetches the cars list ``iterations`` times, sleeping ``interval_s``
        between calls, and accumulates per-tick snapshots. The point isn't the
        data — it's to drive a genuinely long-running async loop so you can
        observe progress, task_id tracking, and Docket worker scheduling
        end-to-end.

        Args:
            iterations: Number of polls (default 10).
            interval_s: Seconds between polls (default 3.0).
        """
        auth_kwargs = teslamate_auth_kwargs(ctx)
        iterations = max(1, iterations)
        await progress.set_total(iterations)

        snapshots: list[dict[str, Any]] = []
        last_payload: Any = None
        last_error: str | None = None

        for tick in range(1, iterations + 1):
            ts = time.time()
            try:
                payload = teslamate_module.get_cars(**auth_kwargs)
                cars = _coerce_cars(payload)
                last_payload = payload
                last_error = None
            except Exception as exc:  # noqa: BLE001
                cars = []
                last_error = str(exc)

            snapshots.append(
                {
                    "tick": tick,
                    "ts": ts,
                    "count": len(cars),
                    "first_car": cars[0] if cars else None,
                    "error": last_error,
                }
            )

            await progress.set_message(
                f"tick {tick}/{iterations} cars={len(cars)}"
                + (f" error={last_error}" if last_error else "")
            )
            await progress.increment()

            if tick < iterations:
                await asyncio.sleep(interval_s)

        return {
            "iterations": iterations,
            "interval_s": interval_s,
            "snapshots": snapshots,
            "last_payload_type": type(last_payload).__name__,
            "last_payload_keys": list(last_payload.keys())
            if isinstance(last_payload, dict)
            else None,
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
