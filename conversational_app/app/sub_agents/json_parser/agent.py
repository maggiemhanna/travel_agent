# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

from google.adk import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.planners import BuiltInPlanner
from google.genai.types import HttpRetryOptions, ThinkingConfig

from app.config import (
    GEMINI_MODEL_LOCATION,
    JSON_PARSER_FALLBACK_MODEL,
    JSON_PARSER_MODEL,
)
from app.sub_agents.json_parser.prompt import system_instruction
from app.sub_agents.json_parser.schema import JSONParserInput, JSONParserOutput

from app.app_utils.logging import setup_logging
from app.app_utils.telemetry_plugin import build_plugins

logger = setup_logging(name=__name__)

APP_NAME = "conversational_app"


def build_json_parser_agent(model_name: str) -> Agent:
    """Builds a JSON Parser ADK Agent bound to the specified Gemini model."""
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
        name="json_parser",
        description="""The JSON Parser Agent: An expert at parsing the results into JSON format.""",
        instruction=system_instruction,
        state_schema=JSONParserInput,
        output_schema=JSONParserOutput,
        include_contents='none',
        #planner=BuiltInPlanner(
        #    thinking_config=ThinkingConfig(
        #        include_thoughts=False,
        #        thinking_budget=0,
        #    )
        #)
    )


# Create the primary agent & App
json_parser = build_json_parser_agent(JSON_PARSER_MODEL)

app = App(
    name=APP_NAME,
    root_agent=json_parser,
    plugins=build_plugins(),
)

fallback_app = (
    App(
        name=APP_NAME,
        root_agent=build_json_parser_agent(JSON_PARSER_FALLBACK_MODEL),
        plugins=build_plugins(),
    )
    if JSON_PARSER_FALLBACK_MODEL
    and JSON_PARSER_FALLBACK_MODEL != JSON_PARSER_MODEL
    else None
)