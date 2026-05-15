from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

from fastmcp import Context, FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.utilities.types import Image
from mcp.types import Icon


from .auth_context import (
    execute as _execute,
    extract_bearer_token as _extract_bearer_token,
    sanitize_response_payload as _sanitize_response_payload,
)
from .base import TeslaClient

from .modules import VehicleEndpoints, VehicleCommandsModule, EnergyModule, ChargingModule, UserModule, TeslaMateAPIModule
from .oauth import TeslaProvider

from starlette.responses import JSONResponse, PlainTextResponse

import os


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tesla_mcp")


# Patch FastMCP's PrefabApp serialiser so the JSON also lands in `content[0].text`,
# not only in `structuredContent`. Native MCP integrations (Anthropic
# `mcp_servers`, OpenAI `tools[type=mcp]`) only surface the `content` array
# to API consumers — they drop `structuredContent`. Without this, our chat
# backend receives the literal placeholder "[Rendered Prefab UI]" and the
# Prefab iframe can't mount. Apps SDK clients (ChatGPT/Claude.ai) read
# `structuredContent` directly and are unaffected.
def _patch_prefab_tool_result_to_inline_json() -> None:
    import json
    from fastmcp.tools import base as _fastmcp_base
    from mcp.types import TextContent as _TextContent

    original = _fastmcp_base._prefab_to_tool_result

    def _patched(app, fastmcp_app_name=None):
        result = original(app, fastmcp_app_name=fastmcp_app_name)
        structured = getattr(result, "structured_content", None)
        if structured is not None:
            try:
                payload = json.dumps(structured, ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError):
                return result
            result.content = [_TextContent(type="text", text=payload)]
        return result

    _fastmcp_base._prefab_to_tool_result = _patched


_patch_prefab_tool_result_to_inline_json()


def _normalize_origin(url: str | None) -> str | None:
    """Return normalized https origin from a URL-like value."""
    if not url:
        return None

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None

    return f"{parsed.scheme}://{parsed.netloc}"


def _build_csp_connect_domains() -> list[str]:
    """Build strict, deduplicated connect domains for FastMCP app CSP."""
    configured_base_url = _normalize_origin(os.environ.get("TESLA_OAUTH_BASE_URL"))
    configured_mtm_url = _normalize_origin(os.environ.get("TESLA_OAUTH_MTM_BASE_URL"))

    connect_domains = [
        configured_base_url or "https://mcp.myteslamate.com",
        "https://fleet-auth.prd.vn.cloud.tesla.com",
    ]
    if configured_mtm_url:
        connect_domains.append(configured_mtm_url)

    # Preserve order while deduplicating
    return list(dict.fromkeys(connect_domains))


APP_CSP = {
    "connect_domains": _build_csp_connect_domains(),
    "resource_domains": [],
    "frame_domains": [],
    "base_uri_domains": [],
}


_ASSETS_DIR = Path(__file__).parent / "assets"


def _build_app_icons() -> list[Icon]:
    """Embed local icons as data URIs (SVG primary, PNG raster fallback)."""
    icons: list[Icon] = []
    svg_path = _ASSETS_DIR / "logo.svg"
    if svg_path.exists():
        icons.append(
            Icon(
                src=Image(path=svg_path, format="svg+xml").to_data_uri(),
                mimeType="image/svg+xml",
                sizes=["any"],
            )
        )
    png_path = _ASSETS_DIR / "icon.png"
    if png_path.exists():
        icons.append(
            Icon(
                src=Image(path=png_path).to_data_uri(),
                mimeType="image/png",
                sizes=["1024x1024"],
            )
        )
    return icons

mcp_port = int(os.environ.get("PORT", 8084))
openai_apps_challenge_token = os.environ.get(
    "OPENAI_APPS_CHALLENGE_TOKEN",
    "mjfI5TvAUa5hL6MtblBT5Q_6Vg1Y8qEltcPyIor5Cz4",
)
_tesla_oauth_client_id = os.environ.get("TESLA_OAUTH_CLIENT_ID")

BASE_INSTRUCTIONS = (
    "MyTeslaMate MCP — control and inspect Tesla vehicles and energy products via the "
    "official Tesla Fleet API, and query historical drive/charge analytics via TeslaMate.\n\n"
    "At conversation start, call `list_vehicles_and_energy_sites` to discover the products "
    "on this account; use the returned `id`/`vin` as `vehicle_tag` for subsequent commands. "
    "Use `get_user_info` for account profile details. Most vehicle commands require an "
    "awake vehicle — call `wake_up_vehicle` first if a command fails with an offline/sleep "
    "error.\n\n"
    "Tool categories:\n"
    "- Live data & state: `get_vehicle`, `get_vehicle_data`\n"
    "- Vehicle commands (locks, climate, charging, navigation, …): destructive — confirm "
    "intent before calling.\n"
    "- Energy products: `energy_live_status`, `energy_history`, `energy_storm_mode`, …\n"
    "- Historical analytics (TeslaMate): `teslamate_get_cars`, `teslamate_get_car_drives`, "
    "`teslamate_get_car_charges`, …\n\n"
    "Always summarise tool results in natural language; widgets render automatically where "
    "available."
)

mcp = FastMCP(
    "MyTeslaMate MCP",
    auth=TeslaProvider() if _tesla_oauth_client_id else None,
    icons=_build_app_icons(),
    website_url="https://app.myteslamate.com",
    instructions=BASE_INSTRUCTIONS,
)
client = TeslaClient()
vehicle_module = VehicleEndpoints(client)
commands_module = VehicleCommandsModule(client)
energy_module = EnergyModule(client)
charging_module = ChargingModule(client)
user_module = UserModule(client)
teslamate_module = TeslaMateAPIModule(client)


def tesla_tool(
    *,
    tags: set[str],
    read_only: bool,
    destructive: bool,
    open_world: bool = True,
    output_template: str | None = None,
):
    """Register MCP tool with mandatory OpenAI-compatible safety hints."""
    kwargs = dict(
        tags=tags,
        annotations={
            "readOnlyHint": read_only,
            "destructiveHint": destructive,
            "openWorldHint": open_world,
        },
        app={"csp": APP_CSP},
    )
    if output_template is not None:
        kwargs["meta"] = {"openai/outputTemplate": output_template}
    return mcp.tool(**kwargs)


_WIDGETS_DIR = Path(__file__).parent / "widgets"

VEHICLE_LIVE_WIDGET_META = {
    "ui": {
        "domain": "https://mcp.myteslamate.com",
        "csp": {
            "connectDomains": [
                "https://mcp.myteslamate.com",
                "https://fleet-auth.prd.vn.cloud.tesla.com",
            ],
            "resourceDomains": [],
        },
    },
    "openai/widgetDescription": "Shows a vehicle live data card rendered by get_vehicle_data."
}


PRODUCTS_LIST_WIDGET_META = {
    "ui": {
        "domain": "https://mcp.myteslamate.com",
        "csp": {
            "connectDomains": [
                "https://mcp.myteslamate.com",
                "https://fleet-auth.prd.vn.cloud.tesla.com",
            ],
            "resourceDomains": [],
        },
    },
    "openai/widgetDescription": "Lists Tesla vehicles and energy sites available to the authenticated account."
}


@mcp.resource(
    uri="ui://widget/vehicle-live.html",
    name="Vehicle Live Widget",
    mime_type="text/html+skybridge",
    meta=VEHICLE_LIVE_WIDGET_META,
)
def vehicle_live_widget() -> str:
    """HTML widget rendering a live vehicle state card for `get_vehicle_data`."""
    return (_WIDGETS_DIR / "vehicle_live.html").read_text(encoding="utf-8")


@mcp.resource(
    uri="ui://widget/products-list.html",
    name="Tesla Products Widget",
    mime_type="text/html+skybridge",
    meta=PRODUCTS_LIST_WIDGET_META,
)
def products_list_widget() -> str:
    """HTML widget rendering the list of vehicles and energy sites for `list_vehicles_and_energy_sites`."""
    return (_WIDGETS_DIR / "products_list.html").read_text(encoding="utf-8")


