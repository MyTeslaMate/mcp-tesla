"""Tesla Fleet OAuth provider for FastMCP integration."""

from __future__ import annotations

import os
from typing import Any

import httpx
from pydantic import AnyHttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.oauth_proxy import OAuthProxy
from fastmcp.utilities.auth import parse_scopes
from fastmcp.utilities.logging import get_logger
from fastmcp.utilities.storage import KVStorage
from fastmcp.utilities.types import NotSet, NotSetT

from ...base import DEFAULT_TESLA_BASE_URL

logger = get_logger(__name__)


class TeslaFleetProviderSettings(BaseSettings):
    """Environment-driven configuration for the Tesla Fleet auth provider."""

    model_config = SettingsConfigDict(
        env_prefix="TESLA_MCP_AUTH_TESLA_FLEET_",
        env_file=".env",
        extra="ignore",
    )

    client_id: str | None = None
    client_secret: SecretStr | None = None
    base_url: AnyHttpUrl | str | None = None
    redirect_path: str | None = None
    required_scopes: list[str] | None = None
    timeout_seconds: int | None = None
    allowed_client_redirect_uris: list[str] | None = None
    auth_base_url: AnyHttpUrl | str | None = None
    api_base_url: AnyHttpUrl | str | None = None
    audience: str | None = None

    @field_validator("required_scopes", mode="before")
    @classmethod
    def _parse_scopes(cls, value: Any):
        return parse_scopes(value)


