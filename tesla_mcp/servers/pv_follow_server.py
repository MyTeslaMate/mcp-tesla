"""PV-follow smart charging sub-server.

Mounted on the main FastMCP server with ``namespace="pv_follow"`` so each tool
exposed here is reachable as ``pv_follow_<name>`` from the parent. The flagship
tool ``start`` is registered as a background task (``task=True``) so the
control loop runs server-side while the client tracks progress and can read
status via the companion read tools.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Optional

from fastmcp import Context, FastMCP

from ..auth_context import extract_bearer_token, make_tesla_tool
from ..modules.commands import VehicleCommandsModule
from ..modules.energy import EnergyModule
from ..modules.pv_follow import (
    PVFollowConfig,
    PVFollowConfigStore,
    PVFollowRegistry,
    PVFollowSession,
)
from ..modules.vehicles import VehicleEndpoints


_TAGS = {"tesla_fleet_api", "pv_follow"}


def build_pv_follow_server(
    *,
    energy_module: EnergyModule,
    commands_module: VehicleCommandsModule,
    vehicle_module: VehicleEndpoints,
    config_store: PVFollowConfigStore,
    registry: PVFollowRegistry,
    app_csp: dict[str, Any],
) -> FastMCP:
    """Build the PV-follow sub-server bound to the shared modules + registry."""
    mcp = FastMCP("MyTeslaMate – PV Follow", tasks=True)
    tesla_tool = make_tesla_tool(mcp, app_csp)

    @tesla_tool(read_only=False, destructive=True, open_world=True, task=True, tags=_TAGS)
    async def start(
        ctx: Context,
        vehicle_tag: str,
        energy_site_id: Optional[str] = None,
        target_soc_percent: Optional[int] = None,
        min_amps: Optional[int] = None,
        max_amps: Optional[int] = None,
        interval_s: Optional[int] = None,
        min_pw_soc_percent: Optional[int] = None,
        start_hysteresis_s: Optional[int] = None,
        stop_hysteresis_s: Optional[int] = None,
        voltage_v: Optional[int] = None,
        phases: Optional[int] = None,
    ) -> dict:
        """Start a PV-follow session (long-running background task).

        Continuously matches the vehicle's charging current to the solar
        surplus reported by the Powerwall. The car only draws what's being
        exported to the grid — never imports. Hysteresis on start/stop avoids
        flapping with passing clouds.

        Args:
            vehicle_tag: Target vehicle (VIN or vehicle_id).
            energy_site_id: Powerwall site ID. If omitted, falls back to the
                persisted config for this vehicle.
            target_soc_percent: Stop the session when battery_level reaches
                this value. If omitted, falls back to the car's charge_limit_soc.
            min_amps / max_amps: Bound the charging current (default 5–16 A).
            interval_s: Control-loop period in seconds (default 30).
            min_pw_soc_percent: Don't divert surplus below this Powerwall SoC
                (default 50%, leaves headroom for the home battery).
            start_hysteresis_s / stop_hysteresis_s: Surplus must persist this
                long before starting/stopping the charge (defaults 120/180s).
            voltage_v / phases: Override the voltage/phase detection if the
                car doesn't expose them while idle.
        """
        bearer_token = extract_bearer_token(ctx)
        overrides = {
            "energy_site_id": energy_site_id,
            "target_soc_percent": target_soc_percent,
            "min_amps": min_amps,
            "max_amps": max_amps,
            "interval_s": interval_s,
            "min_pw_soc_percent": min_pw_soc_percent,
            "start_hysteresis_s": start_hysteresis_s,
            "stop_hysteresis_s": stop_hysteresis_s,
            "voltage_v": voltage_v,
            "phases": phases,
        }
        base_config = config_store.get_config(vehicle_tag)
        config = base_config.merged_with(overrides)
        if not config.energy_site_id:
            raise ValueError(
                "energy_site_id is required (pass as argument or persist via pv_follow_set_config)"
            )

        session = PVFollowSession(
            vehicle_tag=vehicle_tag,
            config=config,
            bearer_token=bearer_token,
            energy_module=energy_module,
            commands_module=commands_module,
            vehicle_module=vehicle_module,
        )
        await registry.register(session)
        try:
            return await session.run()
        finally:
            await registry.unregister(vehicle_tag)

    @tesla_tool(read_only=False, destructive=True, open_world=True, tags=_TAGS)
    async def stop(ctx: Context, vehicle_tag: str) -> dict:
        """Signal the active PV-follow session to stop at the next tick.

        Does NOT explicitly stop charging — the car keeps doing whatever it's
        currently doing once the loop exits. Call charge_stop separately if
        you also want to cut the charge.

        Args:
            vehicle_tag: Vehicle whose session should stop.
        """
        session = registry.get(vehicle_tag)
        if session is None:
            return {"running": False, "message": "no active session"}
        session.request_stop()
        return {"running": True, "stop_requested": True}

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TAGS)
    async def status(ctx: Context, vehicle_tag: str) -> dict:
        """Read the live state of the active PV-follow session for this vehicle.

        Returns ``{"running": False}`` if no session is active.

        Args:
            vehicle_tag: Vehicle to inspect.
        """
        session = registry.get(vehicle_tag)
        if session is None:
            return {"running": False}
        return {
            "running": True,
            "stop_requested": session.stop_requested,
            "config": asdict(session.config),
            "state": asdict(session.state),
        }

    @tesla_tool(read_only=True, destructive=False, open_world=True, tags=_TAGS)
    async def get_config(ctx: Context, vehicle_tag: str) -> dict:
        """Return the persisted PV-follow configuration for this vehicle.

        Falls back to defaults if no config has been saved yet.

        Args:
            vehicle_tag: Vehicle whose config to load.
        """
        return asdict(config_store.get_config(vehicle_tag))

    @tesla_tool(read_only=False, destructive=True, open_world=True, tags=_TAGS)
    async def set_config(
        ctx: Context,
        vehicle_tag: str,
        energy_site_id: Optional[str] = None,
        target_soc_percent: Optional[int] = None,
        min_amps: Optional[int] = None,
        max_amps: Optional[int] = None,
        interval_s: Optional[int] = None,
        min_pw_soc_percent: Optional[int] = None,
        start_hysteresis_s: Optional[int] = None,
        stop_hysteresis_s: Optional[int] = None,
        voltage_v: Optional[int] = None,
        phases: Optional[int] = None,
    ) -> dict:
        """Persist a PV-follow configuration for this vehicle.

        Only fields you provide are updated; others keep their current value.
        See ``start`` for argument semantics.
        """
        existing = config_store.get_config(vehicle_tag)
        merged = existing.merged_with(
            {
                "energy_site_id": energy_site_id,
                "target_soc_percent": target_soc_percent,
                "min_amps": min_amps,
                "max_amps": max_amps,
                "interval_s": interval_s,
                "min_pw_soc_percent": min_pw_soc_percent,
                "start_hysteresis_s": start_hysteresis_s,
                "stop_hysteresis_s": stop_hysteresis_s,
                "voltage_v": voltage_v,
                "phases": phases,
            }
        )
        saved = config_store.set_config(vehicle_tag, merged)
        return asdict(saved)

    return mcp