@tesla_tool(
    read_only=True,
    destructive=False,
    open_world=True,
    tags={"tesla_fleet_api"},
    output_template="ui://widget/products-list.html",
)
def list_vehicles_and_energy_sites(ctx: Context):
    """Return the vehicles and energy sites available to the authenticated account."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(vehicle_module.products, bearer_token=bearer_token)

@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_vehicle(vehicle_tag: str, ctx: Context):
    """Fetch detailed metadata for a vehicle."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_vehicle,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@tesla_tool(
    read_only=True,
    destructive=False,
    open_world=True,
    tags={"tesla_fleet_api"},
    output_template="ui://widget/vehicle-live.html",
)
def get_vehicle_data(vehicle_tag: str, ctx: Context):
    """Fetch live vehicle data (location, climate, charge, etc.)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_vehicle_data,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def wake_up_vehicle(vehicle_tag: str, ctx: Context):
    """Wake a sleeping vehicle."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.wake_up_vehicle,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_mobile_enabled(vehicle_tag: str, ctx: Context):
    """Check if the vehicle allows mobile access."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_mobile_enabled,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_nearby_charging_sites(vehicle_tag: str, ctx: Context):
    """List charging sites close to the vehicle."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_nearby_charging_sites,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_service_data(vehicle_tag: str, ctx: Context):
    """Retrieve service-related data for the vehicle."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_service_data,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_release_notes(vehicle_tag: str, ctx: Context):
    """Return the latest firmware release notes."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_release_notes,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_recent_alerts(vehicle_tag: str, ctx: Context):
    """Return recent vehicle alerts."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_recent_alerts,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_fleet_status(vins: list[str], ctx: Context):
    """Return fleet status details for the provided VINs."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_fleet_status,
        vins=vins,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_vehicle_options(vin: str, ctx: Context):
    """Return option codes for a VIN."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_vehicle_options,
        vin=vin,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_eligible_upgrades(vin: str, ctx: Context):
    """Return upgrades available for a VIN."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_eligible_upgrades,
        vin=vin,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_eligible_subscriptions(vin: str, ctx: Context):
    """Return subscription offers for a VIN."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_eligible_subscriptions,
        vin=vin,
        bearer_token=bearer_token,
    )


# === Drivers & Sharing ===


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_drivers(vehicle_tag: str, ctx: Context):
    """
    Returns all allowed drivers for a vehicle.
    Note: This endpoint is only available for the vehicle owner.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_drivers,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def remove_driver(vehicle_tag: str, ctx: Context, share_user_id: Optional[str] = None):
    """
    Removes driver access from a vehicle.
    Share users can only remove their own access.
    Owners can remove share access or their own.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.remove_driver,
        vehicle_tag=vehicle_tag,
        share_user_id=share_user_id,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_share_invites(
    vehicle_tag: str,
    ctx: Context,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
):
    """
    Returns the active share invites for a vehicle.
    This endpoint is paginated with a max page size of 25 records.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_share_invites,
        vehicle_tag=vehicle_tag,
        page=page,
        page_size=page_size,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def create_share_invite(vehicle_tag: str, ctx: Context):
    """
    Create a share invite for a vehicle.
    - Each invite link is for single-use and expires after 24 hours.
    - Provides DRIVER privileges (not all OWNER features)
    - Up to five drivers can be added at a time
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.create_share_invite,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )

# === Fleet Telemetry ===


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_fleet_telemetry_config(vehicle_tag: str, ctx: Context):
    """
    Fetches a vehicle's fleet telemetry config.
    - synced=true: vehicle has adopted the target config
    - synced=false: vehicle will attempt to adopt the target config on next backend connection
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_fleet_telemetry_config,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def delete_fleet_telemetry_config(vehicle_tag: str, ctx: Context):
    """
    Remove a fleet telemetry configuration from a vehicle.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.delete_fleet_telemetry_config,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_fleet_telemetry_errors(vehicle_tag: str, ctx: Context):
    """
    Returns recent fleet telemetry errors reported for the specified vehicle.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_fleet_telemetry_errors,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


# === Subscriptions ===


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_subscriptions(ctx: Context, device_token: Optional[str] = None):
    """
    Returns the list of vehicles for which this mobile device currently subscribes to push notifications.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_subscriptions,
        device_token=device_token,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def set_subscriptions(vehicle_ids: list[int], device_token: str, ctx: Context):
    """
    Allows a mobile device to specify which vehicles to receive push notifications from.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.set_subscriptions,
        vehicle_ids=vehicle_ids,
        device_token=device_token,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_vehicle_subscriptions(ctx: Context):
    """
    Returns the list of vehicles for which this mobile device currently subscribes to push notifications.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_vehicle_subscriptions,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def set_vehicle_subscriptions(vehicle_ids: list[int], ctx: Context):
    """
    Allows a mobile device to specify which vehicles to receive push notifications from.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.set_vehicle_subscriptions,
        vehicle_ids=vehicle_ids,
        bearer_token=bearer_token,
    )


