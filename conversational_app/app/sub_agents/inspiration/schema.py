from typing import Any, Dict, List, Literal, Union
from pydantic import BaseModel, ConfigDict, Field

from app.schema import FlightParams, RawTextFallback


class InspirationInput(BaseModel):
    """Input schema for the Inspiration Agent."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    user_message: str = Field(..., description="The message from the user.")
    conversational_history: List[str] = Field(
        default_factory=list,
        description=(
            "The history of the conversation where each string is formatted as "
            "'role: message' (e.g., 'bot: Hello' or 'user: flights under $500')."
        ),
    )
    flights_search_input: FlightParams = Field(..., description="The flights search input.")


class InspirationOutput(BaseModel):
    """
    The structure for the user's raw request provided to the Inspiration agent.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    agent_response: str = Field(..., description="The inspiration response for the new flight search.")
    flights_search_output: FlightParams = Field(..., description="The flights search output.")


class InspirationResponse(BaseModel):
    """HTTP response envelope for standalone Inspiration service."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    status: Literal["success"] = Field("success", description="Execution status indicator.")
    results: List[Union[InspirationOutput, RawTextFallback, Dict[str, Any]]] = Field(
        ..., description="Inspiration agent response list."
    )
