# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

from google.adk import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.planners import BuiltInPlanner
from google.genai.types import HttpRetryOptions, ThinkingConfig

from app.config import (
    FLIGHTS_SEARCH_FALLBACK_MODEL,
    FLIGHTS_SEARCH_MODEL,
    GEMINI_MODEL_LOCATION,
)
from app.prompt import system_instruction
from app.schema import FlightsSearchInput, FlightsSearchOutput

from app.app_utils.logging import setup_logging
from app.app_utils.telemetry_plugin import build_plugins

logger = setup_logging(name=__name__)

APP_NAME = "app"


def build_flights_search_agent(model_name: str) -> Agent:
    """Builds a Flights Search ADK Agent bound to the specified Gemini model."""
    return Agent(
        model=Gemini(
            model=model_name,
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
        ),
    )


def build_flights_search_app(model_name: str) -> App:
    """Builds an isolated ADK App container for primary or backup model execution."""
    return App(
        name=APP_NAME,
        root_agent=build_flights_search_agent(model_name),
        plugins=build_plugins(),
    )


# Create primary agent & App
flights_search = build_flights_search_agent(FLIGHTS_SEARCH_MODEL)
root_agent = flights_search

app = App(
    name=APP_NAME,
    root_agent=root_agent,
    plugins=build_plugins(),
)

# Create isolated backup App for automatic cross-model failover
fallback_app = (
    build_flights_search_app(FLIGHTS_SEARCH_FALLBACK_MODEL)
    if FLIGHTS_SEARCH_FALLBACK_MODEL
    and FLIGHTS_SEARCH_FALLBACK_MODEL != FLIGHTS_SEARCH_MODEL
    else None
)