# === Warranty & Other ===


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_warranty_details(vin: str, ctx: Context):
    """
    Returns the warranty information for a vehicle.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_warranty_details,
        vin=vin,
        bearer_token=bearer_token,
    )


# === Vehicle Commands ===


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def door_lock(ctx: Context, vehicle_tag: str):
    """Lock the vehicle doors."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.door_lock, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def door_unlock(ctx: Context, vehicle_tag: str):
    """Unlock the vehicle doors."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.door_unlock, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def actuate_trunk(ctx: Context, vehicle_tag: str, which_trunk: str):
    """
    Open/close the front or rear trunk.
    
    Args:
        which_trunk: "front" or "rear"
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.actuate_trunk, vehicle_tag=vehicle_tag, which_trunk=which_trunk, bearer_token=bearer_token
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def auto_conditioning_start(ctx: Context, vehicle_tag: str):
    """Start climate preconditioning."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.auto_conditioning_start, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def auto_conditioning_stop(ctx: Context, vehicle_tag: str):
    """Stop climate preconditioning."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.auto_conditioning_stop, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def set_temps(ctx: Context, vehicle_tag: str, driver_temp: Optional[float] = None, passenger_temp: Optional[float] = None):
    """
    Set cabin temperature (Celsius).
    
    Args:
        driver_temp: Driver-side temperature
        passenger_temp: Passenger-side temperature (if None, syncs with driver)
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.set_temps,
        vehicle_tag=vehicle_tag,
        driver_temp=driver_temp,
        passenger_temp=passenger_temp,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def set_climate_keeper_mode(ctx: Context, vehicle_tag: str, climate_keeper_mode: int):
    """
    Set climate keeper mode.
    
    Args:
        climate_keeper_mode: 0=Off, 1=Keep, 2=Dog, 3=Camp
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.set_climate_keeper_mode,
        vehicle_tag=vehicle_tag,
        climate_keeper_mode=climate_keeper_mode,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def set_bioweapon_mode(ctx: Context, vehicle_tag: str, on: bool):
    """Enable/disable Bioweapon Defense Mode."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.set_bioweapon_mode, vehicle_tag=vehicle_tag, on=on, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def set_cabin_overheat_protection(ctx: Context, vehicle_tag: str, on: bool, fan_only: bool):
    """Set cabin overheat protection."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.set_cabin_overheat_protection,
        vehicle_tag=vehicle_tag,
        on=on,
        fan_only=fan_only,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def set_cop_temp(ctx: Context, vehicle_tag: str, cop_level: int):
    """
    Set cabin overheat protection temperature.
    
    Args:
        cop_level: 0=Low (90F/30C), 1=Medium (95F/35C), 2=High (100F/40C)
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.set_cop_temp, vehicle_tag=vehicle_tag, cop_level=cop_level, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def set_preconditioning_max(ctx: Context, vehicle_tag: str, on: bool, manual_override: bool):
    """Set preconditioning max override."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.set_preconditioning_max,
        vehicle_tag=vehicle_tag,
        on=on,
        manual_override=manual_override,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def remote_seat_heater_request(ctx: Context, vehicle_tag: str, heater: int, level: int):
    """
    Set seat heating level.
    
    Args:
        heater: Seat position (0=driver, 1=passenger, 2=rear-left, 4=rear-center, 5=rear-right)
        level: Heat level 0-3
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.remote_seat_heater_request,
        vehicle_tag=vehicle_tag,
        heater=heater,
        level=level,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def remote_seat_cooler_request(ctx: Context, vehicle_tag: str, seat_position: int, seat_cooler_level: int):
    """
    Set seat cooling level.
    
    Args:
        seat_position: Seat position
        seat_cooler_level: Cooling level 0-3
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.remote_seat_cooler_request,
        vehicle_tag=vehicle_tag,
        seat_position=seat_position,
        seat_cooler_level=seat_cooler_level,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def remote_auto_seat_climate_request(ctx: Context, vehicle_tag: str, auto_seat_position: int, auto_climate_on: bool):
    """Enable/disable automatic seat heating and cooling."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.remote_auto_seat_climate_request,
        vehicle_tag=vehicle_tag,
        auto_seat_position=auto_seat_position,
        auto_climate_on=auto_climate_on,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def remote_steering_wheel_heater_request(ctx: Context, vehicle_tag: str, on: bool):
    """Enable/disable steering wheel heater."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.remote_steering_wheel_heater_request, vehicle_tag=vehicle_tag, on=on, bearer_token=bearer_token
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def remote_steering_wheel_heat_level_request(ctx: Context, vehicle_tag: str, level: int):
    """Set steering wheel heat level."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.remote_steering_wheel_heat_level_request,
        vehicle_tag=vehicle_tag,
        level=level,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def remote_auto_steering_wheel_heat_climate_request(ctx: Context, vehicle_tag: str, on: bool):
    """Enable/disable automatic steering wheel heating."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.remote_auto_steering_wheel_heat_climate_request,
        vehicle_tag=vehicle_tag,
        on=on,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def charge_start(ctx: Context, vehicle_tag: str):
    """Start charging."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.charge_start, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def charge_stop(ctx: Context, vehicle_tag: str):
    """Stop charging."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.charge_stop, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def charge_port_door_open(ctx: Context, vehicle_tag: str):
    """Open charge port door."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.charge_port_door_open, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def charge_port_door_close(ctx: Context, vehicle_tag: str):
    """Close charge port door."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.charge_port_door_close, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def set_charge_limit(ctx: Context, vehicle_tag: str, percent: int):
    """Set charge limit percentage (50-100)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.set_charge_limit, vehicle_tag=vehicle_tag, percent=percent, bearer_token=bearer_token
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def charge_standard(ctx: Context, vehicle_tag: str):
    """Set charge mode to standard range."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.charge_standard, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def charge_max_range(ctx: Context, vehicle_tag: str):
    """Set charge mode to max range."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.charge_max_range, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def set_charging_amps(ctx: Context, vehicle_tag: str, charging_amps: int):
    """Set charging amperage."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.set_charging_amps, vehicle_tag=vehicle_tag, charging_amps=charging_amps, bearer_token=bearer_token
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def set_scheduled_charging(ctx: Context, vehicle_tag: str, enable: bool, time: int):
    """
    Set scheduled charging (deprecated, use add_charge_schedule).
    
    Args:
        enable: Enable scheduled charging
        time: Minutes after midnight
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.set_scheduled_charging,
        vehicle_tag=vehicle_tag,
        enable=enable,
        time=time,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def add_charge_schedule(
    ctx: Context,
    vehicle_tag: str,
    time: str,
    latitude: float,
    longitude: float,
    name: Optional[str] = None,
    one_time: Optional[bool] = None,
):
    """Add a charge schedule."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.add_charge_schedule,
        vehicle_tag=vehicle_tag,
        time=time,
        latitude=latitude,
        longitude=longitude,
        name=name,
        one_time=one_time,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def remove_charge_schedule(ctx: Context, vehicle_tag: str, schedule_id: int):
    """Remove a charge schedule by ID."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.remove_charge_schedule, vehicle_tag=vehicle_tag, schedule_id=schedule_id, bearer_token=bearer_token
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def add_precondition_schedule(
    ctx: Context,
    vehicle_tag: str,
    time: str,
    latitude: float,
    longitude: float,
    name: Optional[str] = None,
    one_time: Optional[bool] = None,
):
    """Add a precondition schedule."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.add_precondition_schedule,
        vehicle_tag=vehicle_tag,
        time=time,
        latitude=latitude,
        longitude=longitude,
        name=name,
        one_time=one_time,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def remove_precondition_schedule(ctx: Context, vehicle_tag: str, schedule_id: int):
    """Remove a precondition schedule by ID."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.remove_precondition_schedule,
        vehicle_tag=vehicle_tag,
        schedule_id=schedule_id,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def window_control(ctx: Context, vehicle_tag: str, command: str, lat: float, lon: float):
    """
    Control windows.
    
    Args:
        command: "vent" or "close"
        lat: User latitude
        lon: User longitude
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.window_control,
        vehicle_tag=vehicle_tag,
        command=command,
        lat=lat,
        lon=lon,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def sun_roof_control(ctx: Context, vehicle_tag: str, state: str):
    """
    Control sunroof.
    
    Args:
        state: "stop", "close", or "vent"
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.sun_roof_control, vehicle_tag=vehicle_tag, state=state, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def flash_lights(ctx: Context, vehicle_tag: str):
    """Flash the headlights."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.flash_lights, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def honk_horn(ctx: Context, vehicle_tag: str):
    """Honk the horn."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.honk_horn, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def adjust_volume(ctx: Context, vehicle_tag: str, volume: float):
    """Adjust media volume (0.0-10.0)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.adjust_volume, vehicle_tag=vehicle_tag, volume=volume, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def navigation_request(ctx: Context, vehicle_tag: str, address: str, locale: str = "en-US"):
    """Send navigation destination."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.navigation_request,
        vehicle_tag=vehicle_tag,
        address=address,
        locale=locale,
        bearer_token=bearer_token,
    )

@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def set_sentry_mode(ctx: Context, vehicle_tag: str, on: bool):
    """Enable/disable Sentry Mode."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.set_sentry_mode, vehicle_tag=vehicle_tag, on=on, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def set_valet_mode(ctx: Context, vehicle_tag: str, on: bool, password: str):
    """Enable/disable Valet Mode with 4-digit PIN."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.set_valet_mode, vehicle_tag=vehicle_tag, on=on, password=password, bearer_token=bearer_token
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def reset_valet_pin(ctx: Context, vehicle_tag: str):
    """Remove Valet Mode PIN."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.reset_valet_pin, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def speed_limit_set_limit(ctx: Context, vehicle_tag: str, limit_mph: float):
    """Set speed limit (mph)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.speed_limit_set_limit, vehicle_tag=vehicle_tag, limit_mph=limit_mph, bearer_token=bearer_token
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def speed_limit_activate(ctx: Context, vehicle_tag: str, pin: str):
    """Activate Speed Limit Mode with 4-digit PIN."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.speed_limit_activate, vehicle_tag=vehicle_tag, pin=pin, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def speed_limit_deactivate(ctx: Context, vehicle_tag: str, pin: str):
    """Deactivate Speed Limit Mode."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.speed_limit_deactivate, vehicle_tag=vehicle_tag, pin=pin, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def speed_limit_clear_pin(ctx: Context, vehicle_tag: str, pin: str):
    """Clear Speed Limit Mode PIN."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.speed_limit_clear_pin, vehicle_tag=vehicle_tag, pin=pin, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def speed_limit_clear_pin_admin(ctx: Context, vehicle_tag: str):
    """Clear Speed Limit Mode PIN (admin/owner only, firmware 2023.38+)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.speed_limit_clear_pin_admin, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def set_pin_to_drive(ctx: Context, vehicle_tag: str, on: bool, password: str):
    """Set PIN to Drive."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.set_pin_to_drive, vehicle_tag=vehicle_tag, on=on, password=password, bearer_token=bearer_token
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def reset_pin_to_drive_pin(ctx: Context, vehicle_tag: str):
    """Reset PIN to Drive."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.reset_pin_to_drive_pin, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def clear_pin_to_drive_admin(ctx: Context, vehicle_tag: str):
    """Clear PIN to Drive (admin/owner only, firmware 2023.44+)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.clear_pin_to_drive_admin, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def schedule_software_update(ctx: Context, vehicle_tag: str, offset_sec: int):
    """Schedule OTA software update."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.schedule_software_update, vehicle_tag=vehicle_tag, offset_sec=offset_sec, bearer_token=bearer_token
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def cancel_software_update(ctx: Context, vehicle_tag: str):
    """Cancel scheduled software update."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.cancel_software_update, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def remote_start_drive(ctx: Context, vehicle_tag: str):
    """Start vehicle remotely (keyless driving must be enabled)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.remote_start_drive, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def trigger_homelink(ctx: Context, vehicle_tag: str, lat: float, lon: float):
    """Trigger HomeLink (garage door opener)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.trigger_homelink, vehicle_tag=vehicle_tag, lat=lat, lon=lon, bearer_token=bearer_token
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def remote_boombox(ctx: Context, vehicle_tag: str, sound: int):
    """
    Play sound through external speaker.
    
    Args:
        sound: 0=random fart, 2000=locate ping
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.remote_boombox, vehicle_tag=vehicle_tag, sound=sound, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def set_vehicle_name(ctx: Context, vehicle_tag: str, vehicle_name: str):
    """Change vehicle name (requires Vehicle Command Protocol)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.set_vehicle_name, vehicle_tag=vehicle_tag, vehicle_name=vehicle_name, bearer_token=bearer_token
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def guest_mode(ctx: Context, vehicle_tag: str, on: bool):
    """Enable/disable Guest Mode."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.guest_mode, vehicle_tag=vehicle_tag, on=on, bearer_token=bearer_token)


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def erase_user_data(ctx: Context, vehicle_tag: str):
    """Erase user data from UI (must be parked and in Guest Mode)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.erase_user_data, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


