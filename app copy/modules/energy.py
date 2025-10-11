"""Energy endpoints module for Tesla MCP."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..base import TeslaClient, TeslaModule, TeslaRequestContext


class EnergyModule(TeslaModule):
    """Energy site endpoints for controlling Tesla Powerwalls and solar."""

    def __init__(self, client: TeslaClient):
        super().__init__(client)

    @staticmethod
    def _energy_site_path(energy_site_id: str, suffix: str = "") -> str:
        """Build energy site endpoint path."""
        clean_suffix = f"/{suffix}" if suffix else ""
        return f"/api/1/energy_sites/{energy_site_id}{clean_suffix}"

    # === Information & Status ===

    def site_info(self, energy_site_id: str, *, bearer_token: str) -> Dict[str, Any]:
        """
        Returns information about the energy site.
        
        Includes:
        - Assets (solar, battery, etc.)
        - Settings (backup reserve, default mode, etc.)
        - Features (storm_mode_capable, etc.)
        
        Power values are in watts.
        Energy values are in watt hours.
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._energy_site_path(energy_site_id, "site_info")
        return self.client.get(endpoint, context=context)

    def live_status(self, energy_site_id: str, *, bearer_token: str) -> Dict[str, Any]:
        """
        Returns the live status of the energy site.
        
        Includes:
        - Power (watts)
        - State of energy (watt hours)
        - Grid status
        - Storm mode
        
        Power values are in watts.
        Energy values are in watt hours.
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._energy_site_path(energy_site_id, "live_status")
        return self.client.get(endpoint, context=context)

    # === History & Analytics ===

    def energy_history(
        self,
        energy_site_id: str,
        *,
        start_date: str,
        end_date: str,
        bearer_token: str,
        period: Optional[str] = None,
        time_zone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns the energy measurements of the site, aggregated to the requested period.
        
        Args:
            start_date: ISO 8601 date (e.g., "2024-01-01")
            end_date: ISO 8601 date (e.g., "2024-01-31")
            period: Aggregation period (e.g., "day", "week", "month")
            time_zone: Time zone (e.g., "America/Los_Angeles")
        
        Energy values are in watt hours.
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._energy_site_path(energy_site_id, "calendar_history")
        params = {
            "kind": "energy",
            "start_date": start_date,
            "end_date": end_date,
        }
        if period:
            params["period"] = period
        if time_zone:
            params["time_zone"] = time_zone
        return self.client.get(endpoint, context=context, params=params)

    def backup_history(
        self,
        energy_site_id: str,
        *,
        start_date: str,
        end_date: str,
        bearer_token: str,
        period: Optional[str] = None,
        time_zone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns the backup (off-grid) event history of the site in duration of seconds.
        
        Args:
            start_date: ISO 8601 date (e.g., "2024-01-01")
            end_date: ISO 8601 date (e.g., "2024-01-31")
            period: Aggregation period (e.g., "day", "week", "month")
            time_zone: Time zone (e.g., "America/Los_Angeles")
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._energy_site_path(energy_site_id, "calendar_history")
        params = {
            "kind": "backup",
            "start_date": start_date,
            "end_date": end_date,
        }
        if period:
            params["period"] = period
        if time_zone:
            params["time_zone"] = time_zone
        return self.client.get(endpoint, context=context, params=params)

    def charge_history(
        self,
        energy_site_id: str,
        *,
        start_date: str,
        end_date: str,
        bearer_token: str,
        time_zone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns the charging history of a wall connector.
        
        Args:
            start_date: ISO 8601 date (e.g., "2024-01-01")
            end_date: ISO 8601 date (e.g., "2024-01-31")
            time_zone: Time zone (e.g., "America/Los_Angeles")
        
        Energy values are in watt hours.
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._energy_site_path(energy_site_id, "telemetry_history")
        params = {
            "kind": "charge",
            "start_date": start_date,
            "end_date": end_date,
        }
        if time_zone:
            params["time_zone"] = time_zone
        return self.client.get(endpoint, context=context, params=params)

    # === Control & Configuration ===

    def operation(
        self,
        energy_site_id: str,
        *,
        default_real_mode: str,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """
        Set the site's operation mode.
        
        Args:
            default_real_mode: "autonomous" for time-based control, "self_consumption" for self-powered mode
        
        Visit https://www.tesla.com/support/energy/powerwall/mobile-app/powerwall-modes for more info.
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._energy_site_path(energy_site_id, "operation")
        payload = {"default_real_mode": default_real_mode}
        return self.client.post(endpoint, context=context, json=payload)

    def backup(
        self,
        energy_site_id: str,
        *,
        backup_reserve_percent: int,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """
        Adjust the site's backup reserve.
        
        Args:
            backup_reserve_percent: Backup reserve percentage (0-100)
        
        Visit https://www.tesla.com/support/energy/powerwall/mobile-app/powerwall-modes#backup-reserve-anchor for more info.
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._energy_site_path(energy_site_id, "backup")
        payload = {"backup_reserve_percent": backup_reserve_percent}
        return self.client.post(endpoint, context=context, json=payload)

    def off_grid_vehicle_charging_reserve(
        self,
        energy_site_id: str,
        *,
        off_grid_vehicle_charging_reserve_percent: int,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """
        Adjust the site's off-grid vehicle charging backup reserve.
        
        Args:
            off_grid_vehicle_charging_reserve_percent: Reserve percentage for vehicle charging during outage (0-100)
        
        Visit https://www.tesla.com/support/energy/powerwall/mobile-app/vehicle-charging-during-power-outage for more info.
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._energy_site_path(energy_site_id, "off_grid_vehicle_charging_reserve")
        payload = {"off_grid_vehicle_charging_reserve_percent": off_grid_vehicle_charging_reserve_percent}
        return self.client.post(endpoint, context=context, json=payload)

    def storm_mode(
        self,
        energy_site_id: str,
        *,
        enabled: bool,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """
        Update storm watch participation.
        
        Args:
            enabled: Enable/disable storm mode
        
        Visit https://www.tesla.com/support/energy/powerwall/mobile-app/storm-watch for more info.
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._energy_site_path(energy_site_id, "storm_mode")
        payload = {"enabled": enabled}
        return self.client.post(endpoint, context=context, json=payload)

    def grid_import_export(
        self,
        energy_site_id: str,
        *,
        bearer_token: str,
        disallow_charge_from_grid_with_solar_installed: Optional[bool] = None,
        customer_preferred_export_rule: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Allow/disallow charging from the grid and exporting energy to the grid.
        
        Args:
            disallow_charge_from_grid_with_solar_installed: If true, prevent charging from grid when solar is installed
            customer_preferred_export_rule: Export rule (e.g., "battery_ok", "pv_only", "never")
        
        Visit https://www.tesla.com/support/energy/powerwall/mobile-app/powerwall-modes#energy-exports-anchor for more info.
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._energy_site_path(energy_site_id, "grid_import_export")
        payload = {}
        if disallow_charge_from_grid_with_solar_installed is not None:
            payload["disallow_charge_from_grid_with_solar_installed"] = disallow_charge_from_grid_with_solar_installed
        if customer_preferred_export_rule is not None:
            payload["customer_preferred_export_rule"] = customer_preferred_export_rule
        return self.client.post(endpoint, context=context, json=payload)

    def time_of_use_settings(
        self,
        energy_site_id: str,
        *,
        tou_settings: Dict[str, Any],
        bearer_token: str,
    ) -> Dict[str, Any]:
        """
        Update the time of use settings for the energy site.
        
        Args:
            tou_settings: Tariff structure with seasons, periods, and rates.
                         See https://digitalassets-energy.tesla.com/raw/upload/app/fleet-api/example-tariff/PGE-EV2-A.json for example.
        
        Visit https://www.tesla.com/support/energy/powerwall/mobile-app/utility-rate-plans for more info.
        
        The tariff structure should include:
        - tariff_content_v2: Tariff structure with seasons and time periods
        - Seasons with start/end dates
        - Time of use periods with labels (ON_PEAK, OFF_PEAK, PARTIAL_PEAK, SUPER_OFF_PEAK)
        - Energy charges or demand charges
        - Valid currency strings: USD, EUR, GBP
        
        Validation requirements:
        - No overlaps of time periods
        - No gaps in time periods
        - No overlapping seasons or gaps between seasons
        - Buy price should be >= sell price
        - No negative prices
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._energy_site_path(energy_site_id, "time_of_use_settings")
        payload = {"tou_settings": tou_settings}
        return self.client.post(endpoint, context=context, json=payload)
