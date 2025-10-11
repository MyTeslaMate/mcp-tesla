"""Vehicle endpoints module for Tesla MCP."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..base import TeslaClient, TeslaModule, TeslaRequestContext


class VehicleEndpoints(TeslaModule):
    """Wrapper around Tesla Fleet vehicle endpoints."""

    def __init__(self, client: TeslaClient):
        super().__init__(client)


    def products(self, *, bearer_token: str) -> Dict[str, Any]:
        """
        Returns vehicles and energy sites mapped to user.
        
        Returns:
            List of vehicles and energy sites
        """
        context = TeslaRequestContext.from_env(bearer_token)
        return self.client.get("/api/1/products", context=context)

    def get_vehicle(
        self,
        vehicle_tag: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """Fetch basic information about a vehicle."""
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag)
        return self.client.get(endpoint, context=context)

    def get_vehicle_data(
        self,
        vehicle_tag: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """Fetch realtime vehicle data."""
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag, "vehicle_data")
        return self.client.get(endpoint, context=context)

    def wake_up_vehicle(
        self,
        vehicle_tag: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """Wake up a sleeping vehicle."""
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag, "wake_up")
        return self.client.post(endpoint, context=context)

    def get_mobile_enabled(
        self,
        vehicle_tag: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """Check if mobile access is enabled for the vehicle."""
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag, "mobile_enabled")
        return self.client.get(endpoint, context=context)

    def get_nearby_charging_sites(
        self,
        vehicle_tag: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """Return nearby charging locations."""
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag, "nearby_charging_sites")
        return self.client.get(endpoint, context=context)

    def get_service_data(
        self,
        vehicle_tag: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """Fetch service data for the vehicle."""
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag, "service_data")
        return self.client.get(endpoint, context=context)

    def get_release_notes(
        self,
        vehicle_tag: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """Return the firmware release notes."""
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag, "release_notes")
        return self.client.get(endpoint, context=context)

    def get_recent_alerts(
        self,
        vehicle_tag: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """Return the vehicle's recent alerts."""
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag, "recent_alerts")
        return self.client.get(endpoint, context=context)

    def get_fleet_status(
        self,
        *,
        vins: List[str],
        bearer_token: str,
    ) -> Dict[str, Any]:
        """Return fleet status information for the provided VINs."""
        context = TeslaRequestContext.from_env(bearer_token)
        payload = {"vins": vins}
        return self.client.post("/api/1/vehicles/fleet_status", context=context, json=payload)

    def get_vehicle_options(
        self,
        vin: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """Return vehicle option details."""
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = "/api/1/dx/vehicles/options"
        return self.client.get(endpoint, context=context, params={"vin": vin})

    def get_eligible_upgrades(
        self,
        vin: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """Return eligible vehicle upgrades."""
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = "/api/1/dx/vehicles/upgrades/eligibility"
        return self.client.get(endpoint, context=context, params={"vin": vin})

    def get_eligible_subscriptions(
        self,
        vin: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """Return eligible subscriptions for a vehicle."""
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = "/api/1/dx/vehicles/subscriptions/eligibility"
        return self.client.get(endpoint, context=context, params={"vin": vin})

    # === Drivers & Sharing ===

    def get_drivers(
        self,
        vehicle_tag: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """
        Returns all allowed drivers for a vehicle.
        
        Note: This endpoint is only available for the vehicle owner.
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag, "drivers")
        return self.client.get(endpoint, context=context)

    def remove_driver(
        self,
        vehicle_tag: str,
        *,
        bearer_token: str,
        share_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Removes driver access from a vehicle.
        
        Share users can only remove their own access.
        Owners can remove share access or their own.
        
        Args:
            share_user_id: The user ID to remove (optional, defaults to self)
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag, "drivers")
        params = {}
        if share_user_id:
            params["share_user_id"] = share_user_id
        return self.client.delete(endpoint, context=context, params=params or None)

    def get_share_invites(
        self,
        vehicle_tag: str,
        *,
        bearer_token: str,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Returns the active share invites for a vehicle.
        
        This endpoint is paginated with a max page size of 25 records.
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag, "invitations")
        params = {}
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size
        return self.client.get(endpoint, context=context, params=params or None)

    def create_share_invite(
        self,
        vehicle_tag: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """
        Create a share invite for a vehicle.
        
        - Each invite link is for single-use and expires after 24 hours.
        - Provides DRIVER privileges (not all OWNER features)
        - Up to five drivers can be added at a time
        - Does not require the car to be online
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag, "invitations")
        return self.client.post(endpoint, context=context)

    # === Fleet Telemetry ===

    def get_fleet_telemetry_config(
        self,
        vehicle_tag: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """
        Fetches a vehicle's fleet telemetry config.
        
        - synced=true: vehicle has adopted the target config
        - synced=false: vehicle will attempt to adopt the target config on next backend connection
        - limit_reached=true: vehicle has reached max supported applications
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag, "fleet_telemetry_config")
        return self.client.get(endpoint, context=context)

    def delete_fleet_telemetry_config(
        self,
        vehicle_tag: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """
        Remove a fleet telemetry configuration from a vehicle.
        
        Removes the configuration for any vehicle if called with a partner token.
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag, "fleet_telemetry_config")
        return self.client.delete(endpoint, context=context)

    def get_fleet_telemetry_errors(
        self,
        vehicle_tag: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """
        Returns recent fleet telemetry errors reported for the specified vehicle.
        
        Errors are reported after receiving the config.
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = self._vehicle_path(vehicle_tag, "fleet_telemetry_errors")
        return self.client.get(endpoint, context=context)

    # === Subscriptions ===

    def get_subscriptions(
        self,
        *,
        bearer_token: str,
        device_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Returns the list of vehicles for which this mobile device currently subscribes to push notifications.
        
        Args:
            device_token: Optional device token for filtering
        """
        context = TeslaRequestContext.from_env(bearer_token)
        params = {}
        if device_token:
            params["device_token"] = device_token
        return self.client.get("/api/1/subscriptions", context=context, params=params or None)

    def set_subscriptions(
        self,
        *,
        vehicle_ids: List[int],
        device_token: str,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """
        Allows a mobile device to specify which vehicles to receive push notifications from.
        
        Args:
            vehicle_ids: List of vehicle IDs to subscribe to
            device_token: Device token for push notifications
        """
        context = TeslaRequestContext.from_env(bearer_token)
        payload = {
            "device_token": device_token,
            "vehicle_ids": vehicle_ids,
        }
        return self.client.post("/api/1/subscriptions", context=context, json=payload)

    def get_vehicle_subscriptions(
        self,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """
        Returns the list of vehicles for which this mobile device currently subscribes to push notifications.
        
        Alternative endpoint to get_subscriptions.
        """
        context = TeslaRequestContext.from_env(bearer_token)
        return self.client.get("/api/1/vehicle_subscriptions", context=context)

    def set_vehicle_subscriptions(
        self,
        *,
        vehicle_ids: List[int],
        bearer_token: str,
    ) -> Dict[str, Any]:
        """
        Allows a mobile device to specify which vehicles to receive push notifications from.
        
        Args:
            vehicle_ids: List of vehicle IDs to subscribe to
        """
        context = TeslaRequestContext.from_env(bearer_token)
        payload = {"vehicle_ids": vehicle_ids}
        return self.client.post("/api/1/vehicle_subscriptions", context=context, json=payload)

    # === Warranty & Other ===

    def get_warranty_details(
        self,
        vin: str,
        *,
        bearer_token: str,
    ) -> Dict[str, Any]:
        """
        Returns the warranty information for a vehicle.
        
        Args:
            vin: Vehicle VIN
        """
        context = TeslaRequestContext.from_env(bearer_token)
        return self.client.get("/api/1/dx/warranty/details", context=context, params={"vin": vin})
