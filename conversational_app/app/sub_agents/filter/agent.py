# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

from google.adk import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.planners import BuiltInPlanner
from google.genai.types import HttpRetryOptions, ThinkingConfig

from app.config import (
    FILTER_FALLBACK_MODEL,
    FILTER_MODEL,
    FILTER_THINKING_BUDGET,
    FILTER_THINKING_LEVEL,
    GEMINI_MODEL_LOCATION,
    build_thinking_config,
)
from app.sub_agents.filter.prompt import system_instruction
from app.sub_agents.filter.schema import FilterInput, FilterOutput

from app.app_utils.logging import setup_logging
from app.app_utils.telemetry_plugin import build_plugins

logger = setup_logging(name=__name__)

APP_NAME = "conversational_app"


def build_filter_agent(model_name: str) -> Agent:
    """Builds a Filter ADK Agent bound to the specified Gemini model."""
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
        name="filter",
        description="""The Filter Agent: An expert at filtering the results of the flights search agent based on existing filters.""",
        instruction=system_instruction,
        state_schema=FilterInput,
        output_schema=FilterOutput,
        include_contents='none',
        planner=BuiltInPlanner(
            thinking_config=build_thinking_config(
                model_name,
                thinking_budget=FILTER_THINKING_BUDGET,
                thinking_level=FILTER_THINKING_LEVEL,
            )
        ),
    )


# Create the primary agent & App
filter = build_filter_agent(FILTER_MODEL)

app = App(
    name=APP_NAME,
    root_agent=filter,
    plugins=build_plugins(),
)

fallback_app = (
    App(
        name=APP_NAME,
        root_agent=build_filter_agent(FILTER_FALLBACK_MODEL),
        plugins=build_plugins(),
    )
    if FILTER_FALLBACK_MODEL and FILTER_FALLBACK_MODEL != FILTER_MODEL
    else None
)