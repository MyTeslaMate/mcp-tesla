"""Tesla OAuth 2.0 provider for FastMCP.

Proxies the OAuth flow to Tesla's authorization server (auth.tesla.com),
exchanges the Tesla token for a MyTeslaMate token, and stores the mapping
so MCP tools can call the MyTeslaMate API transparently.

Example:
    ```python
    from fastmcp import FastMCP
    from tesla_mcp.oauth import TeslaProvider

    mcp = FastMCP("Tesla Vehicle MCP", auth=TeslaProvider())
    ```

Environment variables:
    TESLA_OAUTH_CLIENT_ID      Tesla Developer app client ID
    TESLA_OAUTH_CLIENT_SECRET  Tesla Developer app client secret
    TESLA_OAUTH_BASE_URL       Public URL of this MCP server (for OAuth callback)
    TESLA_OAUTH_MTM_BASE_URL   Base URL of the MyTeslaMate API
"""

from __future__ import annotations

import logging

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.oauth_proxy import OAuthProxy
from mcp.server.auth.provider import AuthorizationParams, OAuthClientInformationFull

logger = logging.getLogger("tesla_mcp.oauth")

TESLA_AUTH_URL = "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/authorize"
TESLA_TOKEN_URL = "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token"
TESLA_SCOPES = [
    "openid",
    "offline_access",
    "user_data",
    "vehicle_device_data",
    "vehicle_location",
    "vehicle_cmds",
    "vehicle_charging_cmds",
    "energy_device_data",
    "energy_cmds",
]

# In-memory mapping: tesla_token → {mtm_token, subscribe_api, subscribe_teslamate, teslamate_api_endpoint}
# Populated by TeslaTokenVerifier on each token verification.
# Cleared on server restart (acceptable for MVP).
_token_map: dict[str, dict] = {}


class TeslaProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TESLA_OAUTH_",
        env_file=".env",
        extra="ignore",
    )
    client_id: str | None = None
    client_secret: SecretStr | None = None
    base_url: str | None = None
    mtm_base_url: str | None = None


class TeslaTokenVerifier(TokenVerifier):
    """Verifies a Tesla access token by exchanging it for a MyTeslaMate token.

    On first use, calls POST /api/auth/exchange on the MyTeslaMate API with the
    Tesla token. On subsequent requests, serves from the in-memory cache.
    """

    def __init__(self, *, required_scopes: list[str] | None = None, mtm_base_url: str):
        super().__init__(required_scopes=required_scopes)
        self.mtm_base_url = mtm_base_url.rstrip("/")

    async def verify_token(self, token: str) -> AccessToken | None:
        if token in _token_map:
            cached = _token_map[token]
            return AccessToken(
                token=token,
                client_id="cached",
                scopes=TESLA_SCOPES,
                expires_at=None,
                claims={
                    "mtm_token": cached["mtm_token"],
                    "subscribe_api": cached["subscribe_api"],
                    "subscribe_teslamate": cached["subscribe_teslamate"],
                    "teslamate_api_endpoint": cached["teslamate_api_endpoint"],
                    "teslamate_auth_type": cached["teslamate_auth_type"],
                },
            )

        # Try Tesla → MTM exchange first (the OAuth-flow path used by ChatGPT
        # and Claude.ai). Fall back to a direct MTM-token introspection so
        # backend callers (e.g. the Laravel chat) that already hold an MTM
        # bearer can also authenticate.
        data = await self._exchange(token, key="tesla_token")
        if data is None or not data.get("token"):
            data = await self._exchange(token, key="mtm_token")
        if data is None or not data.get("token"):
            logger.info("verify_token: rejected (neither tesla_token nor mtm_token matched)")
            return None

        mtm_token = data["token"]
        subscribe_api = bool(data.get("subscribe_api", False))
        subscribe_teslamate = bool(data.get("subscribe_teslamate", False))
        teslamate_api_endpoint = data.get("teslamate_api_endpoint", "")
        teslamate_auth_type = (data.get("auth_type") or "").lower()
        _token_map[token] = {
            "mtm_token": mtm_token,
            "subscribe_api": subscribe_api,
            "subscribe_teslamate": subscribe_teslamate,
            "teslamate_api_endpoint": teslamate_api_endpoint,
            "teslamate_auth_type": teslamate_auth_type,
        }
        return AccessToken(
            token=token,
            client_id=str(data.get("user_id", "unknown")),
            scopes=TESLA_SCOPES,
            expires_at=None,
            claims={
                "mtm_token": mtm_token,
                "subscribe_api": subscribe_api,
                "subscribe_teslamate": subscribe_teslamate,
                "teslamate_api_endpoint": teslamate_api_endpoint,
                "teslamate_auth_type": teslamate_auth_type,
            },
        )

    async def _exchange(self, token: str, *, key: str) -> dict | None:
        """POST {key: token} to /api/auth/exchange. Returns the JSON body on
        2xx, None otherwise. Logs the outcome for diagnosis."""
        url = f"{self.mtm_base_url}/api/auth/exchange"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(url, json={key: token})
        except httpx.RequestError as exc:
            logger.warning("verify_token: %s exchange failed network: %s", key, exc)
            return None
        if r.status_code != 200:
            logger.info(
                "verify_token: %s exchange returned %d (body=%s)",
                key, r.status_code, r.text[:200],
            )
            return None
        try:
            return r.json()
        except ValueError:
            logger.warning("verify_token: %s exchange returned non-JSON", key)
            return None


