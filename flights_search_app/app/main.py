# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

import json
import os
from typing import Any, Dict, List
from uuid import uuid4

from dotenv import load_dotenv
import uvicorn
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from app.agent import app, fallback_app, flights_search
from app.config import (
    ALLOWED_ORIGINS,
    FLIGHTS_SEARCH_FALLBACK_MODEL,
    FLIGHTS_SEARCH_MODEL,
    HOST,
    PORT,
)
from app.schema import FlightsSearchInput, FlightsSearchResponse, RootInfoResponse
from app.app_utils.health import (
    LivenessResponse,
    ReadinessResponse,
    UnreadyResponse,
    build_liveness_payload,
    evaluate_readiness,
)
from app.app_utils.logging import format_dict_for_logs, setup_logging
from app.app_utils.versioning import (
    API_V1_PREFIX,
    API_VERSION,
    VERSIONING_EXPOSED_HEADERS,
    register_versioning_middleware,
)

# --- Configuration & Setup ---
logger = setup_logging(name=__name__)

APP_NAME = "flights_search"
SERVICE_NAME = "flights-search-app"

# --- FastAPI Application ---
api = FastAPI(
    title="Flights Search Agent Service",
    description="API for running the Flights Search Agent.",
    version=API_VERSION,
)

api.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=VERSIONING_EXPOSED_HEADERS,
)

register_versioning_middleware(
    api,
    deprecated_route_map={
        "/run-flights-search": f"{API_V1_PREFIX}/run-flights-search",
    },
)

@api.get("/", response_model=RootInfoResponse, tags=["Health"])
async def root() -> Dict[str, str]:
    return {"message": "Flights Search Agent Service is running. Use the /run-flights-search endpoint via POST."}

@api.get("/healthz", response_model=LivenessResponse, tags=["Health"])
async def healthz() -> Dict[str, str]:
    """Cloud Run liveness probe endpoint."""
    return build_liveness_payload(SERVICE_NAME)

@api.get(
    "/readyz",
    response_model=ReadinessResponse,
    responses={503: {"model": UnreadyResponse}},
    tags=["Health"],
)
async def readyz():
    """Cloud Run startup/readiness probe endpoint."""
    return evaluate_readiness(
        service_name=SERVICE_NAME,
        adk_app=app,
        models={"flights_search": FLIGHTS_SEARCH_MODEL},
        fallback_model=FLIGHTS_SEARCH_FALLBACK_MODEL if fallback_app is not None else None,
    )

# --- Core Agent Logic ---
async def setup_session_and_runner(
    session_id: str, user_id: str, initial_state: dict, target_app=None
):
    """Initializes the session service and runner for the agent."""
    service = InMemorySessionService()
    
    await service.create_session(
        app_name=APP_NAME, 
        user_id=user_id, 
        session_id=session_id, 
        state=initial_state
    )

    runner = Runner(
        app=target_app or app,
        app_name=APP_NAME,
        session_service=service
    )
    return service, runner

async def _run_with_app(initial_state: dict, target_app) -> List[Dict[str, Any]]:
    """Executes a single isolated ADK Runner pass against the given App."""
    session_id = str(uuid4())
    user_id = str(uuid4())
    _, runner = await setup_session_and_runner(
        session_id=session_id,
        user_id=user_id,
        initial_state=initial_state,
        target_app=target_app,
    )
    responses = await runner.run_debug(
        "Follow the system instructions.",
        user_id=user_id,
        session_id=session_id,
        quiet=True,
    )

    parsed_responses = []
    for resp in responses:
        if not resp.content or not resp.content.parts:
            continue
        text_content = resp.content.parts[-1].text
        if not text_content:
            continue
        try:
            parsed_responses.append(json.loads(text_content))
        except json.JSONDecodeError:
            logger.warning("Agent response text was not valid JSON. Returning raw text.")
            parsed_responses.append({"raw_text": text_content})

    return parsed_responses

async def execute_agent_run(user_input: FlightsSearchInput) -> List[Dict[str, Any]]:
    """Executes the flight search agent runner with automatic backup model failover."""
    initial_state = user_input.model_dump()

    try:
        parsed_responses = await _run_with_app(initial_state, app)
        logger.info(f"--- Agent Response ---\n{format_dict_for_logs(parsed_responses)}")
        return parsed_responses
    except Exception as primary_err:
        if fallback_app is None:
            logger.error(
                f"An error occurred during agent execution (no fallback configured): {primary_err}",
                exc_info=True,
            )
            raise

        logger.warning(
            "Primary model '%s' failed (%s: %s). Failing over to backup model '%s'.",
            FLIGHTS_SEARCH_MODEL,
            type(primary_err).__name__,
            primary_err,
            FLIGHTS_SEARCH_FALLBACK_MODEL,
        )
        try:
            parsed_responses = await _run_with_app(initial_state, fallback_app)
            logger.info(
                f"--- Backup Model ({FLIGHTS_SEARCH_FALLBACK_MODEL}) Agent Response ---\n"
                f"{format_dict_for_logs(parsed_responses)}"
            )
            return parsed_responses
        except Exception as fallback_err:
            logger.error(
                f"Backup model '{FLIGHTS_SEARCH_FALLBACK_MODEL}' also failed: {fallback_err}",
                exc_info=True,
            )
            raise

# --- FastAPI Endpoints ---
v1_router = APIRouter(prefix=API_V1_PREFIX, tags=["Agent v1"])

@v1_router.post(
    "/run-flights-search",
    response_model=FlightsSearchResponse,
    response_model_exclude_none=True,
    operation_id="run_flights_search_v1",
)
async def run_flights_search(user_input: FlightsSearchInput) -> Dict[str, Any]:
    """
    Triggers the flights search agent with the provided user input.
    The response will contain the structured JSON output from the agent.
    """
    logger.info(f"--- Raw User Input ---\n{format_dict_for_logs(user_input.model_dump())}")
    logger.info("--- Executing Agent Runner... ---")

    try:
        results = await execute_agent_run(user_input)
        return {
            "status": "success",
            "results": results
        }
    except Exception:
        logger.exception("A critical error occurred while processing the request.")
        raise HTTPException(
            status_code=500, 
            detail="Internal Server Error during request processing."
        )

api.include_router(v1_router)

# Backward-compatible unversioned alias (emits RFC 8594 Deprecation + Link headers)
api.add_api_route(
    "/run-flights-search",
    run_flights_search,
    methods=["POST"],
    response_model=FlightsSearchResponse,
    response_model_exclude_none=True,
    deprecated=True,
    tags=["Agent (Legacy)"],
    operation_id="run_flights_search_legacy",
)

# --- Running the Server ---
if __name__ == "__main__":
    logger.info(f"Starting Uvicorn server on {HOST}:{PORT}...")
    uvicorn.run(api, host=HOST, port=PORT)