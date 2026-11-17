from typing import Any, Dict, List, Literal, Union
from pydantic import BaseModel, ConfigDict, Field

from app.schema import Flight, RawTextFallback

class FilterSmartInput(BaseModel):
    """Input schema for the Filter Agent."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    user_message: str = Field(..., description="The message from the user.")
    conversational_history: List[str] = Field(default_factory=list, description="The history of the conversation where each string is formatted as 'role: message' (e.g., 'bot: Hello' or 'user: flights under $500').")
    flights_input: List[Flight] = Field(default_factory=list, description="The flights to filter.")

class FilterSmartOutput(BaseModel):
    """Output schema for the Filter Agent."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    agent_response: str = Field(..., description="The response from the agent.")
    flights_output: List[Flight] = Field(..., description="The flights to filter.")


class FilterSmartResponse(BaseModel):
    """HTTP response envelope for standalone Filter Smart service."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    status: Literal["success"] = Field("success", description="Execution status indicator.")
    results: List[Union[FilterSmartOutput, RawTextFallback, Dict[str, Any]]] = Field(..., description="Filter Smart agent response list.")
