from __future__ import annotations

import logging
from typing import List, Optional

from mcp.server.fastmcp import Context, FastMCP


from .base import TeslaClient, TeslaAPIError

from .modules import VehicleEndpoints, VehicleCommandsModule, EnergyModule, ChargingModule, UserModule

from starlette.responses import JSONResponse

import os


logging.basicConfig(level=logging.INFO)

mcp_port = int(os.environ.get("PORT", 8084))
mcp = FastMCP("Tesla Vehicle MCP", port=mcp_port)
client = TeslaClient()
vehicle_module = VehicleEndpoints(client)
commands_module = VehicleCommandsModule(client)
energy_module = EnergyModule(client)
charging_module = ChargingModule(client)
user_module = UserModule(client)


def _extract_bearer_token(ctx: Context) -> str:
    """Extract bearer token from MCP request headers."""
    # Access the underlying Starlette request from the session
    request = ctx.request_context.request
    if hasattr(request, "headers"):
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]  # Strip "Bearer " prefix
    raise RuntimeError("No Authorization header found in MCP request")


def _execute(handler, **kwargs):
    try:
        return handler(**kwargs)
    except TeslaAPIError as exc:  # pragma: no cover - tool surface
        logging.getLogger("tesla_mcp").error("Tesla API error: %s", exc)
        status = f" (status {exc.status_code})" if exc.status_code else ""
        raise RuntimeError(f"Tesla API error{status}: {exc}") from exc

@mcp.tool()
def list_vehicles_and_energy_sites(ctx: Context):
    """Return the vehicles and energy sites available to the authenticated account."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(vehicle_module.products, bearer_token=bearer_token)

@mcp.tool()
def get_vehicle(vehicle_tag: str, ctx: Context):
    """Fetch detailed metadata for a vehicle."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_vehicle,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@mcp.tool()
def get_vehicle_data(vehicle_tag: str, ctx: Context):
    """Fetch live vehicle data (location, climate, charge, etc.)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_vehicle_data,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@mcp.tool()
def wake_up_vehicle(vehicle_tag: str, ctx: Context):
    """Wake a sleeping vehicle."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.wake_up_vehicle,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@mcp.tool()
def get_mobile_enabled(vehicle_tag: str, ctx: Context):
    """Check if the vehicle allows mobile access."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_mobile_enabled,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@mcp.tool()
def get_nearby_charging_sites(vehicle_tag: str, ctx: Context):
    """List charging sites close to the vehicle."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_nearby_charging_sites,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@mcp.tool()
def get_service_data(vehicle_tag: str, ctx: Context):
    """Retrieve service-related data for the vehicle."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_service_data,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@mcp.tool()
def get_release_notes(vehicle_tag: str, ctx: Context):
    """Return the latest firmware release notes."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_release_notes,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@mcp.tool()
def get_recent_alerts(vehicle_tag: str, ctx: Context):
    """Return recent vehicle alerts."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_recent_alerts,
        vehicle_tag=vehicle_tag,
        bearer_token=bearer_token,
    )


@mcp.tool()
def get_fleet_status(vins: List[str], ctx: Context):
    """Return fleet status details for the provided VINs."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_fleet_status,
        vins=vins,
        bearer_token=bearer_token,
    )


@mcp.tool()
def get_vehicle_options(vin: str, ctx: Context):
    """Return option codes for a VIN."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_vehicle_options,
        vin=vin,
        bearer_token=bearer_token,
    )


@mcp.tool()
def get_eligible_upgrades(vin: str, ctx: Context):
    """Return upgrades available for a VIN."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_eligible_upgrades,
        vin=vin,
        bearer_token=bearer_token,
    )


@mcp.tool()
def get_eligible_subscriptions(vin: str, ctx: Context):
    """Return subscription offers for a VIN."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_eligible_subscriptions,
        vin=vin,
        bearer_token=bearer_token,
    )


# === Drivers & Sharing ===


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
def set_subscriptions(vehicle_ids: List[int], device_token: str, ctx: Context):
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


@mcp.tool()
def get_vehicle_subscriptions(ctx: Context):
    """
    Returns the list of vehicles for which this mobile device currently subscribes to push notifications.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        vehicle_module.get_vehicle_subscriptions,
        bearer_token=bearer_token,
    )


@mcp.tool()
def set_vehicle_subscriptions(vehicle_ids: List[int], ctx: Context):
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


@mcp.tool()
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


@mcp.tool()
def door_lock(ctx: Context, vehicle_tag: str):
    """Lock the vehicle doors."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.door_lock, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def door_unlock(ctx: Context, vehicle_tag: str):
    """Unlock the vehicle doors."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.door_unlock, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
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


@mcp.tool()
def auto_conditioning_start(ctx: Context, vehicle_tag: str):
    """Start climate preconditioning."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.auto_conditioning_start, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def auto_conditioning_stop(ctx: Context, vehicle_tag: str):
    """Stop climate preconditioning."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.auto_conditioning_stop, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
