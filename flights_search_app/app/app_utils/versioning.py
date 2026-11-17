# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""API versioning constants and RFC 8594 deprecation header middleware."""

from __future__ import annotations

from typing import Mapping

from fastapi import FastAPI, Request, Response

API_VERSION = "1.0.0"
API_V1_PREFIX = "/api/v1"
VERSIONING_EXPOSED_HEADERS = ["X-API-Version", "Deprecation", "Link"]


def register_versioning_middleware(
    api: FastAPI,
    *,
    api_version: str = API_VERSION,
    deprecated_route_map: Mapping[str, str] | None = None,
) -> None:
    """Attaches X-API-Version to all HTTP responses and Deprecation/Link headers on legacy routes."""
    route_map = dict(deprecated_route_map or {})

    @api.middleware("http")
    async def _api_version_headers(request: Request, call_next) -> Response:
        response: Response = await call_next(request)
        response.headers["X-API-Version"] = api_version
        successor = route_map.get(request.url.path)
        if successor:
            response.headers["Deprecation"] = "true"
            response.headers["Link"] = f'<{successor}>; rel="successor-version"'
        return response