# === Energy Sites ===


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def energy_site_info(ctx: Context, energy_site_id: str):
    """
    Returns information about the energy site.
    
    Includes assets (solar, battery), settings (backup reserve), and features (storm_mode_capable).
    Power values are in watts. Energy values are in watt hours.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(energy_module.site_info, energy_site_id=energy_site_id, bearer_token=bearer_token)


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def energy_live_status(ctx: Context, energy_site_id: str):
    """
    Returns the live status of the energy site.
    
    Includes power (watts), state of energy (watt hours), grid status, and storm mode.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(energy_module.live_status, energy_site_id=energy_site_id, bearer_token=bearer_token)


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def energy_history(
    ctx: Context,
    energy_site_id: str,
    start_date: str,
    end_date: str,
    period: Optional[str] = None,
    time_zone: Optional[str] = None,
):
    """
    Returns the energy measurements of the site, aggregated to the requested period.
    
    Args:
        start_date: ISO 8601 date (e.g., "2024-01-01")
        end_date: ISO 8601 date (e.g., "2024-01-31")
        period: Aggregation period (e.g., "day", "week", "month")
        time_zone: Time zone (e.g., "America/Los_Angeles")
    
    Energy values are in watt hours.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        energy_module.energy_history,
        energy_site_id=energy_site_id,
        start_date=start_date,
        end_date=end_date,
        period=period,
        time_zone=time_zone,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def energy_backup_history(
    ctx: Context,
    energy_site_id: str,
    start_date: str,
    end_date: str,
    period: Optional[str] = None,
    time_zone: Optional[str] = None,
):
    """
    Returns the backup (off-grid) event history of the site in duration of seconds.
    
    Args:
        start_date: ISO 8601 date (e.g., "2024-01-01")
        end_date: ISO 8601 date (e.g., "2024-01-31")
        period: Aggregation period (e.g., "day", "week", "month")
        time_zone: Time zone (e.g., "America/Los_Angeles")
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        energy_module.backup_history,
        energy_site_id=energy_site_id,
        start_date=start_date,
        end_date=end_date,
        period=period,
        time_zone=time_zone,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def energy_charge_history(
    ctx: Context,
    energy_site_id: str,
    start_date: str,
    end_date: str,
    time_zone: Optional[str] = None,
):
    """
    Returns the charging history of a wall connector.
    
    Args:
        start_date: ISO 8601 date (e.g., "2024-01-01")
        end_date: ISO 8601 date (e.g., "2024-01-31")
        time_zone: Time zone (e.g., "America/Los_Angeles")
    
    Energy values are in watt hours.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        energy_module.charge_history,
        energy_site_id=energy_site_id,
        start_date=start_date,
        end_date=end_date,
        time_zone=time_zone,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def energy_operation(ctx: Context, energy_site_id: str, default_real_mode: str):
    """
    Set the site's operation mode.
    
    Args:
        default_real_mode: "autonomous" for time-based control, "self_consumption" for self-powered mode
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        energy_module.operation,
        energy_site_id=energy_site_id,
        default_real_mode=default_real_mode,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def energy_backup(ctx: Context, energy_site_id: str, backup_reserve_percent: int):
    """
    Adjust the site's backup reserve.
    
    Args:
        backup_reserve_percent: Backup reserve percentage (0-100)
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        energy_module.backup,
        energy_site_id=energy_site_id,
        backup_reserve_percent=backup_reserve_percent,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def energy_off_grid_vehicle_charging_reserve(
    ctx: Context, energy_site_id: str, off_grid_vehicle_charging_reserve_percent: int
):
    """
    Adjust the site's off-grid vehicle charging backup reserve.
    
    Args:
        off_grid_vehicle_charging_reserve_percent: Reserve percentage for vehicle charging during outage (0-100)
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        energy_module.off_grid_vehicle_charging_reserve,
        energy_site_id=energy_site_id,
        off_grid_vehicle_charging_reserve_percent=off_grid_vehicle_charging_reserve_percent,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def energy_storm_mode(ctx: Context, energy_site_id: str, enabled: bool):
    """
    Update storm watch participation.
    
    Args:
        enabled: Enable/disable storm mode
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        energy_module.storm_mode, energy_site_id=energy_site_id, enabled=enabled, bearer_token=bearer_token
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def energy_grid_import_export(
    ctx: Context,
    energy_site_id: str,
    disallow_charge_from_grid_with_solar_installed: Optional[bool] = None,
    customer_preferred_export_rule: Optional[str] = None,
):
    """
    Allow/disallow charging from the grid and exporting energy to the grid.
    
    Args:
        disallow_charge_from_grid_with_solar_installed: If true, prevent charging from grid when solar is installed
        customer_preferred_export_rule: Export rule (e.g., "battery_ok", "pv_only", "never")
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        energy_module.grid_import_export,
        energy_site_id=energy_site_id,
        disallow_charge_from_grid_with_solar_installed=disallow_charge_from_grid_with_solar_installed,
        customer_preferred_export_rule=customer_preferred_export_rule,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=False, destructive=True, open_world=True, tags={"tesla_fleet_api"})
def energy_time_of_use_settings(ctx: Context, energy_site_id: str, tou_settings: dict):
    """
    Update the time of use settings for the energy site.
    
    Args:
        tou_settings: Tariff structure with seasons, periods, and rates.
                     See https://digitalassets-energy.tesla.com/raw/upload/app/fleet-api/example-tariff/PGE-EV2-A.json
    
    The tariff structure should include:
    - tariff_content_v2: Tariff structure with seasons and time periods
    - Seasons with start/end dates
    - Time of use periods with labels (ON_PEAK, OFF_PEAK, PARTIAL_PEAK, SUPER_OFF_PEAK)
    - Energy charges or demand charges
    - Valid currency strings: USD, EUR, GBP
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        energy_module.time_of_use_settings,
        energy_site_id=energy_site_id,
        tou_settings=tou_settings,
        bearer_token=bearer_token,
    )


# === Charging ===


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def charging_history(
    ctx: Context,
    vin: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
):
    """
    Returns the paginated charging history.
    
    Args:
        vin: Filter by vehicle VIN
        page: Page number for pagination
        page_size: Number of results per page
        start_time: Start timestamp (ISO 8601)
        end_time: End timestamp (ISO 8601)
        sort_by: Field to sort by (e.g., "charge_start_date_time")
        sort_order: Sort order ("asc" or "desc")
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        charging_module.charging_history,
        bearer_token=bearer_token,
        vin=vin,
        page=page,
        page_size=page_size,
        start_time=start_time,
        end_time=end_time,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def charging_invoice(ctx: Context, invoice_id: str):
    """
    Returns a charging invoice PDF for an event from charging history.
    
    Args:
        invoice_id: The invoice ID from charging history
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        charging_module.charging_invoice,
        invoice_id=invoice_id,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def charging_sessions(
    ctx: Context,
    vin: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = None,
):
    """
    Returns the charging session information including pricing and energy data.
    
    Note: This endpoint is only available for business accounts that own a fleet of vehicles.
    
    Args:
        vin: Filter by vehicle VIN
        page: Page number for pagination
        page_size: Number of results per page
        start_time: Start timestamp (ISO 8601)
        end_time: End timestamp (ISO 8601)
        sort_by: Field to sort by
        sort_order: Sort order ("asc" or "desc")
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        charging_module.charging_sessions,
        bearer_token=bearer_token,
        vin=vin,
        page=page,
        page_size=page_size,
        start_time=start_time,
        end_time=end_time,
        sort_by=sort_by,
        sort_order=sort_order,
    )


