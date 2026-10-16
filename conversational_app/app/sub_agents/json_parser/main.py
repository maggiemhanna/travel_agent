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

from app.sub_agents.json_parser.agent import json_parser
from app.sub_agents.json_parser.schema import JSONParserInput
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
        agent=json_parser,
        app_name=APP_NAME,
        session_service=service
    )
    return service, runner

async def execute_agent_run(user_input: JSONParserInput) -> List[Dict[str, Any]]:
    """Executes the json_parser agent runner and processes its responses."""
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
                parsed_responses.append(json.loads(text_content))
            except json.JSONDecodeError:
                logger.warning("Agent response text was not valid JSON. Returning raw text.")
                parsed_responses.append({"raw_text": text_content})
        
        logger.info(f"--- Agent Response ---\n{format_dict_for_logs(parsed_responses)}")
        return parsed_responses

    except Exception as e:
        logger.error(f"An error occurred during agent execution: {e}", exc_info=True)
        raise

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
    logger.info("Starting Uvicorn server...")
    uvicorn.run(api, host="127.0.0.1", port=8006)