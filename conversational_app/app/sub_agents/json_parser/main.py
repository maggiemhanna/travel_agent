# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

import json
from typing import Any, Dict, List
from uuid import uuid4

from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI, HTTPException

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from app.config import JSON_PARSER_FALLBACK_MODEL, JSON_PARSER_MODEL
from app.sub_agents.json_parser.agent import app, fallback_app, json_parser
from app.sub_agents.json_parser.schema import JSONParserInput
from app.app_utils.health import build_liveness_payload, evaluate_readiness
from app.app_utils.logging import format_dict_for_logs, setup_logging

# --- Configuration & Setup ---
logger = setup_logging(name=__name__)

APP_NAME = "json_parser"

# Load the environment variables before initializing the app
load_dotenv()

# --- FastAPI Application ---
api = FastAPI(
    title="JSON Parser Agent Service",
    description="API for running the JSON Parser Agent."
)

@api.get("/", tags=["Health"])
async def root() -> Dict[str, str]:
    return {"message": "JSON Parser Agent Service is running. Use the /run-json-parser endpoint via POST."}

@api.get("/healthz", tags=["Health"])
async def healthz() -> Dict[str, str]:
    return build_liveness_payload(APP_NAME)

@api.get("/readyz", tags=["Health"])
async def readyz():
    return evaluate_readiness(
        service_name=APP_NAME,
        adk_app=app,
        models={"json_parser": JSON_PARSER_MODEL},
        fallback_model=JSON_PARSER_FALLBACK_MODEL if fallback_app is not None else None,
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
        text_content = resp.content.parts[-1].text
        try:
            parsed_responses.append(json.loads(text_content))
        except json.JSONDecodeError:
            logger.warning("Agent response text was not valid JSON. Returning raw text.")
            parsed_responses.append({"raw_text": text_content})

    return parsed_responses

async def execute_agent_run(user_input: JSONParserInput) -> List[Dict[str, Any]]:
    """Executes the json_parser agent runner with automatic backup model failover."""
    initial_state = user_input.model_dump()

    try:
        parsed_responses = await _run_with_app(initial_state, app)
        logger.info(f"--- Agent Response ---\n{format_dict_for_logs(parsed_responses)}")
        return parsed_responses
    except Exception as primary_err:
        if fallback_app is None:
            logger.error(f"An error occurred during agent execution: {primary_err}", exc_info=True)
            raise
        logger.warning(
            "Primary model '%s' failed (%s: %s). Failing over to backup model '%s'.",
            JSON_PARSER_MODEL,
            type(primary_err).__name__,
            primary_err,
            JSON_PARSER_FALLBACK_MODEL,
        )
        parsed_responses = await _run_with_app(initial_state, fallback_app)
        logger.info(
            f"--- Backup Model ({JSON_PARSER_FALLBACK_MODEL}) Agent Response ---\n"
            f"{format_dict_for_logs(parsed_responses)}"
        )
        return parsed_responses

# --- FastAPI Endpoints ---
@api.post("/run-json-parser", response_model=Dict[str, Any], tags=["Agent"])
async def run_json_parser(user_input: JSONParserInput) -> Dict[str, Any]:
    """
    Triggers the json_parser agent with the provided user input.
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

# --- Running the Server ---
if __name__ == "__main__":
    from app.config import JSON_PARSER_HOST, JSON_PARSER_PORT

    logger.info(f"Starting Uvicorn server on {JSON_PARSER_HOST}:{JSON_PARSER_PORT}...")
    uvicorn.run(api, host=JSON_PARSER_HOST, port=JSON_PARSER_PORT)