class TeslaFleetTokenVerifier(TokenVerifier):
    """Verify Tesla Fleet OAuth tokens by calling the `/users/me` endpoint."""

    def __init__(
        self,
        *,
        api_base_url: str,
        auth_base_url: str | None,
        required_scopes: list[str] | None = None,
        timeout_seconds: int = 10,
    ):
        super().__init__(required_scopes=required_scopes)
        self.api_base_url = api_base_url.rstrip("/")
        self.auth_base_url = auth_base_url.rstrip("/") if auth_base_url else None
        self.timeout_seconds = timeout_seconds

    async def verify_token(self, token: str) -> AccessToken | None:
        """Call the Tesla Fleet API to validate the provided access token."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    f"{self.api_base_url}/api/1/users/me",
                    headers=headers,
                )

            if response.status_code != 200:
                logger.debug(
                    "Tesla Fleet token verification failed: %s - %s",
                    response.status_code,
                    response.text[:200],
                )
                return None

            payload = response.json()

        except httpx.RequestError as exc:
            logger.debug("Failed to verify Tesla Fleet token: %s", exc)
            return None
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Unexpected Tesla Fleet token verification error: %s", exc)
            return None

        user_data = payload.get("response", payload)
        if not isinstance(user_data, dict):
            logger.debug("Unexpected token verification payload shape: %s", payload)
            return None

        raw_scopes = user_data.get("scopes") or user_data.get("scope")
        token_scopes: list[str] = []
        if isinstance(raw_scopes, list):
            token_scopes = [str(scope) for scope in raw_scopes if scope]
        elif isinstance(raw_scopes, str):
            token_scopes = parse_scopes(raw_scopes)

        if not token_scopes and self.required_scopes:
            token_scopes = list(self.required_scopes)

        if self.required_scopes:
            token_scopes_set = set(token_scopes)
            required_scopes_set = set(self.required_scopes)
            if token_scopes_set and not required_scopes_set.issubset(token_scopes_set):
                logger.debug(
                    "Tesla Fleet token missing required scopes. Has %s, expected %s",
                    token_scopes_set,
                    required_scopes_set,
                )
                return None

        user_id = str(
            user_data.get("user_id")
            or user_data.get("id")
            or user_data.get("uid")
            or user_data.get("email")
            or "unknown"
        )

        claims = {
            "sub": user_data.get("user_id") or user_id,
            "email": user_data.get("email"),
            "name": user_data.get("full_name") or user_data.get("name"),
            "user": user_data,
        }
        if self.auth_base_url:
            claims["issuer"] = self.auth_base_url

        # Drop empty values from claims
        filtered_claims = {k: v for k, v in claims.items() if v is not None}

        return AccessToken(
            token=token,
            client_id=user_id,
            scopes=token_scopes,
            expires_at=None,
            resource_owner=user_data.get("email"),
            claims=filtered_claims,
        )


class TeslaFleetProvider(OAuthProxy):
    """Complete OAuth provider for Tesla Fleet authentication."""

    def __init__(
        self,
        *,
        client_id: str | NotSetT = NotSet,
        client_secret: str | NotSetT = NotSet,
        base_url: AnyHttpUrl | str | NotSetT = NotSet,
        redirect_path: str | NotSetT = NotSet,
        required_scopes: list[str] | NotSetT = NotSet,
        timeout_seconds: int | NotSetT = NotSet,
        allowed_client_redirect_uris: list[str] | NotSetT = NotSet,
        auth_base_url: AnyHttpUrl | str | NotSetT = NotSet,
        api_base_url: AnyHttpUrl | str | NotSetT = NotSet,
        audience: str | NotSetT = NotSet,
        client_storage: KVStorage | None = None,
    ):
        config_values = {
            "client_id": client_id,
            "client_secret": client_secret,
            "base_url": base_url,
            "redirect_path": redirect_path,
            "required_scopes": required_scopes,
            "timeout_seconds": timeout_seconds,
            "allowed_client_redirect_uris": allowed_client_redirect_uris,
            "auth_base_url": auth_base_url,
            "api_base_url": api_base_url,
            "audience": audience,
        }

        settings = TeslaFleetProviderSettings.model_validate(
            {k: v for k, v in config_values.items() if v is not NotSet}
        )

        if not settings.client_id:
            raise ValueError(
                "client_id is required - set via parameter or TESLA_MCP_AUTH_TESLA_FLEET_CLIENT_ID"
            )
        if not settings.client_secret:
            raise ValueError(
                "client_secret is required - set via parameter or TESLA_MCP_AUTH_TESLA_FLEET_CLIENT_SECRET"
            )
        if not settings.base_url:
            raise ValueError(
                "base_url is required - set via parameter or TESLA_MCP_AUTH_TESLA_FLEET_BASE_URL"
            )

        auth_base = str(settings.auth_base_url or "https://auth.tesla.com").rstrip("/")
        api_base = str(
            settings.api_base_url
            or os.getenv("TESLA_BASE_URL")
            or DEFAULT_TESLA_BASE_URL
        ).rstrip("/")

        required_scopes_final = settings.required_scopes or [
            "openid",
            "offline_access",
            "user_data",
            "vehicle_device_data",
            "vehicle_cmds",
        ]
        timeout_seconds_final = settings.timeout_seconds or 15
        allowed_client_redirect_uris_final = settings.allowed_client_redirect_uris
        audience_value = settings.audience or api_base

        token_verifier = TeslaFleetTokenVerifier(
            api_base_url=api_base,
            auth_base_url=auth_base,
            required_scopes=required_scopes_final,
            timeout_seconds=timeout_seconds_final,
        )

        client_secret_str = settings.client_secret.get_secret_value()

        extra_authorize_params: dict[str, str] = {}
        if audience_value:
            extra_authorize_params["audience"] = audience_value

        super().__init__(
            upstream_authorization_endpoint=f"{auth_base}/oauth2/v3/authorize",
            upstream_token_endpoint=f"{auth_base}/oauth2/v3/token",
            upstream_client_id=settings.client_id,
            upstream_client_secret=client_secret_str,
            token_verifier=token_verifier,
            base_url=settings.base_url,
            redirect_path=settings.redirect_path,
            issuer_url=settings.base_url,
            allowed_client_redirect_uris=allowed_client_redirect_uris_final,
            extra_authorize_params=extra_authorize_params,
            client_storage=client_storage,
        )

        logger.info(
            "Initialized Tesla Fleet OAuth provider for client %s targeting %s",
            settings.client_id,
            api_base,
        )
