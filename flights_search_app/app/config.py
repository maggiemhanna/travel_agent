# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

import os

from dotenv import load_dotenv

# Ensure .env overrides are loaded before reading model or server configuration
load_dotenv()

# --- AI Model Configuration ---
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
FLIGHTS_SEARCH_MODEL = os.getenv("FLIGHTS_SEARCH_MODEL", DEFAULT_GEMINI_MODEL)
GEMINI_MODEL_LOCATION = os.getenv("GEMINI_MODEL_LOCATION", "global")

# --- Server & Endpoint Configuration ---
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
FLIGHTS_SEARCH_BASE_URL = os.getenv(
    "FLIGHTS_SEARCH_BASE_URL", f"http://127.0.0.1:{PORT}"
).rstrip("/")

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]
