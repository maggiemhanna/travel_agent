# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

import os
from typing import Optional

from dotenv import load_dotenv
from google.genai.types import ThinkingConfig, ThinkingLevel

# Ensure .env overrides are loaded before reading model or endpoint configuration
load_dotenv()

# --- AI Model Configuration ---
DEFAULT_GEMINI_MODEL = os.getenv(
    "CONVERSATIONAL_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
)
FALLBACK_GEMINI_MODEL = os.getenv("FALLBACK_GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_MODEL_LOCATION = os.getenv("GEMINI_MODEL_LOCATION", "global")

# Per-sub-agent model overrides (fall back to DEFAULT_GEMINI_MODEL)
ENGAGE_MODEL = os.getenv("ENGAGE_MODEL", DEFAULT_GEMINI_MODEL)
FILTER_MODEL = os.getenv("FILTER_MODEL", DEFAULT_GEMINI_MODEL)
FILTER_SMART_MODEL = os.getenv("FILTER_SMART_MODEL", DEFAULT_GEMINI_MODEL)
INSPIRATION_MODEL = os.getenv("INSPIRATION_MODEL", DEFAULT_GEMINI_MODEL)
JSON_PARSER_MODEL = os.getenv("JSON_PARSER_MODEL", DEFAULT_GEMINI_MODEL)

# Per-sub-agent thinking budget (tokens; 0 disables thinking on models that support thinking_budget)
ENGAGE_THINKING_BUDGET = int(os.getenv("ENGAGE_THINKING_BUDGET", "0"))
FILTER_THINKING_BUDGET = int(os.getenv("FILTER_THINKING_BUDGET", "0"))
INSPIRATION_THINKING_BUDGET = int(os.getenv("INSPIRATION_THINKING_BUDGET", "0"))
JSON_PARSER_THINKING_BUDGET = int(os.getenv("JSON_PARSER_THINKING_BUDGET", "0"))
FILTER_SMART_THINKING_BUDGET = int(os.getenv("FILTER_SMART_THINKING_BUDGET", "512"))

# Optional per-sub-agent thinking level (LOW, MEDIUM, HIGH, MINIMAL) — required for Gemini 4 models
ENGAGE_THINKING_LEVEL: Optional[str] = (
    os.getenv("ENGAGE_THINKING_LEVEL", "").strip().upper() or None
)
FILTER_THINKING_LEVEL: Optional[str] = (
    os.getenv("FILTER_THINKING_LEVEL", "").strip().upper() or None
)
INSPIRATION_THINKING_LEVEL: Optional[str] = (
    os.getenv("INSPIRATION_THINKING_LEVEL", "").strip().upper() or None
)
JSON_PARSER_THINKING_LEVEL: Optional[str] = (
    os.getenv("JSON_PARSER_THINKING_LEVEL", "").strip().upper() or None
)
FILTER_SMART_THINKING_LEVEL: Optional[str] = (
    os.getenv("FILTER_SMART_THINKING_LEVEL", "").strip().upper() or None
)


def build_thinking_config(
    model_name: str,
    *,
    thinking_budget: Optional[int] = 0,
    thinking_level: Optional[str] = None,
) -> ThinkingConfig:
    """Builds a model-compatible ThinkingConfig without passing conflicting budget/level fields."""
    if thinking_level:
        return ThinkingConfig(
            include_thoughts=False,
            thinking_level=ThinkingLevel[thinking_level.upper()],
        )
    normalized = (model_name or "").strip().lower()
    if normalized.startswith("gemini-4"):
        # Gemini 4 models reject thinking_budget and require thinking_level (LOW/MEDIUM/HIGH).
        level = (
            ThinkingLevel.LOW
            if thinking_budget is None or thinking_budget <= 0
            else ThinkingLevel.MEDIUM
        )
        return ThinkingConfig(include_thoughts=False, thinking_level=level)
    return ThinkingConfig(
        include_thoughts=False,
        thinking_budget=0 if thinking_budget is None else int(thinking_budget),
    )

# Per-sub-agent backup model overrides (fall back to FALLBACK_GEMINI_MODEL)
ENGAGE_FALLBACK_MODEL = os.getenv("ENGAGE_FALLBACK_MODEL", FALLBACK_GEMINI_MODEL)
FILTER_FALLBACK_MODEL = os.getenv("FILTER_FALLBACK_MODEL", FALLBACK_GEMINI_MODEL)
FILTER_SMART_FALLBACK_MODEL = os.getenv(
    "FILTER_SMART_FALLBACK_MODEL", FALLBACK_GEMINI_MODEL
)
INSPIRATION_FALLBACK_MODEL = os.getenv(
    "INSPIRATION_FALLBACK_MODEL", FALLBACK_GEMINI_MODEL
)
JSON_PARSER_FALLBACK_MODEL = os.getenv(
    "JSON_PARSER_FALLBACK_MODEL", FALLBACK_GEMINI_MODEL
)

# --- Main Conversational Service Endpoint Configuration ---
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))
CONVERSATIONAL_BASE_URL = os.getenv(
    "CONVERSATIONAL_BASE_URL", f"http://127.0.0.1:{PORT}"
).rstrip("/")

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

# --- Sub-Agent Standalone Service Endpoints ---
SUB_AGENT_DEFAULT_HOST = os.getenv("SUB_AGENT_HOST", "127.0.0.1")

ENGAGE_HOST = os.getenv("ENGAGE_HOST", SUB_AGENT_DEFAULT_HOST)
ENGAGE_PORT = int(os.getenv("ENGAGE_PORT", "8002"))
ENGAGE_BASE_URL = os.getenv(
    "ENGAGE_BASE_URL", f"http://{ENGAGE_HOST}:{ENGAGE_PORT}"
).rstrip("/")

FILTER_HOST = os.getenv("FILTER_HOST", SUB_AGENT_DEFAULT_HOST)
FILTER_PORT = int(os.getenv("FILTER_PORT", "8003"))
FILTER_BASE_URL = os.getenv(
    "FILTER_BASE_URL", f"http://{FILTER_HOST}:{FILTER_PORT}"
).rstrip("/")

FILTER_SMART_HOST = os.getenv("FILTER_SMART_HOST", SUB_AGENT_DEFAULT_HOST)
FILTER_SMART_PORT = int(os.getenv("FILTER_SMART_PORT", "8004"))
FILTER_SMART_BASE_URL = os.getenv(
    "FILTER_SMART_BASE_URL", f"http://{FILTER_SMART_HOST}:{FILTER_SMART_PORT}"
).rstrip("/")

INSPIRATION_HOST = os.getenv("INSPIRATION_HOST", SUB_AGENT_DEFAULT_HOST)
INSPIRATION_PORT = int(os.getenv("INSPIRATION_PORT", "8005"))
INSPIRATION_BASE_URL = os.getenv(
    "INSPIRATION_BASE_URL", f"http://{INSPIRATION_HOST}:{INSPIRATION_PORT}"
).rstrip("/")

JSON_PARSER_HOST = os.getenv("JSON_PARSER_HOST", SUB_AGENT_DEFAULT_HOST)
JSON_PARSER_PORT = int(os.getenv("JSON_PARSER_PORT", "8006"))
JSON_PARSER_BASE_URL = os.getenv(
    "JSON_PARSER_BASE_URL", f"http://{JSON_PARSER_HOST}:{JSON_PARSER_PORT}"
).rstrip("/")

# --- ADK Plugin Configuration ---
ENABLE_TELEMETRY_PLUGIN = os.getenv(
    "ENABLE_TELEMETRY_PLUGIN", "true"
).strip().lower() in {"1", "true", "yes", "on"}

