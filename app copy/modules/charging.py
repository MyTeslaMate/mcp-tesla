"""Charging endpoints module for Tesla MCP."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..base import TeslaClient, TeslaModule, TeslaRequestContext


class ChargingModule(TeslaModule):
    """Charging endpoints for Tesla charging history and invoices."""

    def __init__(self, client: TeslaClient):
        super().__init__(client)

    def charging_history(
        self,
        *,
        bearer_token: str,
        vin: Optional[str] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Dict[str, Any]:
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
        
        Returns:
            Paginated charging history with events
        """
        context = TeslaRequestContext.from_env(bearer_token)
        params = {}
        if vin:
            params["vin"] = vin
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        if sort_by:
            params["sortBy"] = sort_by
        if sort_order:
            params["sortOrder"] = sort_order
        
        return self.client.get("/api/1/dx/charging/history", context=context, params=params)

    def charging_invoice(
        self,
        invoice_id: str,
        *,
        bearer_token: str,
    ) -> Any:
        """
        Returns a charging invoice PDF for an event from charging history.
        
        Args:
            invoice_id: The invoice ID from charging history
        
        Returns:
            PDF file content for the charging invoice
        """
        context = TeslaRequestContext.from_env(bearer_token)
        endpoint = f"/api/1/dx/charging/invoice/{invoice_id}"
        return self.client.get(endpoint, context=context)

    def charging_sessions(
        self,
        *,
        bearer_token: str,
        vin: Optional[str] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> Dict[str, Any]:
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
        
        Returns:
            Charging session information with pricing and energy data
        """
        context = TeslaRequestContext.from_env(bearer_token)
        params = {}
        if vin:
            params["vin"] = vin
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["pageSize"] = page_size
        if start_time:
            params["startTime"] = start_time
        if end_time:
            params["endTime"] = end_time
        if sort_by:
            params["sortBy"] = sort_by
        if sort_order:
            params["sortOrder"] = sort_order
        
        return self.client.get("/api/1/dx/charging/sessions", context=context, params=params)
