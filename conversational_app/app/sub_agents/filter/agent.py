# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

from google.adk import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.planners import BuiltInPlanner
from google.genai.types import HttpRetryOptions, ThinkingConfig

from app.sub_agents.filter.prompt import system_instruction
from app.sub_agents.filter.schema import FilterInput, FilterOutput

from app.app_utils.logging import setup_logging

logger = setup_logging(name=__name__)

APP_NAME = "conversational_app"

# Create the agent
filter = Agent(
    model=Gemini(
        model="gemini-3.1-pro-preview",
        client_kwargs={"location": "global"},
        use_interactions_api=False,
        retry_options=HttpRetryOptions(
            attempts=5,
            initial_delay=5.0,
            max_delay=60.0,
            exp_base=2.0,
            http_status_codes=[408, 429, 500, 502, 503, 504],
        ),
    ),
    name="filter_agent",
    description="""The Filter Agent: An expert at filtering the results of the flights search agent based on existing filters.""",
    instruction=system_instruction,
    state_schema=FilterInput,
    output_schema=FilterOutput,
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
    root_agent=filter,
)