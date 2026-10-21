# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

from google.adk import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.planners import BuiltInPlanner
from google.genai.types import HttpRetryOptions, ThinkingConfig

from app.config import FLIGHTS_SEARCH_MODEL, GEMINI_MODEL_LOCATION
from app.prompt import system_instruction
from app.schema import FlightsSearchInput, FlightsSearchOutput

from app.app_utils.logging import setup_logging

logger = setup_logging(name=__name__)

APP_NAME = "app"

# Create the agent
flights_search = Agent(
    model=Gemini(
        model=FLIGHTS_SEARCH_MODEL,
        client_kwargs={"location": GEMINI_MODEL_LOCATION},
        use_interactions_api=False,
        retry_options=HttpRetryOptions(
            attempts=5,
            initial_delay=5.0,
            max_delay=60.0,
            exp_base=2.0,
            http_status_codes=[408, 429, 500, 502, 503, 504],
        ),
    ),
    name="flights_search",
    description="""The Flight Search Agent: An expert flight search simulator. 
    This agent generates a list of flights based on the user's input.""",
    instruction=system_instruction,
    state_schema=FlightsSearchInput,
    output_schema=FlightsSearchOutput,
    include_contents='none',
    planner=BuiltInPlanner(
        thinking_config=ThinkingConfig(
            include_thoughts=False,
            thinking_budget=0,
        )
    )
)

root_agent = flights_search

# Create the main App
app = App(
    name=APP_NAME,
    root_agent=root_agent,
)