# === User Endpoints ===


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_user_info(ctx: Context):
    """
    Returns a summary of the authenticated user's account.
    
    Includes user ID, email, full name, profile image, and referral code.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        user_module.me,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_user_feature_config(ctx: Context):
    """
    Returns any custom feature flags applied to the user.
    
    Shows experimental features and special configurations enabled for the account.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        user_module.feature_config,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_user_region(ctx: Context):
    """
    Returns the user's region and appropriate fleet-api base URL.
    
    Useful for determining the correct API endpoint based on the user's region.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        user_module.region,
        bearer_token=bearer_token,
    )


@tesla_tool(read_only=True, destructive=False, open_world=True, tags={"tesla_fleet_api"})
def get_user_orders(ctx: Context):
    """
    Returns the active orders for the user.
    
    Includes information about pending vehicle orders, upgrades, and purchases.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        user_module.orders,
        bearer_token=bearer_token,
    )


# === TeslaMate sub-servers (mounted with namespace="teslamate") ===

from .servers.teslamate_server import build_teslamate_server
from .servers.teslamate_apps import build_teslamate_apps_server

mcp.mount(build_teslamate_server(teslamate_module, app_csp=APP_CSP), namespace="teslamate")
mcp.mount(build_teslamate_apps_server(teslamate_module, app_csp=APP_CSP), namespace="teslamate")

# === Skills (markdown workflows the LLM reads on demand) ===
from fastmcp.server.providers.skills import SkillsDirectoryProvider

_SKILLS_DIR = Path(__file__).parent / "skills"
if _SKILLS_DIR.is_dir():
    mcp.add_provider(SkillsDirectoryProvider(_SKILLS_DIR))


# Also expose each skill as a tool. Anthropic's `mcp_servers` integration
# (and the OpenAI bridge) only see MCP *tools* — they ignore Resources, so
# the SkillsDirectoryProvider alone isn't reachable from API clients. Each
# tool returns the SKILL.md body so the LLM can follow the workflow when
# the user's intent matches.
def _register_skill_tools() -> None:
    import yaml as _yaml

    if not _SKILLS_DIR.is_dir():
        return
    for skill_dir in sorted(_SKILLS_DIR.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            raw = skill_md.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("[skills] cannot read %s: %s", skill_md, exc)
            continue
        front, _, body = _split_skill_frontmatter(raw)
        meta = _yaml.safe_load(front) if front else {}
        if not isinstance(meta, dict):
            meta = {}
        name = (meta.get("name") or skill_dir.name).strip()
        description = (meta.get("description") or "").strip()
        tool_name = f"skill_{name.replace('-', '_')}"
        skill_body = body.lstrip("\n")

        # Closure captures the body so each tool returns its own SKILL.md.
        def _make_handler(text: str):
            async def _skill_tool() -> str:
                """Return this skill's workflow markdown for the LLM to follow."""
                return text
            return _skill_tool

        handler = _make_handler(skill_body)
        handler.__name__ = tool_name
        mcp.tool(
            name=tool_name,
            description=description or f"Run the '{name}' skill workflow.",
            tags={"skill", "teslamate", "generative"},
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "openWorldHint": True,
            },
        )(handler)
        logger.info("[skills] registered tool %s", tool_name)


def _split_skill_frontmatter(text: str) -> tuple[str, str, str]:
    """Split `---\\n<yaml>\\n---\\n<body>` into (front, marker, body)."""
    if not text.startswith("---"):
        return "", "", text
    end = text.find("\n---", 3)
    if end == -1:
        return "", "", text
    front = text[3:end].strip()
    rest = text[end + 4:]
    return front, "---", rest


_register_skill_tools()

# === Generative UI (LLM-authored Prefab apps, sandboxed in Pyodide) ===
from fastmcp.apps.generative import GenerativeUI
from fastmcp.server.transforms import ToolTransform
from fastmcp.tools.tool_transform import ToolTransformConfig

mcp.add_provider(GenerativeUI())


# GenerativeUI registers `ui://prefab/generative.html` with mime
# `text/html;profile=mcp-app` (FastMCP Apps protocol). The OpenAI Apps SDK /
# ChatGPT only renders `text/html+skybridge`, so we expose a parallel resource
# with the Skybridge mime that pulls the same body from the underlying
# generator. The transform below points `openai/outputTemplate` at this
# alias.
_PREFAB_GENERATIVE_CSP = {
    "connectDomains": [
        _normalize_origin(os.environ.get("TESLA_OAUTH_BASE_URL"))
        or "https://mcp.myteslamate.com",
        "https://cdn.jsdelivr.net",
        "https://pypi.org",
        "https://files.pythonhosted.org",
    ],
    "resourceDomains": ["https://cdn.jsdelivr.net"],
}

PREFAB_GENERATIVE_WIDGET_META = {
    "ui": {
        "domain": _normalize_origin(os.environ.get("TESLA_OAUTH_BASE_URL"))
        or "https://mcp.myteslamate.com",
        "csp": _PREFAB_GENERATIVE_CSP,
    },
    "openai/widgetDescription": "Generative UI renderer for LLM-authored Prefab components.",
}


@mcp.resource(
    uri="ui://prefab/generative-skybridge.html",
    name="Prefab Generative Renderer (Skybridge)",
    mime_type="text/html+skybridge",
    meta=PREFAB_GENERATIVE_WIDGET_META,
)
async def prefab_generative_skybridge_widget() -> str:
    """Skybridge-mime mirror of FastMCP's Prefab generative renderer."""
    res = await mcp.get_resource("ui://prefab/generative.html")
    if res is None:
        return ""
    body = await res.read()
    contents = getattr(body, "contents", None) or []
    if not contents:
        return ""
    return getattr(contents[0], "content", "") or ""


