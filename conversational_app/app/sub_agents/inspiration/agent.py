# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

from google.adk import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.planners import BuiltInPlanner
from google.genai.types import HttpRetryOptions, ThinkingConfig

from app.config import (
    GEMINI_MODEL_LOCATION,
    INSPIRATION_FALLBACK_MODEL,
    INSPIRATION_MODEL,
    INSPIRATION_THINKING_BUDGET,
    INSPIRATION_THINKING_LEVEL,
    build_thinking_config,
)
from app.sub_agents.inspiration.prompt import system_instruction
from app.sub_agents.inspiration.schema import InspirationInput, InspirationOutput

from app.app_utils.logging import setup_logging
from app.app_utils.telemetry_plugin import build_plugins

logger = setup_logging(name=__name__)

APP_NAME = "conversational_app"


def build_inspiration_agent(model_name: str) -> Agent:
    """Builds an Inspiration ADK Agent bound to the specified Gemini model."""
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
        name="inspiration",
        description="""The Inspiration Agent: An expert flight inspiration simulator. 
    Your goal is to generate a new destination, or dates based on user message.""",
        instruction=system_instruction,
        state_schema=InspirationInput,
        output_schema=InspirationOutput,
        include_contents='none',
        planner=BuiltInPlanner(
            thinking_config=build_thinking_config(
                model_name,
                thinking_budget=INSPIRATION_THINKING_BUDGET,
                thinking_level=INSPIRATION_THINKING_LEVEL,
            )
        ),
    )


# Create the primary agent & App
inspiration = build_inspiration_agent(INSPIRATION_MODEL)

app = App(
    name=APP_NAME,
    root_agent=inspiration,
    plugins=build_plugins(),
)

fallback_app = (
    App(
        name=APP_NAME,
        root_agent=build_inspiration_agent(INSPIRATION_FALLBACK_MODEL),
        plugins=build_plugins(),
    )
    if INSPIRATION_FALLBACK_MODEL
    and INSPIRATION_FALLBACK_MODEL != INSPIRATION_MODEL
    else None
)