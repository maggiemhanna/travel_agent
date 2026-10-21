# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

import json
from typing import Any, Dict, List
from uuid import uuid4
import requests

from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI, HTTPException

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from app.config import FILTER_SMART_HOST, FILTER_SMART_PORT, JSON_PARSER_BASE_URL
from app.sub_agents.filter_smart.agent import filter_smart
from app.sub_agents.filter_smart.schema import FilterSmartInput
from app.app_utils.logging import format_dict_for_logs, setup_logging

# --- Configuration & Setup ---
logger = setup_logging(name=__name__)

APP_NAME = "filter_smart"

def call_json_parser_api(api_inputs):
    response = requests.post(f"{JSON_PARSER_BASE_URL}/run-json-parser", json=api_inputs)
    return response.json()


# --- FastAPI Application ---
api = FastAPI(
    title="Filter Smart Agent Service",
    description="API for running the Filter Smart Agent."
)

import re

def load_json_with_markdown(data):
    # Strip leading/trailing whitespace
    logger.info(f"--- Raw Data ---\n{format_dict_for_logs(data, max_len=1000)}")
    data = data.strip()
    
    # Regex to find content inside ```json ... ``` or ``` ... ```
    # Pattern explanation:
    # ```(?:json)? -> matches opening triple backticks and optional 'json' tag
    # \s*          -> matches any whitespace/newlines after the opening
    # (.*?)        -> non-greedy match of the actual JSON content
    # \s*```       -> matches trailing whitespace and closing backticks
    match = re.search(r"```(?:json|JSON)?\s*(.*?)\s*```", data, re.DOTALL)
    
    if match:
        data = match.group(1)
    
    return json.loads(data)


@api.get("/", tags=["Health"])
async def root() -> Dict[str, str]:
    return {"message": "Filter Smart Agent Service is running. Use the /run-filter-smart endpoint via POST."}

# --- Core Agent Logic ---
async def setup_session_and_runner(session_id: str, user_id: str, initial_state: dict):
    """Initializes the session service and runner for the agent."""
    service = InMemorySessionService()
    
    await service.create_session(
        app_name=APP_NAME, 
        user_id=user_id, 
        session_id=session_id, 
        state=initial_state
    )

    runner = Runner(
        agent=filter_smart,
        app_name=APP_NAME,
        session_service=service
    )
    return service, runner

async def execute_agent_run(user_input: FilterSmartInput) -> List[Dict[str, Any]]:
    """Executes the filter smart agent runner and processes its responses."""
    session_id = str(uuid4())
    user_id = str(uuid4())  # Generate per-request rather than globally
    initial_state = user_input.model_dump()

    _, runner = await setup_session_and_runner(
        session_id=session_id, 
        user_id=user_id,
        initial_state=initial_state
    )

    try:
        responses = await runner.run_debug(
            "Follow the system instructions.", 
            user_id=user_id, 
            session_id=session_id,
            quiet=True
        )
        
        parsed_responses =[]
        for resp in responses:
            text_content = resp.content.parts[-1].text
            try:
                parsed_responses.append(load_json_with_markdown(text_content))
            except json.JSONDecodeError:
                logger.warning("Agent response text was not valid JSON. Calling JSON Parser Agent.")
                json_parser_state = {
                    "agent_response": text_content,
                }
                json_parser_response = call_json_parser_api(json_parser_state) 
                logger.info(f"--- JSON Parser Response ---\n{format_dict_for_logs(json_parser_response, max_len=1000)}")
                parsed_responses.append(json_parser_response["results"][0])

        
        logger.info(f"--- Agent Response ---\n{format_dict_for_logs(parsed_responses, max_len=1000)}")
        return parsed_responses

    except Exception as e:
        logger.error(f"An error occurred during agent execution: {e}", exc_info=True)
        raise

# --- FastAPI Endpoints ---
@api.post("/run-filter-smart", response_model=Dict[str, Any], tags=["Agent"])
async def run_filter_smart(user_input: FilterSmartInput) -> Dict[str, Any]:
    """
    Triggers the filter agent with the provided user input.
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
    logger.info(f"Starting Uvicorn server on {FILTER_SMART_HOST}:{FILTER_SMART_PORT}...")
    uvicorn.run(api, host=FILTER_SMART_HOST, port=FILTER_SMART_PORT)