_GENERATIVE_DESCRIPTION = """
Generate a custom interactive UI on demand for cases not covered by the
specialized teslamate_* / pv_follow_* tools.

Workflow:
1. Call `generative_search_prefab_components` whenever you're unsure of a component's
   args — it returns the exact keyword names and required fields.
2. Import only from `prefab_ui.app` and `prefab_ui.components(.charts)`.
   Everything is flat under `prefab_ui.components` — there is NO
   `navigation`, `forms`, or `layout` submodule.
3. Always wrap the tree in `with PrefabApp() as app:` (enables streaming).
   Components self-register when instantiated inside that block. There is
   NO `app.add(...)` method — calling it raises `AttributeError`. Just
   write the component statements directly, e.g.:

       with PrefabApp() as app:
           Heading(content="Title", level=2)        # ✓ auto-registered
           BarChart(data=rows, x_axis="date", ...)  # ✓ auto-registered

   NOT:
           app.add(Heading(...))                    # ✗ AttributeError
           app.children.append(...)                 # ✗ no such attribute
4. Pull data from `teslamate_get_*` tools first if the request is about
   the user's car. Pass it via the `data` argument; each KEY of `data`
   becomes a top-level global in the sandbox — NOT a single `data` variable.

   Example: you call with `data={"drives": [...], "car": {...}}`. In the
   sandbox you access them as `drives` and `car` directly:

       drives = globals().get("drives", [])
       car = globals().get("car", {})

   There is NO `data` variable in the sandbox. Writing `for d in data:`
   raises `NameError: name 'data' is not defined` and the call fails.

MANDATORY — Data references (this is the #1 performance rule):

Before writing any Python, scan the recent tool responses in this
conversation for `[data_ref=mtm:...]` banners. If you find one whose payload
you would otherwise paste into `data=` or inline inside the script, you MUST
pass it as a reference. Re-emitting the same JSON you just received is
NEVER an acceptable shortcut — it can blow the model's output budget by
50× and triggers a 30–60 s latency spike for the user.

Refs use SEMANTIC ids based on the source tool name — copy them
EXACTLY from the banner you just received. Examples of valid refs you
will see in banners:
    mtm:get_car_drives     (from teslamate_get_car_drives)
    mtm:get_car_charges    (from teslamate_get_car_charges)
    mtm:get_cars           (from teslamate_get_cars)
    mtm:get_car_status     (from teslamate_get_car_status)

DO NOT invent refs (`mtm:abc123`, `mtm:<random hex>`, `mtm:<uuid>`)
— those are not in the cache and the call will fail with
"data_ref not found". The ref ID is ALWAYS the bare tool name
with the `teslamate_` prefix stripped.

Two shapes accepted — pick based on how many sources you combine:

  Single source — PREFERRED when one `teslamate_get_*` gave everything:
      data={"__ref__": "mtm:get_car_drives"}    # or just data="mtm:get_car_drives"
    The resolved value is flattened: each key of the tool's inner result
    (e.g. `car`, `drives`, `units` from `teslamate_get_car_drives`)
    becomes its own global. Then in Python you write directly:
        drives = globals().get("drives", [])
        car = globals().get("car", {})

  Multiple sources — only when you genuinely merge outputs of several tools:
      data={
          "drives": "mtm:get_car_drives",       # from teslamate_get_car_drives
          "charges": "mtm:get_car_charges",     # from teslamate_get_car_charges
          "window_days": 7,                     # plain values pass through
      }
    The KEY (`drives`, `charges`) becomes the sandbox global. The server
    is smart about the value: if the resolved payload contains a top-level
    key matching the parent (e.g. parent `drives` and resolved has a
    `drives` field), it drills in — so `drives` global IS the drives list,
    not the wrapping dict. Other plain values pass through unchanged.

If you only need ONE tool's data, always pick single-source — it's the
cleanest mapping and the model has the smallest chance of structural
mistakes. Reserve multi-source for true cross-tool combination.

Anti-patterns that make the call hit the slow path:
  ✗ Pasting the JSON drives array into the code as a literal.
  ✗ Pasting it into `data={"drives": [{...}, {...}, ...]}` instead of using
    the ref.
  ✗ Calling a `teslamate_get_*` tool again to re-fetch data you already
    received this turn (the ref is still in cache).

Refs are session-scoped and expire after ~5 minutes. If a ref is missing
the call fails with a clear error telling you to re-fetch — handle that
gracefully by re-calling the source tool, then retrying with the new ref.

DO NOT import these — they look like common React names but are NOT
exported by `prefab_ui.components`. Importing them raises ImportError
and the call fails:
  Text         (use Markdown for prose, Heading for titles)
  Spacer       (use Div(css_class="h-4") or omit — Column/Grid have gap=)
  Note         (use Alert with variant="info" or AlertDescription)
  Hr, Divider  (use Separator)
  Box          (use Div or Container)
  Stack        (use Column for vertical, Row for horizontal)
  Flex         (use Row)
  Row, Col(umn) elements like HTML — Row/Column ARE valid components,
                but there is no `Col`. Use Column for vertical flex.

Required-field cheatsheet (forgetting these raises Pydantic "missing"):
  Heading(content=), Markdown(content=), Badge(label=),
  Metric(label=, value=), Progress(value=, max=),
  DataTableColumn(key=, header=), DataTable(columns=, rows=).

Chart components — IMPORT FROM A DIFFERENT SUBMODULE:
  from prefab_ui.components.charts import BarChart, LineChart, PieChart, Histogram, ChartSeries

The following WILL ImportError (charts are NOT re-exported from the main
components module):
  from prefab_ui.components import LineChart       # ✗ ImportError
  from prefab_ui.components import BarChart, ...   # ✗ ImportError

Exact chart signatures — the sandbox truncates Pydantic errors to a URL,
so getting these wrong leaves you blind. Do NOT improvise:

  ChartSeries(data_key="col", label="Drives", color="#3b82f6")
    # `data_key` is the column name (str). The legend label is `label`,
    # NOT `name`. `color` is optional.

  BarChart(data=rows, series=[ChartSeries(...)], x_axis="col",
           height=320, stacked=False, show_legend=True)
    # `x_axis` is a STRING — the column name. NEVER pass a dict.
    # `data` is a list[dict].

  LineChart / Histogram / PieChart: same `x_axis: str` rule as BarChart.

  Grid(columns=3, gap=4, children=[...])
    # `gap` is an INT (Tailwind spacing scale, 0–8). NOT "m"/"sm"/"lg".

  GridItem(col_span=2, row_span=1, children=[...])
    # All ints; defaults to 1×1.

If a component you need is not in this cheatsheet, call
`generative_search_prefab_components` BEFORE writing the code — never guess.
""".strip()


# Rename the canonical provider tools to the namespaced names ChatGPT learned,
# and tag them so subscription-filtering picks them up alongside teslamate UI.
mcp.add_transform(
    ToolTransform(
        {
            "generate_prefab_ui": ToolTransformConfig(
                name="generative_generate_prefab_ui",
                tags={"generative", "ui", "teslamate", "tesla_fleet_api"},
                description=_GENERATIVE_DESCRIPTION,
                # Replace meta entirely: keep the FastMCP `ui` block (for
                # native MCP-app clients) AND add `openai/outputTemplate` so
                # the OpenAI Apps SDK / ChatGPT picks up the Skybridge mirror.
                meta={
                    "openai/outputTemplate": "ui://prefab/generative-skybridge.html",
                    "ui": {
                        "resourceUri": "ui://prefab/generative.html",
                        "csp": _PREFAB_GENERATIVE_CSP,
                    },
                },
            ),
            "search_prefab_components": ToolTransformConfig(
                name="generative_search_prefab_components",
                tags={"generative", "ui", "teslamate", "tesla_fleet_api"},
            ),
        }
    )
)


class GenerativeLoggingMiddleware(Middleware):
    """Log Prefab code submitted to ``generative_generate_prefab_ui``.

    Always logs the submitted code so we can see what the LLM produced —
    useful both for failures (Pydantic errors, missing modules) and silent
    issues (chart not rendering, empty data). Set ``GENERATIVE_DEBUG=0``
    to disable success logging while keeping error logging.
    """

    _GENERATIVE_TOOL = "generative_generate_prefab_ui"
    _LOG_SUCCESS = os.environ.get("GENERATIVE_DEBUG", "1") != "0"

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool_name = getattr(context.message, "name", None)
        try:
            result = await call_next(context)
        except Exception as exc:
            if tool_name == self._GENERATIVE_TOOL:
                args = getattr(context.message, "arguments", None) or {}
                code = args.get("code", "")
                logger.error(
                    "[generative] FAILED — full error and submitted code below\n"
                    "----- error -----\n%s\n"
                    "----- code (%d chars) -----\n%s\n"
                    "----- end -----",
                    exc,
                    len(code),
                    code,
                )
            raise

        if tool_name == self._GENERATIVE_TOOL and self._LOG_SUCCESS:
            args = getattr(context.message, "arguments", None) or {}
            code = args.get("code", "")
            data = args.get("data")
            data_repr = (
                f"keys={list(data.keys())}"
                if isinstance(data, dict)
                else f"type={type(data).__name__}"
                if data is not None
                else "None"
            )
            logger.info(
                "[generative] OK — code (%d chars), data %s\n----- code -----\n%s\n----- end -----",
                len(code),
                data_repr,
                code,
            )
        return result


mcp.add_middleware(GenerativeLoggingMiddleware())


# === Data reference cache: avoid the LLM re-emitting tool JSON when calling
# `generative_generate_prefab_ui`. Each non-generative tool result is cached
# server-side under a short opaque ref; the response is annotated with a
# `[data_ref=mtm:...]` banner so the LLM can pass `data={"__ref__": "..."}`
# back in the generative call instead of copying the full payload.
import json as _json
import time as _time
import uuid as _uuid
from collections import OrderedDict as _OrderedDict
from threading import Lock as _Lock

from fastmcp.exceptions import ToolError as _DataRefToolError
from mcp.types import TextContent as _DataRefTextContent  # noqa: F401

_DATA_REF_PREFIX = "mtm:"
_DATA_REF_TTL = int(os.environ.get("GENERATIVE_DATA_REF_TTL", "300"))
_DATA_REF_MAXSIZE = int(os.environ.get("GENERATIVE_DATA_REF_MAXSIZE", "512"))
_DATA_REF_MAX_PAYLOAD = int(os.environ.get("GENERATIVE_DATA_REF_MAX_PAYLOAD", "5000000"))


