"""TeslaMate API endpoints module for Tesla MCP."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from ..base import TeslaClient, TeslaModule, TeslaRequestContext


class TeslaMateAPIModule(TeslaModule):
    """Wrapper around TeslaMate API endpoints."""

    def __init__(self, client: TeslaClient):
        super().__init__(client)

    def _get_teslamate_context(self, bearer_token: str, endpoint: str) -> TeslaRequestContext:
        """Get TeslaMate API context with custom base URL."""
        return TeslaRequestContext(
            bearer_token=bearer_token,
            base_url=endpoint.rstrip("/"),
        )

    def get_cars(self, *, bearer_token: str, endpoint: str) -> Dict[str, Any]:
        """
        Get all cars from TeslaMate.
        
        Returns:
            List of cars with their basic information
        """
        context = self._get_teslamate_context(bearer_token, endpoint)
        return self.client.get("/api/v1/cars", context=context)

    def get_car(self, car_id: int, *, bearer_token: str, endpoint: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific car.
        
        Args:
            car_id: The TeslaMate car ID
            
        Returns:
            Detailed car information
        """
        context = self._get_teslamate_context(bearer_token, endpoint)
        return self.client.get(f"/api/v1/cars/{car_id}", context=context)

    def get_car_battery_health(self, car_id: int, *, bearer_token: str, endpoint: str) -> Dict[str, Any]:
        """
        Get battery health information for a specific car.
        
        Args:
            car_id: The TeslaMate car ID
            
        Returns:
            Battery health data including degradation information
        """
        context = self._get_teslamate_context(bearer_token, endpoint)
        return self.client.get(f"/api/v1/cars/{car_id}/battery-health", context=context)

    def get_car_charges(
        self, 
        car_id: int, 
        *, 
        bearer_token: str,
        endpoint: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get charging sessions for a specific car.
        
        Args:
            car_id: The TeslaMate car ID
            start_date: Optional start date in RFC3339 format (e.g., 2006-01-02T15:04:05Z)
            end_date: Optional end date in RFC3339 format (e.g., 2006-01-02T15:04:05Z)
            
        Returns:
            List of charging sessions
        """
        context = self._get_teslamate_context(bearer_token, endpoint)
        params = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
            
        return self.client.get(f"/api/v1/cars/{car_id}/charges", context=context, params=params)

    def get_car_charge(
        self, 
        car_id: int, 
        charge_id: int, 
        *, 
        bearer_token: str,
        endpoint: str
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific charging session.
        
        Args:
            car_id: The TeslaMate car ID
            charge_id: The charging session ID
            
        Returns:
            Detailed charging session information
        """
        context = self._get_teslamate_context(bearer_token, endpoint)
        return self.client.get(f"/api/v1/cars/{car_id}/charges/{charge_id}", context=context)

    def get_car_drives(
        self, 
        car_id: int, 
        *, 
        bearer_token: str,
        endpoint: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get driving sessions for a specific car.
        
        Args:
            car_id: The TeslaMate car ID
            start_date: Optional start date in RFC3339 format (e.g., 2006-01-02T15:04:05Z)
            end_date: Optional end date in RFC3339 format (e.g., 2006-01-02T15:04:05Z)
            
        Returns:
            List of driving sessions
        """
        context = self._get_teslamate_context(bearer_token, endpoint)
        params = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
            
        return self.client.get(f"/api/v1/cars/{car_id}/drives", context=context, params=params)

    def get_car_drive(
        self, 
        car_id: int, 
        drive_id: int, 
        *, 
        bearer_token: str,
        endpoint: str
    ) -> Dict[str, Any]:
        """
        Get detailed information about a specific driving session.
        
        Args:
            car_id: The TeslaMate car ID
            drive_id: The driving session ID
            
        Returns:
            Detailed driving session information
        """
        context = self._get_teslamate_context(bearer_token, endpoint)
        return self.client.get(f"/api/v1/cars/{car_id}/drives/{drive_id}", context=context)

    def get_car_status(self, car_id: int, *, bearer_token: str, endpoint: str) -> Dict[str, Any]:
        """
        Get current status of a specific car.
        
        Args:
            car_id: The TeslaMate car ID
            
        Returns:
            Current car status information
        """
        context = self._get_teslamate_context(bearer_token, endpoint)
        return self.client.get(f"/api/v1/cars/{car_id}/status", context=context)

    def get_car_updates(self, car_id: int, *, bearer_token: str, endpoint: str) -> Dict[str, Any]:
        """
        Get software updates information for a specific car.
        
        Args:
            car_id: The TeslaMate car ID
            
        Returns:
            Software updates information
        """
        context = self._get_teslamate_context(bearer_token, endpoint)
        return self.client.get(f"/api/v1/cars/{car_id}/updates", context=context)