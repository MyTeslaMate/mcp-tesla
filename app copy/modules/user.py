"""User endpoints module for Tesla MCP."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..base import TeslaClient, TeslaModule, TeslaRequestContext


class UserModule(TeslaModule):
    """User endpoints for Tesla user information and settings."""
    
    def __init__(self, client: TeslaClient):
        super().__init__(client)
    
    # === User Information ===
    
    def me(self, *, bearer_token: str) -> Dict[str, Any]:
        """
        Returns a summary of a user's account.
        
        Includes:
        - User ID
        - Email
        - Full name
        - Profile image URL
        - Referral code
        
        Endpoint: GET /api/1/users/me
        """
        context = TeslaRequestContext.from_env(bearer_token)
        return self.client.get("/api/1/users/me", context=context)
    
    def feature_config(self, *, bearer_token: str) -> Dict[str, Any]:
        """
        Returns any custom feature flag applied to a user.
        
        Returns feature flags and experimental features enabled for the user.
        
        Endpoint: GET /api/1/users/feature_config
        """
        context = TeslaRequestContext.from_env(bearer_token)
        return self.client.get("/api/1/users/feature_config", context=context)
    
    def region(self, *, bearer_token: str) -> Dict[str, Any]:
        """
        Returns a user's region and appropriate fleet-api base URL.
        
        Accepts no parameters, response is based on the authentication token subject.
        Useful for determining the correct API endpoint for the user's region.
        
        Endpoint: GET /api/1/users/region
        """
        context = TeslaRequestContext.from_env(bearer_token)
        return self.client.get("/api/1/users/region", context=context)
    
    def orders(self, *, bearer_token: str) -> Dict[str, Any]:
        """
        Returns the active orders for a user.
        
        Includes information about pending vehicle orders, upgrades, and purchases.
        
        Endpoint: GET /api/1/users/orders
        """
        context = TeslaRequestContext.from_env(bearer_token)
        return self.client.get("/api/1/users/orders", context=context)

    