class _DataRefCache:
    """Tiny TTL+LRU cache for tool result payloads, scoped per session key."""

    def __init__(self, maxsize: int, ttl: int) -> None:
        self._maxsize = maxsize
        self._ttl = ttl
        self._store: "_OrderedDict[tuple[str, str], tuple[float, str]]" = _OrderedDict()
        self._lock = _Lock()

    def _purge_locked(self, now: float) -> None:
        # Evict expired entries (cheap walk; small N).
        expired = [k for k, (ts, _) in self._store.items() if now - ts > self._ttl]
        for k in expired:
            self._store.pop(k, None)

    def put(self, session_key: str, payload: str, ref_id: str | None = None) -> str:
        """Cache `payload` under (session_key, ref_id) and return the full
        `mtm:<ref_id>` handle. When `ref_id` is None, falls back to a
        random 12-char hex — used for tools we don't have a semantic name
        for. Semantic IDs (e.g. ref_id="drives") let the LLM copy short
        readable words instead of random hex, which it routinely hallucinates.
        """
        if not ref_id:
            ref_id = _uuid.uuid4().hex[:12]
        now = _time.monotonic()
        with self._lock:
            self._purge_locked(now)
            # Move to end (LRU touch) — handles the overwrite case for
            # semantic IDs cleanly.
            self._store.pop((session_key, ref_id), None)
            self._store[(session_key, ref_id)] = (now, payload)
            while len(self._store) > self._maxsize:
                self._store.popitem(last=False)
        return f"{_DATA_REF_PREFIX}{ref_id}"

    def get(self, session_key: str, ref: str) -> str | None:
        if not ref.startswith(_DATA_REF_PREFIX):
            return None
        ref_id = ref[len(_DATA_REF_PREFIX):]
        now = _time.monotonic()
        with self._lock:
            entry = self._store.get((session_key, ref_id))
            if entry is None:
                return None
            ts, payload = entry
            if now - ts > self._ttl:
                self._store.pop((session_key, ref_id), None)
                return None
            # Touch for LRU recency.
            self._store.move_to_end((session_key, ref_id))
            return payload


_data_ref_cache = _DataRefCache(maxsize=_DATA_REF_MAXSIZE, ttl=_DATA_REF_TTL)


def _data_ref_session_key(context: MiddlewareContext) -> str | None:
    """Derive a per-user/per-session namespace so refs never leak across users.

    Tries in order:
      1. `access_token.claims.sub` — preferred if the verifier sets it
      2. `access_token.client_id` — second-best stable per-user id
      3. `mtm_token` claim — what TeslaTokenVerifier stores (per-user)
      4. `mcp-session-id` header — per-transport session
      5. Authorization header hash — last-resort per-bearer fallback
    Returning `None` here disables ref caching for the request entirely.
    """
    import hashlib as _hashlib

    try:
        request = context.fastmcp_context.request_context.request
    except AttributeError:
        return None
    if request is None:
        return None

    user = getattr(request, "user", None)
    token = getattr(user, "access_token", None) if user is not None else None
    if token is not None:
        claims = getattr(token, "claims", None) or {}
        for key in ("sub", "mtm_token"):
            val = claims.get(key) if hasattr(claims, "get") else None
            if val:
                return f"u:{key}:{_hashlib.sha1(str(val).encode()).hexdigest()[:16]}"
        client_id = getattr(token, "client_id", None)
        if client_id and client_id != "cached":
            return f"c:{client_id}"

    headers = getattr(request, "headers", None)
    if headers is not None:
        sid = headers.get("mcp-session-id") or headers.get("Mcp-Session-Id")
        if sid:
            return f"s:{sid}"
        auth = headers.get("authorization") or headers.get("Authorization")
        if auth:
            return f"a:{_hashlib.sha1(auth.encode()).hexdigest()[:16]}"
    return None


# Sentinel that says "leave args['data'] untouched" — distinguishes from
# `None` (which is a legitimate resolved value when the model passed nothing).
_UNCHANGED: object = object()


def _unwrap_data_envelope(value: object) -> object:
    """Strip the `{"data": X}` outer envelope that FastMCP wraps around dict
    tool results. Without this, a ref resolved from `teslamate_get_car_drives`
    would inject a `data` global that wraps `{"car": ..., "drives": [...]}` —
    forcing the model to remember an extra unwrap step. With this, the global
    structure matches what you'd get from inline `data={"drives": [...]}`.
    """
    if (
        isinstance(value, dict)
        and len(value) == 1
        and "data" in value
        and isinstance(value["data"], dict)
    ):
        return value["data"]
    return value


def _smart_extract_by_key(parent_key: str, value: object) -> object:
    """In multi-ref form `data={"drives": "mtm:..."}` the model's intent is
    almost always "the global named `drives` should be the drives list".
    But the cached payload of a `teslamate_get_*` tool is an inner dict like
    `{"car": {...}, "drives": [...], "units": {...}}`. If the parent key
    (`drives`) matches a key in that dict, drill into it so the global
    ends up as the value the model expected.

    Bypassed when the parent key doesn't match — the model gets the full
    structure to navigate manually.
    """
    if isinstance(value, dict) and parent_key in value:
        return value[parent_key]
    return value


def _extract_data_ref(data: object) -> str | None:
    if isinstance(data, str) and data.startswith(_DATA_REF_PREFIX):
        return data
    if isinstance(data, dict) and len(data) == 1:
        v = data.get("__ref__")
        if isinstance(v, str) and v.startswith(_DATA_REF_PREFIX):
            return v
    return None


def _maybe_decode_json_arg(value: object) -> object:
    """Some providers (notably DeepSeek) occasionally encode object-shaped
    function arguments as JSON strings instead of native objects. Normalise
    here so downstream ref-resolution and shape checks see the intended dict.
    """
    if not isinstance(value, str):
        return value
    s = value.strip()
    if not s or s[0] not in ("{", "["):
        return value
    try:
        return _json.loads(s)
    except (TypeError, ValueError):
        return value


