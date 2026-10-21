# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

from google.adk import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.planners import BuiltInPlanner
from google.genai.types import HttpRetryOptions, ThinkingConfig

from app.config import ENGAGE_MODEL, GEMINI_MODEL_LOCATION
from app.sub_agents.engage.prompt import system_instruction
from app.sub_agents.engage.schema import EngageInput, EngageOutput

from app.app_utils.logging import setup_logging

logger = setup_logging(name=__name__)

APP_NAME = "conversational_app"

# Create the agent
engage = Agent(
    model=Gemini(
        model=ENGAGE_MODEL,
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

# Create the main App
app = App(
    name=APP_NAME,
    root_agent=engage,
)