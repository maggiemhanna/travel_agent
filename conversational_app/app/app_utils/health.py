# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Standardized liveness (/healthz) and readiness (/readyz) helpers for Cloud Run probes."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Mapping

from fastapi.responses import JSONResponse

_TRUTHY = {"1", "true", "yes", "on"}


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
