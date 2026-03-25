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

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.oauth_proxy import OAuthProxy

TESLA_AUTH_URL = "https://auth.tesla.com/oauth2/v3/authorize"
TESLA_TOKEN_URL = "https://auth.tesla.com/oauth2/v3/token"
TESLA_SCOPES = [
    "openid",
    "offline_access",
    "vehicle_device_data",
    "vehicle_cmds",
    "vehicle_charging_cmds",
    "energy_device_data",
    "energy_cmds",
]

# In-memory mapping: tesla_token → mtm_token
# Populated by TeslaTokenVerifier on each token verification.
# Cleared on server restart (acceptable for MVP).
_token_map: dict[str, str] = {}


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

    On first use, calls POST /auth/exchange on the MyTeslaMate API with the
    Tesla token. On subsequent requests, serves from the in-memory cache.
    """

    def __init__(self, *, required_scopes: list[str] | None = None, mtm_base_url: str):
        super().__init__(required_scopes=required_scopes)
        self.mtm_base_url = mtm_base_url.rstrip("/")

    async def verify_token(self, token: str) -> AccessToken | None:
        if token in _token_map:
            return AccessToken(
                token=token,
                client_id="cached",
                scopes=TESLA_SCOPES,
                expires_at=None,
                claims={"mtm_token": _token_map[token]},
            )

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"{self.mtm_base_url}/auth/exchange",
                    json={"tesla_token": token},
                )
                if r.status_code != 200:
                    return None
                data = r.json()
                mtm_token = data.get("token")
                if not mtm_token:
                    return None
        except httpx.RequestError:
            return None

        _token_map[token] = mtm_token
        return AccessToken(
            token=token,
            client_id=str(data.get("user_id", "unknown")),
            scopes=TESLA_SCOPES,
            expires_at=None,
            claims={"mtm_token": mtm_token},
        )


class TeslaProvider(OAuthProxy):
    """OAuth 2.0 proxy to Tesla's authorization server for FastMCP.

    Handles Dynamic Client Registration for MCP clients (ChatGPT, Claude, etc.),
    proxies the OAuth flow to auth.tesla.com, and exchanges the resulting Tesla
    token for a MyTeslaMate token via /auth/exchange.

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
        )
