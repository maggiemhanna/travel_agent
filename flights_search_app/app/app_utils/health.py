# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Standardized liveness (/healthz) and readiness (/readyz) helpers for Cloud Run probes."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Literal, Mapping, Optional

from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

_TRUTHY = {"1", "true", "yes", "on"}


class LivenessResponse(BaseModel):
    """HTTP 200 liveness payload contract for GET /healthz."""

    status: Literal["ok"] = Field("ok", description="Liveness status indicator.")
    service: str = Field(..., description="Logical Cloud Run service identifier.")


class ReadinessResponse(BaseModel):
    """HTTP 200 readiness payload contract for GET /readyz."""

    status: Literal["ready"] = Field("ready", description="Readiness status indicator.")
    service: str = Field(..., description="Logical Cloud Run service identifier.")
    models: Dict[str, str] = Field(
        ..., description="Configured primary Gemini models keyed by agent role."
    )
    fallback_model: Optional[str] = Field(
        None, description="Configured automatic backup Gemini model, when enabled."
    )


class UnreadyResponse(BaseModel):
    """HTTP 503 readiness failure contract for GET /readyz."""

    status: Literal["not_ready"] = Field(
        "not_ready", description="Unready status indicator."
    )
    service: str = Field(..., description="Logical Cloud Run service identifier.")
    errors: List[str] = Field(
        ..., description="Startup or configuration validation errors."
    )


def build_liveness_payload(service_name: str) -> Dict[str, str]:
    """Returns a fast, zero-I/O liveness response payload for /healthz."""
    return {
        "status": "ok",
        "service": service_name,
    }


def evaluate_readiness(
    *,
    service_name: str,
    adk_app: Any,
    models: Mapping[str, str],
    fallback_model: str | None = None,
) -> JSONResponse:
    """Validates ADK App wiring, model configuration, and Vertex AI runtime env vars.

    Intentionally performs zero live LLM network calls so Cloud Run startup probes
    remain fast, deterministic, and cost-free.
    """
    errors: List[str] = []

    if adk_app is None or getattr(adk_app, "root_agent", None) is None:
        errors.append("ADK App or root_agent is not initialized.")

    normalized_models: Dict[str, str] = {}
    for role, model_name in models.items():
        cleaned = (model_name or "").strip()
        normalized_models[role] = cleaned
        if not cleaned:
            errors.append(f"Model configuration '{role}' is empty.")

    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in _TRUTHY
    if use_vertex:
        if not os.getenv("GOOGLE_CLOUD_PROJECT", "").strip():
            errors.append(
                "GOOGLE_CLOUD_PROJECT must be set when GOOGLE_GENAI_USE_VERTEXAI is enabled."
            )
        if not os.getenv("GOOGLE_CLOUD_LOCATION", "").strip():
            errors.append(
                "GOOGLE_CLOUD_LOCATION must be set when GOOGLE_GENAI_USE_VERTEXAI is enabled."
            )

    if errors:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": service_name,
                "errors": errors,
            },
        )

    payload: Dict[str, Any] = {
        "status": "ready",
        "service": service_name,
        "models": normalized_models,
    }
    if fallback_model:
        payload["fallback_model"] = fallback_model.strip()

    return JSONResponse(status_code=200, content=payload)
