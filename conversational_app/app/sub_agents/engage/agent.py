# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

from google.adk import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.planners import BuiltInPlanner
from google.genai.types import HttpRetryOptions, ThinkingConfig

from app.config import (
    ENGAGE_FALLBACK_MODEL,
    ENGAGE_MODEL,
    GEMINI_MODEL_LOCATION,
)
from app.sub_agents.engage.prompt import system_instruction
from app.sub_agents.engage.schema import EngageInput, EngageOutput

from app.app_utils.logging import setup_logging
from app.app_utils.telemetry_plugin import build_plugins

logger = setup_logging(name=__name__)

APP_NAME = "conversational_app"


def build_engage_agent(model_name: str) -> Agent:
    """Builds an Engage ADK Agent bound to the specified Gemini model."""
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
        name="engage",
        description="""The Engage Agent: An expert at understanding user intent and extracting key information from their messages in order to decide which agent to use.""",
        instruction=system_instruction,
        state_schema=EngageInput,
        output_schema=EngageOutput,
        include_contents='none',
        #planner=BuiltInPlanner(
        #    thinking_config=ThinkingConfig(
        #        include_thoughts=False,
        #        thinking_budget=0,
        #    )
        #)
    )


# Create the primary agent & App
engage = build_engage_agent(ENGAGE_MODEL)

app = App(
    name=APP_NAME,
    root_agent=engage,
    plugins=build_plugins(),
)

fallback_app = (
    App(
        name=APP_NAME,
        root_agent=build_engage_agent(ENGAGE_FALLBACK_MODEL),
        plugins=build_plugins(),
    )
    if ENGAGE_FALLBACK_MODEL and ENGAGE_FALLBACK_MODEL != ENGAGE_MODEL
    else None
)