"""Shared auth + response-sanitization helpers used by app.py and sub-servers.

Extracted from app.py so mounted sub-servers can reuse them without circular imports.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

from fastmcp import Context, FastMCP

from .base import TeslaAPIError


logger = logging.getLogger("tesla_mcp")


SENSITIVE_KEY_NAMES = {
    "access_token",
    "refresh_token",
    "id_token",
    "token",
    "tesla_token",
    "mtm_token",
    "authorization",
    "client_secret",
    "api_key",
    "password",
    "secret",
    "set-cookie",
    "cookie",
}
INTERNAL_TELEMETRY_KEYS = {
    "session_id",
    "trace_id",
    "request_id",
    "correlation_id",
    "internal_id",
    "debug",
    "stack_trace",
}
SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"^Bearer\s+[A-Za-z0-9._\-+/=]+$", re.IGNORECASE),
    re.compile(r"^[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}$"),
]


def extract_bearer_token(ctx: Context) -> str:
    """Extract bearer token from MCP request headers.

    OAuth mode: fastmcp 3.x issues its own JWTs — the MTM token is stored in
    ``AccessToken.claims`` by ``TeslaTokenVerifier``.
    Manual mode: the ``Authorization`` header carries the MTM token directly.
    """
    request = ctx.request_context.request

    user = getattr(request, "user", None) if hasattr(request, "user") else None
    if user and hasattr(user, "access_token"):
        mtm_token = user.access_token.claims.get("mtm_token")
        if mtm_token:
            return mtm_token

    if hasattr(request, "headers"):
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]

    raise RuntimeError("No Authorization header found in MCP request")


def extract_teslamate_bearer_token(ctx: Context) -> str:
    return extract_bearer_token(ctx)


def extract_teslamate_auth_type(ctx: Context) -> str:
    """Return 'basic' or 'bearer' to decide the Authorization scheme for TeslaMate calls."""
    request = ctx.request_context.request
    user = getattr(request, "user", None) if hasattr(request, "user") else None
    if user and hasattr(user, "access_token"):
        auth_type = user.access_token.claims.get("teslamate_auth_type", "")
        if auth_type:
            return auth_type.lower()
    if hasattr(request, "headers"):
        return (request.headers.get("x-teslamate-auth-type") or "bearer").lower()
    return "bearer"


def extract_teslamate_endpoint(ctx: Context) -> str:
    """Extract Teslamate API endpoint from OAuth claims or ``x-teslamate-endpoint`` header."""
    request = ctx.request_context.request

    user = getattr(request, "user", None) if hasattr(request, "user") else None
    if user and hasattr(user, "access_token"):
        endpoint = user.access_token.claims.get("teslamate_api_endpoint", "")
        if endpoint:
            return endpoint

    if hasattr(request, "headers"):
        return request.headers.get("x-teslamate-endpoint", "")

    raise RuntimeError("No Teslamate endpoint found in MCP request")


def teslamate_auth_kwargs(ctx: Context) -> dict[str, str]:
    """Return the {bearer_token, endpoint, auth_type} kwargs every TeslaMate module call needs."""
    return {
        "bearer_token": extract_teslamate_bearer_token(ctx),
        "endpoint": extract_teslamate_endpoint(ctx),
        "auth_type": extract_teslamate_auth_type(ctx),
    }


def _looks_like_secret_string(value: str) -> bool:
    return any(pattern.match(value.strip()) for pattern in SENSITIVE_VALUE_PATTERNS)


def sanitize_response_payload(payload: Any) -> Any:
    """Remove sensitive/auth/debug fields before returning tool output."""
    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in SENSITIVE_KEY_NAMES:
                continue
            if normalized_key in INTERNAL_TELEMETRY_KEYS:
                continue
            cleaned[key] = sanitize_response_payload(value)
        return cleaned

    if isinstance(payload, list):
        return [sanitize_response_payload(item) for item in payload]

    if isinstance(payload, str) and _looks_like_secret_string(payload):
        return "***redacted***"

    return payload


def make_tesla_tool(server: FastMCP, app_csp: dict[str, Any]):
    """Build a ``@tesla_tool`` decorator bound to ``server`` with mandatory safety hints.

    Same signature as the original ``tesla_tool`` in app.py — kept here so
    mounted sub-servers can register tools with identical metadata.
    """
    def tesla_tool(
        *,
        tags: set[str],
        read_only: bool,
        destructive: bool,
        open_world: bool = True,
        output_template: str | None = None,
        app: bool | dict[str, Any] | None = None,
    ):
        kwargs: dict[str, Any] = dict(
            tags=tags,
            annotations={
                "readOnlyHint": read_only,
                "destructiveHint": destructive,
                "openWorldHint": open_world,
            },
            app=app if app is not None else {"csp": app_csp},
        )
        if output_template is not None:
            kwargs["meta"] = {"openai/outputTemplate": output_template}
        return server.tool(**kwargs)

    return tesla_tool


def execute(handler: Callable[..., Any], **kwargs: Any) -> Any:
    """Run a Tesla module method, sanitize its result, normalize Tesla errors."""
    try:
        result = handler(**kwargs)
        return sanitize_response_payload(result)
    except TeslaAPIError as exc:
        logger.error("Tesla API error: %s", exc)
        status = f" (status {exc.status_code})" if exc.status_code else ""
        raise RuntimeError(f"Tesla API error{status}: {exc}") from exc
