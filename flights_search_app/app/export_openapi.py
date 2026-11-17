# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Exports the deterministic OpenAPI 3.1 contract snapshot to flights_search_app/openapi.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from app.main import api

OPENAPI_SNAPSHOT_PATH = Path(__file__).resolve().parent.parent / "openapi.json"


def generate_openapi_spec() -> Dict[str, Any]:
    """Generates a fresh, deterministic OpenAPI specification dictionary."""
    api.openapi_schema = None
    return api.openapi()


def export_openapi_snapshot(target_path: Path = OPENAPI_SNAPSHOT_PATH) -> Path:
    """Writes the formatted OpenAPI specification JSON to disk."""
    spec = generate_openapi_spec()
    target_path.write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target_path


if __name__ == "__main__":
    written = export_openapi_snapshot()
    print(f"Exported OpenAPI contract snapshot to {written}")