def set_bioweapon_mode(ctx: Context, vehicle_tag: str, on: bool):
    """Enable/disable Bioweapon Defense Mode."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.set_bioweapon_mode, vehicle_tag=vehicle_tag, on=on, bearer_token=bearer_token)


@mcp.tool()
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


@mcp.tool()
def set_cop_temp(ctx: Context, vehicle_tag: str, cop_level: int):
    """
    Set cabin overheat protection temperature.
    
    Args:
        cop_level: 0=Low (90F/30C), 1=Medium (95F/35C), 2=High (100F/40C)
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.set_cop_temp, vehicle_tag=vehicle_tag, cop_level=cop_level, bearer_token=bearer_token)


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
def remote_steering_wheel_heater_request(ctx: Context, vehicle_tag: str, on: bool):
    """Enable/disable steering wheel heater."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.remote_steering_wheel_heater_request, vehicle_tag=vehicle_tag, on=on, bearer_token=bearer_token
    )


@mcp.tool()
def remote_steering_wheel_heat_level_request(ctx: Context, vehicle_tag: str, level: int):
    """Set steering wheel heat level."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.remote_steering_wheel_heat_level_request,
        vehicle_tag=vehicle_tag,
        level=level,
        bearer_token=bearer_token,
    )


@mcp.tool()
def remote_auto_steering_wheel_heat_climate_request(ctx: Context, vehicle_tag: str, on: bool):
    """Enable/disable automatic steering wheel heating."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.remote_auto_steering_wheel_heat_climate_request,
        vehicle_tag=vehicle_tag,
        on=on,
        bearer_token=bearer_token,
    )


@mcp.tool()
def charge_start(ctx: Context, vehicle_tag: str):
    """Start charging."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.charge_start, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def charge_stop(ctx: Context, vehicle_tag: str):
    """Stop charging."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.charge_stop, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def charge_port_door_open(ctx: Context, vehicle_tag: str):
    """Open charge port door."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.charge_port_door_open, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def charge_port_door_close(ctx: Context, vehicle_tag: str):
    """Close charge port door."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.charge_port_door_close, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def set_charge_limit(ctx: Context, vehicle_tag: str, percent: int):
    """Set charge limit percentage (50-100)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.set_charge_limit, vehicle_tag=vehicle_tag, percent=percent, bearer_token=bearer_token
    )


@mcp.tool()
def charge_standard(ctx: Context, vehicle_tag: str):
    """Set charge mode to standard range."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.charge_standard, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def charge_max_range(ctx: Context, vehicle_tag: str):
    """Set charge mode to max range."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.charge_max_range, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def set_charging_amps(ctx: Context, vehicle_tag: str, charging_amps: int):
    """Set charging amperage."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.set_charging_amps, vehicle_tag=vehicle_tag, charging_amps=charging_amps, bearer_token=bearer_token
    )


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
def remove_charge_schedule(ctx: Context, vehicle_tag: str, schedule_id: int):
    """Remove a charge schedule by ID."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.remove_charge_schedule, vehicle_tag=vehicle_tag, schedule_id=schedule_id, bearer_token=bearer_token
    )


@mcp.tool()
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


@mcp.tool()
def remove_precondition_schedule(ctx: Context, vehicle_tag: str, schedule_id: int):
    """Remove a precondition schedule by ID."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.remove_precondition_schedule,
        vehicle_tag=vehicle_tag,
        schedule_id=schedule_id,
        bearer_token=bearer_token,
    )


@mcp.tool()
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


@mcp.tool()
def sun_roof_control(ctx: Context, vehicle_tag: str, state: str):
    """
    Control sunroof.
    
    Args:
        state: "stop", "close", or "vent"
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.sun_roof_control, vehicle_tag=vehicle_tag, state=state, bearer_token=bearer_token)


@mcp.tool()
def flash_lights(ctx: Context, vehicle_tag: str):
    """Flash the headlights."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.flash_lights, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def honk_horn(ctx: Context, vehicle_tag: str):
    """Honk the horn."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.honk_horn, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def adjust_volume(ctx: Context, vehicle_tag: str, volume: float):
    """Adjust media volume (0.0-10.0)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.adjust_volume, vehicle_tag=vehicle_tag, volume=volume, bearer_token=bearer_token)


@mcp.tool()
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

@mcp.tool()
def set_sentry_mode(ctx: Context, vehicle_tag: str, on: bool):
    """Enable/disable Sentry Mode."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.set_sentry_mode, vehicle_tag=vehicle_tag, on=on, bearer_token=bearer_token)


