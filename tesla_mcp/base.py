"""Core Tesla API client and shared utilities."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests
from requests import Response, Session
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

DEFAULT_TESLA_BASE_URL = "https://api.myteslamate.com"

class TeslaAPIError(RuntimeError):
    """Raised when the Tesla API answers with an error."""

    def __init__(self, message: str, status_code: Optional[int] = None, payload: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


@dataclass
class TeslaRequestContext:
    """Context to execute a Tesla API call."""

    bearer_token: str
    base_url: str

    @classmethod
    def from_env(cls, bearer_token: str) -> "TeslaRequestContext":
        resolved_base = os.getenv("TESLA_BASE_URL", DEFAULT_TESLA_BASE_URL)
        return cls(bearer_token=bearer_token, base_url=resolved_base.rstrip("/"))


class TeslaClient:
    """Minimal Tesla Fleet API client. Authentication handled upstream."""

    def __init__(self, *, timeout: int = 30, max_retries: int = 3, session: Optional[Session] = None):
        self.timeout = timeout
        self.logger = logging.getLogger("tesla_mcp.client")
        self.session = session or self._build_session(max_retries=max_retries)

    def _build_session(self, *, max_retries: int) -> Session:
        session = requests.Session()
        retry = Retry(
            total=max_retries,
            read=max_retries,
            connect=max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _build_headers(self, context: TeslaRequestContext, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {context.bearer_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Tesla-MCP/1.0",
        }
        if extra:
            headers.update({k: v for k, v in extra.items() if v is not None})
        return headers

    def _handle_response(self, response: Response) -> Any:
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            payload: Optional[Dict[str, Any]] = None
            try:
                payload = response.json()
            except ValueError:
                payload = None
            message = payload.get("error") if isinstance(payload, dict) and payload.get("error") else str(exc)
            raise TeslaAPIError(message, status_code=response.status_code, payload=payload) from exc

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        context: TeslaRequestContext,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{context.base_url}{endpoint}"
        self.logger.debug("Tesla API %s %s", method.upper(), url)

        if params is None:
            params = {}
        bypass_value = os.getenv("TESLA_BYPASS")
        if bypass_value and bypass_value != "":
            params["bypass"] = bypass_value
        
        response = self.session.request(
            method=method,
            url=url,
            timeout=self.timeout,
            headers=self._build_headers(context),
            params=params,
            json=json,
        )
        return self._handle_response(response)

    def get(self, endpoint: str, *, context: TeslaRequestContext, params: Optional[Dict[str, Any]] = None) -> Any:
        return self.request("GET", endpoint, context=context, params=params)

    def post(self, endpoint: str, *, context: TeslaRequestContext, json: Optional[Dict[str, Any]] = None) -> Any:
        return self.request("POST", endpoint, context=context, json=json)

    def delete(self, endpoint: str, *, context: TeslaRequestContext, params: Optional[Dict[str, Any]] = None) -> Any:
        return self.request("DELETE", endpoint, context=context, params=params)


class TeslaModule:
    """Base class for feature modules (vehicles, commands, energy, charging)."""

    def __init__(self, client: TeslaClient):
        self.client = client
        self.logger = logging.getLogger(f"tesla_mcp.{self.__class__.__name__}")

    @staticmethod
    def _vehicle_path(vehicle_tag: str, suffix: str = "") -> str:
        clean_suffix = f"/{suffix}" if suffix else ""
        return f"/api/1/vehicles/{vehicle_tag}{clean_suffix}"
