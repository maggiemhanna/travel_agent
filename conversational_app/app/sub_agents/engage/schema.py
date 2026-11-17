from typing import Any, Dict, List, Literal, Union
from pydantic import BaseModel, ConfigDict, Field

from app.schema import RawTextFallback


class EngageInput(BaseModel):
    """Input schema for the Engage Agent."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    user_message: str = Field(..., description="The message from the user.")
    conversational_history: List[str] = Field(
        default_factory=list,
        description=(
            "The history of the conversation where each string is formatted as "
            "'role: message' (e.g., 'bot: Hello' or 'user: flights under $500')."
        ),
    )


class EngageOutput(BaseModel):
    """Output schema for the Engage Agent."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    agent_response: str = Field(..., description="The response from the agent.")
    agent_decision: Literal["continue", "filter", "filter_smart", "inspiration_agent"] = Field(
        ...,
        description=(
            "The decision from the agent to continue the conversation or direct "
            "to another agent filter, filter_smart, inspiration_agent."
        ),
    )


class EngageResponse(BaseModel):
    """HTTP response envelope for standalone Engage service."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    status: Literal["success"] = Field("success", description="Execution status indicator.")
    results: List[Union[EngageOutput, RawTextFallback, Dict[str, Any]]] = Field(
        ..., description="Engage agent response list."
    )
