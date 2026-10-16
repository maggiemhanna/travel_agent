# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

import json
from typing import Any, Dict, List
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, HTTPException

from app.schema import OrchestratorInput, OrchestratorOutput
from app.app_utils.logging import format_dict_for_logs, setup_logging

# --- Configuration & Setup ---
logger = setup_logging(name=__name__)

import requests

def call_engage_api(api_inputs):
    response = requests.post("http://127.0.0.1:8002/run-engage", json=api_inputs)
    return response.json()

def call_filter_api(api_inputs):
    response = requests.post("http://127.0.0.1:8003/run-filter", json=api_inputs)
    return response.json()

def call_smart_filter_api(api_inputs):
    response = requests.post("http://127.0.0.1:8004/run-filter-smart", json=api_inputs)
    return response.json()

def call_inspiration_agent_api(api_inputs):
    response = requests.post("http://127.0.0.1:8005/run-inspiration", json=api_inputs)
    return response.json()

# --- FastAPI Application ---
api = FastAPI(
    title="Orchestrator Agent Service",
    description="API for running the Orchestrator Agent."
)

from fastapi.middleware.cors import CORSMiddleware

api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@api.get("/", tags=["Health"])
async def root() -> Dict[str, str]:
    return {"message": "Orchestrator Agent Service is running. Use the /run-orchestrator endpoint via POST."}

# --- Core Agent Logic ---

async def execute_agent_run(user_input: OrchestratorInput) -> List[Dict[str, Any]]:
    """Executes the engage agent runner and processes its responses."""
    session_id = str(uuid4())
    user_id = str(uuid4())  # Generate per-request rather than globally
    initial_state = user_input.model_dump()

    try:
        # Call the endpoint engage deployed at uvicorn.run("main:api", host="127.0.0.1", port=8002, reload=False)
        engage_state = {
            "user_message": user_input.user_message,
            "conversational_history": user_input.conversational_history,
        }
        engage_response = call_engage_api(engage_state) 
        logger.info(f"--- Engage API response ---\n{format_dict_for_logs(engage_response)}")

        results = engage_response["results"][0]
        
        if results["agent_decision"] == "continue":
            return {"status": "success", "results": results}
        
        if results["agent_decision"] == "filter":
            
            filter_state = {
                "user_message": user_input.user_message,
                "conversational_history": user_input.conversational_history,
            }
            filter_response = call_filter_api(filter_state) 
            logger.info(f"--- Filter API response ---\n{format_dict_for_logs(filter_response)}")
            results = results | filter_response["results"][0]
            logger.info(f"--- Engage & Filter API response ---\n{format_dict_for_logs(results)}")

        if results["agent_decision"] == "smart_filter":
            smart_filter_state = {
                "user_message": initial_state["user_message"],
                "conversational_history": initial_state["conversational_history"],
                "flights_input": initial_state["flights_input"]
            }
            logger.info(f"--- Smart Filter API input ---\n{format_dict_for_logs(smart_filter_state)}")
            smart_filter_response = call_smart_filter_api(smart_filter_state) 
            logger.info(f"--- Smart Filter API response ---\n{format_dict_for_logs(smart_filter_response)}")
            results = results | smart_filter_response["results"][0]
            logger.info(f"--- Engage & Smart Filter API response ---\n{format_dict_for_logs(results)}")

        if results["agent_decision"] == "inspiration_agent":
            inspiration_state = {
                "user_message": initial_state["user_message"],
                "conversational_history": initial_state["conversational_history"],
                "origin": initial_state["flights_search_input"]["origin"],
                "destination": initial_state["flights_search_input"]["destination"],
                "departure_date": initial_state["flights_search_input"]["departure_date"],
                "return_date": initial_state["flights_search_input"]["return_date"],
                "passengers": initial_state["flights_search_input"]["passengers"]
            }
            logger.info(f"--- Inspiration Agent API input ---\n{format_dict_for_logs(inspiration_state)}")
            inspiration_response = call_inspiration_agent_api(inspiration_state) 
            logger.info(f"--- Inspiration Agent API response ---\n{format_dict_for_logs(inspiration_response)}")
            results["flights_search_output"] = inspiration_response["results"][0]
            results["inspiration_response"] = inspiration_response["results"][0]["inspiration_response"]
            results["flights_search_output"].pop("inspiration_response")
            logger.info(f"--- Inspiration Agent API response ---\n{format_dict_for_logs(results)}")

        return {"status": "success", "results": results}

    except Exception as e:
        logger.error(f"An error occurred during agent execution: {e}", exc_info=True)
        raise

# --- FastAPI Endpoints ---
@api.post("/run-orchestrator", response_model=Dict[str, Any], tags=["Agent"])
async def run_orchestrator(user_input: OrchestratorInput) -> Dict[str, Any]:
    """
    Triggers the engage agent with the provided user input.
    The response will contain the structured JSON output from the agent.
    """
    logger.info(f"--- Raw User Input ---\n{format_dict_for_logs(user_input.model_dump())}")
    logger.info("--- Executing Agent Runner... ---")

    try:
        results = await execute_agent_run(user_input)
        return results

    except Exception:
        logger.exception("A critical error occurred while processing the request.")
        raise HTTPException(
            status_code=500, 
            detail="Internal Server Error during request processing."
        )

# --- Running the Server ---
if __name__ == "__main__":
    logger.info("Starting Uvicorn server...")
    uvicorn.run(api, host="127.0.0.1", port=8001)