class DataRefMiddleware(Middleware):
    """Cache non-generative tool outputs + resolve refs for the generative tool.

    - Pre-call: if the generative tool was invoked with `data={"__ref__": "mtm:..."}`
      (or `data="mtm:..."`), look up the cached payload and substitute it as
      the real `data` dict before forwarding. The LLM never has to re-emit
      the JSON.
    - Post-call: for any data tool (non-generative AND non-UI-render), store
      the textual result and append a separate `[data_ref=mtm:...]` content
      block so the LLM sees a handle it can pass to a later generative call.
      The banner is a NEW content block — `content[0].text` is left intact so
      backend clients can still `json_decode` it (most data tools return JSON
      via FastMCP's standard serializer).
    """

    _GENERATIVE_TOOLS = {
        "generative_generate_prefab_ui",
        "generative_search_prefab_components",
    }
    _BANNER_PREFIX = "[data_ref="

    def _resolve_data_refs(
        self,
        data: object,
        session_key: str | None,
    ) -> tuple[object, list[str]]:
        """Resolve any data_ref(s) embedded in the `data` argument.

        Three shapes accepted from the model:
          1. data="mtm:abc"                 → resolve, replace whole `data`
          2. data={"__ref__": "mtm:abc"}    → same as (1)
          3. data={"drives": "mtm:abc", "charges": "mtm:def", "metadata": {...}}
             → per-key resolution: each value that looks like a ref gets
               replaced with the cached payload; other values pass through.

        Returns `(resolved, missing_refs)`. `resolved` is `_UNCHANGED` when no
        refs were present (caller should leave the arg as-is). When any ref
        is missing/expired, `missing_refs` is populated and the caller should
        surface an `isError` result instead of running the tool.
        """
        # Unwrap JSON-string args (e.g. DeepSeek encoding `{"__ref__":"mtm:..."}`
        # as a string literal). This lets the rest of the resolver treat it as
        # the dict the model intended.
        decoded = _maybe_decode_json_arg(data)
        json_unwrapped = decoded is not data
        data = decoded

        # Shape (1) and (2): whole-data ref.
        whole_ref = _extract_data_ref(data)
        if whole_ref:
            cached = _data_ref_cache.get(session_key, whole_ref) if session_key else None
            if cached is None:
                return _UNCHANGED, [whole_ref]
            try:
                parsed = _json.loads(cached)
            except (TypeError, ValueError):
                logger.info("[data_ref] resolved %s as raw text (%d chars)", whole_ref, len(cached))
                return cached, []
            parsed = _unwrap_data_envelope(parsed)
            logger.info("[data_ref] resolved %s (%d chars)", whole_ref, len(cached))
            return parsed, []

        # Shape (3): per-key refs in a dict.
        if isinstance(data, dict):
            missing: list[str] = []
            resolved_dict: dict[str, object] = {}
            changed = False
            for key, value in data.items():
                if isinstance(value, str) and value.startswith(_DATA_REF_PREFIX):
                    changed = True
                    cached = _data_ref_cache.get(session_key, value) if session_key else None
                    if cached is None:
                        missing.append(value)
                        continue
                    try:
                        parsed = _json.loads(cached)
                    except (TypeError, ValueError):
                        resolved_dict[key] = cached
                    else:
                        # Two-step normalisation so multi-ref maps cleanly
                        # onto the model's intent:
                        #   1. Strip the `{"data": X}` FastMCP envelope.
                        #   2. If the parent key matches a key inside the
                        #      inner dict (e.g. parent "drives" + inner
                        #      `{"car":..,"drives":[...],"units":..}`),
                        #      drill into it. Result: `drives` global is
                        #      the actual drives list.
                        parsed = _unwrap_data_envelope(parsed)
                        parsed = _smart_extract_by_key(key, parsed)
                        resolved_dict[key] = parsed
                    logger.info(
                        "[data_ref] resolved %s into key '%s' (%d chars)",
                        value, key, len(cached),
                    )
                else:
                    resolved_dict[key] = value
            if missing:
                return _UNCHANGED, missing
            if changed:
                return resolved_dict, []

        # No refs to resolve, but we decoded a JSON-string arg — return the
        # decoded value so the caller can replace the original string with
        # the native object the tool's schema expects.
        if json_unwrapped:
            return data, []

        return _UNCHANGED, []

    @staticmethod
    def _semantic_ref_id(tool_name: str) -> str:
        """Map a tool name to a short, memorable cache key that the LLM
        can copy reliably. Strips known prefixes and namespace separators.
        Example: 'teslamate.get_car_drives' → 'get_car_drives'.
        """
        n = tool_name or ""
        # Drop the namespace prefix added by `mcp.mount(..., namespace=...)`.
        for sep in (".", "/", ":"):
            if sep in n:
                n = n.split(sep, 1)[1]
        # Drop the conventional `teslamate_` prefix for brevity.
        if n.startswith("teslamate_"):
            n = n[len("teslamate_"):]
        # Defensive: keep only chars the LLM can copy without confusion.
        return "".join(c for c in n if c.isalnum() or c == "_") or "data"

    @staticmethod
    def _is_ui_render_tool(name: str | None) -> bool:
        """UI-rendering tools already return a PrefabApp tree — their output
        is consumed for direct mounting, not as data for a subsequent
        generative call. No banner needed."""
        if not name:
            return False
        if name == "teslamate_dashboard":
            return True
        return (
            name.endswith("_chart")
            or name.endswith("_table")
            or name.endswith("_card")
        )

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        tool_name = getattr(context.message, "name", None)
        session_key = _data_ref_session_key(context)
        # Diagnostic — emit at INFO so we can confirm the middleware sees
        # data-fetch tool calls and what session_key was resolved to.
        logger.info(
            "[data_ref] middleware on_call_tool: name=%r session_key=%r",
            tool_name, session_key,
        )

        # Pre-call: resolve any data_ref into the real `data` payload.
        if tool_name == "generative_generate_prefab_ui":
            args = getattr(context.message, "arguments", None)
            if isinstance(args, dict):
                resolved, missing = self._resolve_data_refs(
                    args.get("data"), session_key,
                )
                if missing:
                    logger.warning(
                        "[data_ref] miss for %s — raising ToolError",
                        missing,
                    )
                    raise _DataRefToolError(
                        f"data_ref(s) expired or not found: {missing}. "
                        "Re-fetch the source data with the original tool, "
                        "then call generative_generate_prefab_ui again "
                        "passing the data inline (data={...})."
                    )
                if resolved is not _UNCHANGED:
                    args["data"] = resolved

        result = await call_next(context)

        # Post-call: cache data-tool results and append a banner content block.
        # Skip generative tools (they don't produce reusable data) and skip
        # UI-render tools (their output is a PrefabApp tree the client mounts
        # directly — banner would only confuse the LLM into re-passing it).
        if (
            tool_name
            and tool_name not in self._GENERATIVE_TOOLS
            and not self._is_ui_render_tool(tool_name)
            and not session_key
        ):
            logger.warning(
                "[data_ref] no session_key for tool %s — banner skipped, "
                "LLM will likely hallucinate refs",
                tool_name,
            )
        if (
            tool_name
            and tool_name not in self._GENERATIVE_TOOLS
            and not self._is_ui_render_tool(tool_name)
            and session_key
        ):
            content = getattr(result, "content", None) or []
            if content:
                first = content[0]
                text = getattr(first, "text", None)
                already_bannered = any(
                    isinstance(getattr(b, "text", None), str)
                    and b.text.startswith(self._BANNER_PREFIX)
                    for b in content
                )
                if (
                    isinstance(text, str)
                    and text
                    and len(text) <= _DATA_REF_MAX_PAYLOAD
                    and not already_bannered
                ):
                    # Use a semantic ref ID derived from the tool name —
                    # LLMs reliably copy short readable strings, they
                    # routinely hallucinate long random hex.
                    semantic_id = self._semantic_ref_id(tool_name)
                    ref = _data_ref_cache.put(session_key, text, ref_id=semantic_id)
                    new_content = list(content)
                    new_content.append(_DataRefTextContent(
                        type="text",
                        text=f"{self._BANNER_PREFIX}{ref}]",
                    ))
                    result.content = new_content
                    logger.info(
                        "[data_ref] put for tool %s → %s (%d chars cached, %d content blocks now)",
                        tool_name, ref, len(text), len(new_content),
                    )
                else:
                    logger.info(
                        "[data_ref] put skipped for %s — text_kind=%s len=%d bannered=%s max=%d",
                        tool_name, type(text).__name__,
                        len(text) if isinstance(text, str) else -1,
                        already_bannered, _DATA_REF_MAX_PAYLOAD,
                    )
            else:
                logger.info(
                    "[data_ref] put skipped for %s — no content blocks",
                    tool_name,
                )

        return result


mcp.add_middleware(DataRefMiddleware())


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "healthy", "service": "mcp-server"})


@mcp.custom_route("/.well-known/openai-apps-challenge", methods=["GET"])
async def openai_apps_challenge(request):
    return PlainTextResponse(openai_apps_challenge_token)


# a middleware to filter tools based on subscription flags and "tags" query parameter
_SUBSCRIPTION_TAGS = {"tesla_fleet_api", "teslamate"}


class TagFilteringMiddleware(Middleware):
    async def on_list_tools(self, context: MiddlewareContext, call_next):
        result = await call_next(context)

        request = context.fastmcp_context.request_context.request

        # Filter by subscription flags from OAuth claims (OAuth mode only).
        # A tool is dropped only if every subscription tag it carries is
        # forbidden — so a tool tagged with BOTH `teslamate` and
        # `tesla_fleet_api` survives as long as the user has either
        # subscription. Tools without any subscription tag are always kept.
        forbidden_tags: set[str] = set()
        user = getattr(request, "user", None)
        if user and hasattr(user, "access_token"):
            claims = user.access_token.claims
            if not claims.get("subscribe_api", False):
                forbidden_tags.add("tesla_fleet_api")
            if not claims.get("subscribe_teslamate", False):
                forbidden_tags.add("teslamate")
        if forbidden_tags:
            def _allowed(tool):
                gating = tool.tags & _SUBSCRIPTION_TAGS
                if not gating:
                    return True
                return not gating.issubset(forbidden_tags)
            result = [tool for tool in result if _allowed(tool)]

        # Filter by explicit "tags" query parameter
        tags = request.query_params.getlist("tags")
        if not tags: # no tags specified, return all (subscription-filtered) tools
            return result
        if len(tags) == 1 and "," in tags[0]: # if a single tag with multiple values is provided, ex: tags=red,blue
            tags = set(tags[0].split(","))
        else:
            tags = set(tags)

        return [tool for tool in result if bool(tool.tags & tags)] # if the tool's tags intersect with the requested tags

mcp.add_middleware(TagFilteringMiddleware()) # add the middleware to the FastMCP app

if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=mcp_port)
else:
    app = mcp.http_app()
