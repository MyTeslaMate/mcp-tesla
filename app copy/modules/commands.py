"""Vehicle commands module for Tesla MCP."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..base import TeslaClient, TeslaModule, TeslaRequestContext


class VehicleCommandsModule(TeslaModule):
    """Vehicle command endpoints for controlling Tesla vehicles."""

    def __init__(self, client: TeslaClient):
        super().__init__(client)

    def _command(
        self,
        vehicle_tag: str,
        command: str,
        *,
        bearer_token: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute a vehicle command."""
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag, f"command/{command}")
        res = self.client.post(endpoint, context=context, json=payload or {})
        return res['response'] if 'response' in res else res

    # === Doors, Locks & Access ===

    def door_lock(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Lock the vehicle doors."""
        return self._command(vehicle_tag, "door_lock", bearer_token=bearer_token)

    def door_unlock(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Unlock the vehicle doors."""
        return self._command(vehicle_tag, "door_unlock", bearer_token=bearer_token)

    def actuate_trunk(
        self, vehicle_tag: str, *, which_trunk: str, bearer_token: str
    ) -> Dict[str, Any]:
        """
        Open/close the front or rear trunk.
        
        Args:
            which_trunk: "front" or "rear"
        """
        return self._command(
            vehicle_tag, "actuate_trunk", bearer_token=bearer_token, payload={"which_trunk": which_trunk}
        )

    # === Climate Control ===

    def auto_conditioning_start(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Start climate preconditioning."""
        return self._command(vehicle_tag, "auto_conditioning_start", bearer_token=bearer_token)

    def auto_conditioning_stop(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Stop climate preconditioning."""
        return self._command(vehicle_tag, "auto_conditioning_stop", bearer_token=bearer_token)

    def set_temps(
        self,
        vehicle_tag: str,
        *,
        driver_temp: Optional[float] = None,
        passenger_temp: Optional[float] = None,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """
        Set cabin temperature (Celsius).
        
        Args:
            driver_temp: Driver-side temperature
            passenger_temp: Passenger-side temperature (if None, syncs with driver)
        """
        payload = {}
        if driver_temp is not None:
            payload["driver_temp"] = driver_temp
        if passenger_temp is not None:
            payload["passenger_temp"] = passenger_temp
        return self._command(vehicle_tag, "set_temps", bearer_token=bearer_token, payload=payload)

    def set_climate_keeper_mode(
        self, vehicle_tag: str, *, climate_keeper_mode: int, bearer_token: str
    ) -> Dict[str, Any]:
        """
        Set climate keeper mode.
        
        Args:
            climate_keeper_mode: 0=Off, 1=Keep, 2=Dog, 3=Camp
        """
        return self._command(
            vehicle_tag,
            "set_climate_keeper_mode",
            bearer_token=bearer_token,
            payload={"climate_keeper_mode": climate_keeper_mode},
        )

    def set_bioweapon_mode(self, vehicle_tag: str, *, on: bool, bearer_token: str) -> Dict[str, Any]:
        """Enable/disable Bioweapon Defense Mode."""
        return self._command(vehicle_tag, "set_bioweapon_mode", bearer_token=bearer_token, payload={"on": on})

    def set_cabin_overheat_protection(
        self, vehicle_tag: str, *, on: bool, fan_only: bool, bearer_token: str
    ) -> Dict[str, Any]:
        """Set cabin overheat protection."""
        return self._command(
            vehicle_tag,
            "set_cabin_overheat_protection",
            bearer_token=bearer_token,
            payload={"on": on, "fan_only": fan_only},
        )

    def set_cop_temp(self, vehicle_tag: str, *, cop_level: int, bearer_token: str) -> Dict[str, Any]:
        """
        Set cabin overheat protection temperature.
        
        Args:
            cop_level: 0=Low (90F/30C), 1=Medium (95F/35C), 2=High (100F/40C)
        """
        return self._command(
            vehicle_tag, "set_cop_temp", bearer_token=bearer_token, payload={"level": cop_level}
        )

    def set_preconditioning_max(
        self, vehicle_tag: str, *, on: bool, manual_override: bool, bearer_token: str
    ) -> Dict[str, Any]:
        """Set preconditioning max override."""
        return self._command(
            vehicle_tag,
            "set_preconditioning_max",
            bearer_token=bearer_token,
            payload={"on": on, "manual_override": manual_override},
        )

    def remote_seat_heater_request(
        self, vehicle_tag: str, *, heater: int, level: int, bearer_token: str
    ) -> Dict[str, Any]:
        """
        Set seat heating level.
        
        Args:
            heater: Seat position (0=driver, 1=passenger, 2=rear-left, 4=rear-center, 5=rear-right)
            level: Heat level 0-3
        """
        return self._command(
            vehicle_tag,
            "remote_seat_heater_request",
            bearer_token=bearer_token,
            payload={"heater": heater, "level": level},
        )

    def remote_seat_cooler_request(
        self, vehicle_tag: str, *, seat_position: int, seat_cooler_level: int, bearer_token: str
    ) -> Dict[str, Any]:
        """
        Set seat cooling level.
        
        Args:
            seat_position: Seat position
            seat_cooler_level: Cooling level 0-3
        """
        return self._command(
            vehicle_tag,
            "remote_seat_cooler_request",
            bearer_token=bearer_token,
            payload={"seat_position": seat_position, "seat_cooler_level": seat_cooler_level},
        )

    def remote_auto_seat_climate_request(
        self, vehicle_tag: str, *, auto_seat_position: int, auto_climate_on: bool, bearer_token: str
    ) -> Dict[str, Any]:
        """Enable/disable automatic seat heating and cooling."""
        return self._command(
            vehicle_tag,
            "remote_auto_seat_climate_request",
            bearer_token=bearer_token,
            payload={"auto_seat_position": auto_seat_position, "auto_climate_on": auto_climate_on},
        )

    def remote_steering_wheel_heater_request(
        self, vehicle_tag: str, *, on: bool, bearer_token: str
    ) -> Dict[str, Any]:
        """Enable/disable steering wheel heater."""
        return self._command(
            vehicle_tag, "remote_steering_wheel_heater_request", bearer_token=bearer_token, payload={"on": on}
        )

    def remote_steering_wheel_heat_level_request(
        self, vehicle_tag: str, *, level: int, bearer_token: str
    ) -> Dict[str, Any]:
        """Set steering wheel heat level."""
        return self._command(
            vehicle_tag,
            "remote_steering_wheel_heat_level_request",
            bearer_token=bearer_token,
            payload={"level": level},
        )

    def remote_auto_steering_wheel_heat_climate_request(
        self, vehicle_tag: str, *, on: bool, bearer_token: str
    ) -> Dict[str, Any]:
        """Enable/disable automatic steering wheel heating."""
        return self._command(
            vehicle_tag,
            "remote_auto_steering_wheel_heat_climate_request",
            bearer_token=bearer_token,
            payload={"on": on},
        )

    # === Charging ===

    def charge_start(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Start charging."""
        return self._command(vehicle_tag, "charge_start", bearer_token=bearer_token)

    def charge_stop(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Stop charging."""
        return self._command(vehicle_tag, "charge_stop", bearer_token=bearer_token)

    def charge_port_door_open(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Open charge port door."""
        return self._command(vehicle_tag, "charge_port_door_open", bearer_token=bearer_token)

    def charge_port_door_close(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Close charge port door."""
        return self._command(vehicle_tag, "charge_port_door_close", bearer_token=bearer_token)

    def set_charge_limit(self, vehicle_tag: str, *, percent: int, bearer_token: str) -> Dict[str, Any]:
        """Set charge limit percentage (50-100)."""
        return self._command(
            vehicle_tag, "set_charge_limit", bearer_token=bearer_token, payload={"percent": percent}
        )

    def charge_standard(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Set charge mode to standard range."""
        return self._command(vehicle_tag, "charge_standard", bearer_token=bearer_token)

    def charge_max_range(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Set charge mode to max range."""
        return self._command(vehicle_tag, "charge_max_range", bearer_token=bearer_token)

    def set_charging_amps(self, vehicle_tag: str, *, charging_amps: int, bearer_token: str) -> Dict[str, Any]:
        """Set charging amperage."""
        return self._command(
            vehicle_tag, "set_charging_amps", bearer_token=bearer_token, payload={"charging_amps": charging_amps}
        )

    def set_scheduled_charging(
        self, vehicle_tag: str, *, enable: bool, time: int, bearer_token: str
    ) -> Dict[str, Any]:
        """
        Set scheduled charging (deprecated, use add_charge_schedule).
        
        Args:
            enable: Enable scheduled charging
            time: Minutes after midnight
        """
        return self._command(
            vehicle_tag,
            "set_scheduled_charging",
            bearer_token=bearer_token,
            payload={"enable": enable, "time": time},
        )

    def add_charge_schedule(
        self,
        vehicle_tag: str,
        *,
        time: str,
        latitude: float,
        longitude: float,
        bearer_token: str,
        name: Optional[str] = None,
        one_time: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Add a charge schedule."""
        payload = {"time": time, "latitude": latitude, "longitude": longitude}
        if name:
            payload["name"] = name
        if one_time is not None:
            payload["one_time"] = one_time
        return self._command(vehicle_tag, "add_charge_schedule", bearer_token=bearer_token, payload=payload)

    def remove_charge_schedule(
        self, vehicle_tag: str, *, schedule_id: int, bearer_token: str
    ) -> Dict[str, Any]:
        """Remove a charge schedule by ID."""
        return self._command(
            vehicle_tag, "remove_charge_schedule", bearer_token=bearer_token, payload={"id": schedule_id}
        )

    def add_precondition_schedule(
        self,
        vehicle_tag: str,
        *,
        time: str,
        latitude: float,
        longitude: float,
        bearer_token: str,
        name: Optional[str] = None,
        one_time: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Add a precondition schedule."""
        payload = {"time": time, "latitude": latitude, "longitude": longitude}
        if name:
            payload["name"] = name
        if one_time is not None:
            payload["one_time"] = one_time
        return self._command(vehicle_tag, "add_precondition_schedule", bearer_token=bearer_token, payload=payload)

    def remove_precondition_schedule(
        self, vehicle_tag: str, *, schedule_id: int, bearer_token: str
    ) -> Dict[str, Any]:
        """Remove a precondition schedule by ID."""
        return self._command(
            vehicle_tag, "remove_precondition_schedule", bearer_token=bearer_token, payload={"id": schedule_id}
        )

    # === Windows & Sunroof ===

    def window_control(
        self, vehicle_tag: str, *, command: str, lat: float, lon: float, bearer_token: str
    ) -> Dict[str, Any]:
        """
        Control windows.
        
        Args:
            command: "vent" or "close"
            lat: User latitude
            lon: User longitude
        """
        return self._command(
            vehicle_tag, "window_control", bearer_token=bearer_token, payload={"command": command, "lat": lat, "lon": lon}
        )

    def sun_roof_control(self, vehicle_tag: str, *, state: str, bearer_token: str) -> Dict[str, Any]:
        """
        Control sunroof.
        
        Args:
            state: "stop", "close", or "vent"
        """
        return self._command(vehicle_tag, "sun_roof_control", bearer_token=bearer_token, payload={"state": state})

    # === Lights & Horn ===

    def flash_lights(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Flash the headlights."""
        return self._command(vehicle_tag, "flash_lights", bearer_token=bearer_token)

    def honk_horn(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Honk the horn."""
        return self._command(vehicle_tag, "honk_horn", bearer_token=bearer_token)

    # === Media ===

    def adjust_volume(self, vehicle_tag: str, *, volume: float, bearer_token: str) -> Dict[str, Any]:
        """Adjust media volume (0.0-10.0)."""
        return self._command(vehicle_tag, "adjust_volume", bearer_token=bearer_token, payload={"volume": volume})

    # === Navigation ===

    def navigation_request(
        self, vehicle_tag: str, *, address: str, bearer_token: str, locale: str = "en-US"
    ) -> Dict[str, Any]:
        """Send navigation destination."""
        return self._command(
            vehicle_tag,
            "navigation_request",
            bearer_token=bearer_token,
            payload={"type": "share_ext_content_raw", "value": {"android.intent.extra.TEXT": address}, "locale": locale},
        )

    # === Security & Safety ===

    def set_sentry_mode(self, vehicle_tag: str, *, on: bool, bearer_token: str) -> Dict[str, Any]:
        """Enable/disable Sentry Mode."""
        return self._command(vehicle_tag, "set_sentry_mode", bearer_token=bearer_token, payload={"on": on})

    def set_valet_mode(self, vehicle_tag: str, *, on: bool, password: str, bearer_token: str) -> Dict[str, Any]:
        """Enable/disable Valet Mode with 4-digit PIN."""
        return self._command(
            vehicle_tag, "set_valet_mode", bearer_token=bearer_token, payload={"on": on, "password": password}
        )

    def reset_valet_pin(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Remove Valet Mode PIN."""
        return self._command(vehicle_tag, "reset_valet_pin", bearer_token=bearer_token)

    def speed_limit_set_limit(self, vehicle_tag: str, *, limit_mph: float, bearer_token: str) -> Dict[str, Any]:
        """Set speed limit (mph)."""
        return self._command(
            vehicle_tag, "speed_limit_set_limit", bearer_token=bearer_token, payload={"limit_mph": limit_mph}
        )

    def speed_limit_activate(self, vehicle_tag: str, *, pin: str, bearer_token: str) -> Dict[str, Any]:
        """Activate Speed Limit Mode with 4-digit PIN."""
        return self._command(vehicle_tag, "speed_limit_activate", bearer_token=bearer_token, payload={"pin": pin})

    def speed_limit_deactivate(self, vehicle_tag: str, *, pin: str, bearer_token: str) -> Dict[str, Any]:
        """Deactivate Speed Limit Mode."""
        return self._command(vehicle_tag, "speed_limit_deactivate", bearer_token=bearer_token, payload={"pin": pin})

    def speed_limit_clear_pin(self, vehicle_tag: str, *, pin: str, bearer_token: str) -> Dict[str, Any]:
        """Clear Speed Limit Mode PIN."""
        return self._command(vehicle_tag, "speed_limit_clear_pin", bearer_token=bearer_token, payload={"pin": pin})

    def speed_limit_clear_pin_admin(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Clear Speed Limit Mode PIN (admin/owner only, firmware 2023.38+)."""
        return self._command(vehicle_tag, "speed_limit_clear_pin_admin", bearer_token=bearer_token)

    def set_pin_to_drive(self, vehicle_tag: str, *, on: bool, password: str, bearer_token: str) -> Dict[str, Any]:
        """Set PIN to Drive."""
        return self._command(
            vehicle_tag, "set_pin_to_drive", bearer_token=bearer_token, payload={"on": on, "password": password}
        )

    def reset_pin_to_drive_pin(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Reset PIN to Drive."""
        return self._command(vehicle_tag, "reset_pin_to_drive_pin", bearer_token=bearer_token)

    def clear_pin_to_drive_admin(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Clear PIN to Drive (admin/owner only, firmware 2023.44+)."""
        return self._command(vehicle_tag, "clear_pin_to_drive_admin", bearer_token=bearer_token)

    # === Software & Updates ===

    def schedule_software_update(
        self, vehicle_tag: str, *, offset_sec: int, bearer_token: str
    ) -> Dict[str, Any]:
        """Schedule OTA software update."""
        return self._command(
            vehicle_tag, "schedule_software_update", bearer_token=bearer_token, payload={"offset_sec": offset_sec}
        )

    def cancel_software_update(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Cancel scheduled software update."""
        return self._command(vehicle_tag, "cancel_software_update", bearer_token=bearer_token)

    # === Misc ===

    def remote_start_drive(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Start vehicle remotely (keyless driving must be enabled)."""
        return self._command(vehicle_tag, "remote_start_drive", bearer_token=bearer_token)

    def trigger_homelink(
        self, vehicle_tag: str, *, lat: float, lon: float, bearer_token: str
    ) -> Dict[str, Any]:
        """Trigger HomeLink (garage door opener)."""
        return self._command(
            vehicle_tag, "trigger_homelink", bearer_token=bearer_token, payload={"lat": lat, "lon": lon}
        )

    def remote_boombox(self, vehicle_tag: str, *, sound: int, bearer_token: str) -> Dict[str, Any]:
        """
        Play sound through external speaker.
        
        Args:
            sound: 0=random fart, 2000=locate ping
        """
        return self._command(vehicle_tag, "remote_boombox", bearer_token=bearer_token, payload={"sound": sound})

    def set_vehicle_name(self, vehicle_tag: str, *, vehicle_name: str, bearer_token: str) -> Dict[str, Any]:
        """Change vehicle name (requires Vehicle Command Protocol)."""
        return self._command(
            vehicle_tag, "set_vehicle_name", bearer_token=bearer_token, payload={"vehicle_name": vehicle_name}
        )

    def guest_mode(self, vehicle_tag: str, *, on: bool, bearer_token: str) -> Dict[str, Any]:
        """Enable/disable Guest Mode."""
        return self._command(vehicle_tag, "guest_mode", bearer_token=bearer_token, payload={"on": on})

    def erase_user_data(self, vehicle_tag: str, *, bearer_token: str) -> Dict[str, Any]:
        """Erase user data from UI (must be parked and in Guest Mode)."""
        return self._command(vehicle_tag, "erase_user_data", bearer_token=bearer_token)

