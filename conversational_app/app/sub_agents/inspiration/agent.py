# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

from google.adk.agents.llm_agent import Agent
from google.adk.models.google_llm import Gemini
from google.adk.planners import BuiltInPlanner
from google.genai.types import HttpRetryOptions, ThinkingConfig
from google.adk.apps import App

from app.sub_agents.inspiration.prompt import system_instruction
from app.sub_agents.inspiration.schema import InspirationInput, InspirationOutput

from app.app_utils.logging import setup_logging

logger = setup_logging(name=__name__)

APP_NAME = "conversational_app"

# Create the agent
inspiration = Agent(
    model=Gemini(
        model="gemini-2.5-pro",
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
    input_schema=InspirationInput,
    output_schema=InspirationOutput,
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
    root_agent=inspiration,
)