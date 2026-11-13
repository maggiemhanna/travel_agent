# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

from google.adk import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.planners import BuiltInPlanner
from google.adk.tools import google_search
from google.genai.types import HttpRetryOptions, ThinkingConfig

from app.config import (
    FILTER_SMART_FALLBACK_MODEL,
    FILTER_SMART_MODEL,
    GEMINI_MODEL_LOCATION,
)
from app.sub_agents.filter_smart.prompt import system_instruction
from app.sub_agents.filter_smart.schema import FilterSmartInput, FilterSmartOutput

from app.app_utils.logging import setup_logging
from app.app_utils.telemetry_plugin import build_plugins

logger = setup_logging(name=__name__)

APP_NAME = "conversational_app"


def build_filter_smart_agent(model_name: str) -> Agent:
    """Builds a Filter Smart ADK Agent (with Google Search) bound to the specified Gemini model."""
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
        name="filter_smart",
        description="""The Filter Smart Agent: An expert at filtering the results of the flights search agent that are not based on existing filters.""",
        instruction=system_instruction,
        tools=[google_search],
        state_schema=FilterSmartInput,
        include_contents='none',
        #planner=BuiltInPlanner(
        #    thinking_config=ThinkingConfig(
        #        include_thoughts=False,
        #        thinking_budget=0,
        #    )
        #)
    )


# Create the primary agent & App
filter_smart = build_filter_smart_agent(FILTER_SMART_MODEL)

app = App(
    name=APP_NAME,
    root_agent=filter_smart,
    plugins=build_plugins(),
)

fallback_app = (
    App(
        name=APP_NAME,
        root_agent=build_filter_smart_agent(FILTER_SMART_FALLBACK_MODEL),
        plugins=build_plugins(),
    )
    if FILTER_SMART_FALLBACK_MODEL
    and FILTER_SMART_FALLBACK_MODEL != FILTER_SMART_MODEL
    else None
)