class TeslaProvider(OAuthProxy):
    """OAuth 2.0 proxy to Tesla's authorization server for FastMCP.

    Handles Dynamic Client Registration for MCP clients (ChatGPT, Claude, etc.),
    proxies the OAuth flow to auth.tesla.com, and exchanges the resulting Tesla
    token for a MyTeslaMate token via /api/auth/exchange.

    Example:
        ```python
        auth = TeslaProvider()  # reads from TESLA_OAUTH_* env vars
        mcp = FastMCP("Tesla Vehicle MCP", auth=auth)
        ```
    """

    def __init__(
        self,
        *,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
        mtm_base_url: str | None = None,
    ):
        settings = TeslaProviderSettings.model_validate(
            {
                k: v
                for k, v in {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "base_url": base_url,
                    "mtm_base_url": mtm_base_url,
                }.items()
                if v is not None
            }
        )

        if not settings.client_id:
            raise ValueError(
                "client_id is required — set via parameter or TESLA_OAUTH_CLIENT_ID"
            )
        if not settings.client_secret:
            raise ValueError(
                "client_secret is required — set via parameter or TESLA_OAUTH_CLIENT_SECRET"
            )
        if not settings.mtm_base_url:
            raise ValueError(
                "mtm_base_url is required — set via parameter or TESLA_OAUTH_MTM_BASE_URL"
            )

        super().__init__(
            upstream_authorization_endpoint=TESLA_AUTH_URL,
            upstream_token_endpoint=TESLA_TOKEN_URL,
            upstream_client_id=settings.client_id,
            upstream_client_secret=settings.client_secret.get_secret_value(),
            token_verifier=TeslaTokenVerifier(
                required_scopes=TESLA_SCOPES,
                mtm_base_url=settings.mtm_base_url,
            ),
            base_url=settings.base_url,
            issuer_url=settings.base_url,
            token_endpoint_auth_method="client_secret_post",
        )

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        # Tesla does not support RFC 8707 resource indicators — strip it to avoid
        # "Invalid audience" errors on auth.tesla.com.
        return await super().authorize(client, params.model_copy(update={"resource": None}))

    async def load_access_token(self, token: str) -> AccessToken | None:  # type: ignore[override]
        """Validate the bearer.

        Default behaviour delegates to ``OAuthProxy.load_access_token``, which
        only accepts FastMCP-issued JWTs (the OAuth-flow path used by ChatGPT
        and Claude.ai). When that path fails — typically because a backend
        caller (e.g. our Laravel chat) sends a raw MyTeslaMate API token — we
        fall back to the underlying ``TokenVerifier``. The verifier in turn
        knows how to introspect both Tesla and MTM tokens via the MyTeslaMate
        ``/api/auth/exchange`` endpoint.
        """
        result = await super().load_access_token(token)
        if result is not None:
            return result
        logger.info("load_access_token: JWT path failed, trying raw bearer fallback")
        return await self._token_validator.verify_token(token)