@mcp.tool()
def set_valet_mode(ctx: Context, vehicle_tag: str, on: bool, password: str):
    """Enable/disable Valet Mode with 4-digit PIN."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.set_valet_mode, vehicle_tag=vehicle_tag, on=on, password=password, bearer_token=bearer_token
    )


@mcp.tool()
def reset_valet_pin(ctx: Context, vehicle_tag: str):
    """Remove Valet Mode PIN."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.reset_valet_pin, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def speed_limit_set_limit(ctx: Context, vehicle_tag: str, limit_mph: float):
    """Set speed limit (mph)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.speed_limit_set_limit, vehicle_tag=vehicle_tag, limit_mph=limit_mph, bearer_token=bearer_token
    )


@mcp.tool()
def speed_limit_activate(ctx: Context, vehicle_tag: str, pin: str):
    """Activate Speed Limit Mode with 4-digit PIN."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.speed_limit_activate, vehicle_tag=vehicle_tag, pin=pin, bearer_token=bearer_token)


@mcp.tool()
def speed_limit_deactivate(ctx: Context, vehicle_tag: str, pin: str):
    """Deactivate Speed Limit Mode."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.speed_limit_deactivate, vehicle_tag=vehicle_tag, pin=pin, bearer_token=bearer_token)


@mcp.tool()
def speed_limit_clear_pin(ctx: Context, vehicle_tag: str, pin: str):
    """Clear Speed Limit Mode PIN."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.speed_limit_clear_pin, vehicle_tag=vehicle_tag, pin=pin, bearer_token=bearer_token)


@mcp.tool()
def speed_limit_clear_pin_admin(ctx: Context, vehicle_tag: str):
    """Clear Speed Limit Mode PIN (admin/owner only, firmware 2023.38+)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.speed_limit_clear_pin_admin, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def set_pin_to_drive(ctx: Context, vehicle_tag: str, on: bool, password: str):
    """Set PIN to Drive."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.set_pin_to_drive, vehicle_tag=vehicle_tag, on=on, password=password, bearer_token=bearer_token
    )


@mcp.tool()
def reset_pin_to_drive_pin(ctx: Context, vehicle_tag: str):
    """Reset PIN to Drive."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.reset_pin_to_drive_pin, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def clear_pin_to_drive_admin(ctx: Context, vehicle_tag: str):
    """Clear PIN to Drive (admin/owner only, firmware 2023.44+)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.clear_pin_to_drive_admin, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def schedule_software_update(ctx: Context, vehicle_tag: str, offset_sec: int):
    """Schedule OTA software update."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.schedule_software_update, vehicle_tag=vehicle_tag, offset_sec=offset_sec, bearer_token=bearer_token
    )


@mcp.tool()
def cancel_software_update(ctx: Context, vehicle_tag: str):
    """Cancel scheduled software update."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.cancel_software_update, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def remote_start_drive(ctx: Context, vehicle_tag: str):
    """Start vehicle remotely (keyless driving must be enabled)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.remote_start_drive, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


@mcp.tool()
def trigger_homelink(ctx: Context, vehicle_tag: str, lat: float, lon: float):
    """Trigger HomeLink (garage door opener)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.trigger_homelink, vehicle_tag=vehicle_tag, lat=lat, lon=lon, bearer_token=bearer_token
    )


@mcp.tool()
def remote_boombox(ctx: Context, vehicle_tag: str, sound: int):
    """
    Play sound through external speaker.
    
    Args:
        sound: 0=random fart, 2000=locate ping
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.remote_boombox, vehicle_tag=vehicle_tag, sound=sound, bearer_token=bearer_token)


@mcp.tool()
def set_vehicle_name(ctx: Context, vehicle_tag: str, vehicle_name: str):
    """Change vehicle name (requires Vehicle Command Protocol)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(
        commands_module.set_vehicle_name, vehicle_tag=vehicle_tag, vehicle_name=vehicle_name, bearer_token=bearer_token
    )


@mcp.tool()
def guest_mode(ctx: Context, vehicle_tag: str, on: bool):
    """Enable/disable Guest Mode."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.guest_mode, vehicle_tag=vehicle_tag, on=on, bearer_token=bearer_token)


@mcp.tool()
def erase_user_data(ctx: Context, vehicle_tag: str):
    """Erase user data from UI (must be parked and in Guest Mode)."""
    bearer_token = _extract_bearer_token(ctx)
    return _execute(commands_module.erase_user_data, vehicle_tag=vehicle_tag, bearer_token=bearer_token)


# === Energy Sites ===


@mcp.tool()
def energy_site_info(ctx: Context, energy_site_id: str):
    """
    Returns information about the energy site.
    
    Includes assets (solar, battery), settings (backup reserve), and features (storm_mode_capable).
    Power values are in watts. Energy values are in watt hours.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(energy_module.site_info, energy_site_id=energy_site_id, bearer_token=bearer_token)


@mcp.tool()
def energy_live_status(ctx: Context, energy_site_id: str):
    """
    Returns the live status of the energy site.
    
    Includes power (watts), state of energy (watt hours), grid status, and storm mode.
    """
    bearer_token = _extract_bearer_token(ctx)
    return _execute(energy_module.live_status, energy_site_id=energy_site_id, bearer_token=bearer_token)


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
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

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "healthy", "service": "mcp-server"})

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
else:
    app = mcp.streamable_http_app()