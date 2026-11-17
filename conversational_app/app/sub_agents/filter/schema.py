from typing import Any, Dict, List, Literal, Union
from pydantic import BaseModel, ConfigDict, Field

from app.schema import RawTextFallback

class FilterInput(BaseModel):
    """Input schema for the Filter Agent."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    user_message: str = Field(..., description="The message from the user.")
    conversational_history: List[str] = Field(default_factory=list, description="The history of the conversation where each string is formatted as 'role: message' (e.g., 'bot: Hello' or 'user: flights under $500').")

class FilterOutput(BaseModel):
    """Output schema for the Filter Agent."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    agent_response: str = Field(..., description="The response from the agent.")
    filter_type: Literal["direct", "max_price", "max_stops"] = Field(..., description="The type of filter to apply.")
    filter_value: int = Field(..., description="The value of the filter.")


class FilterResponse(BaseModel):
    """HTTP response envelope for standalone Filter service."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    status: Literal["success"] = Field("success", description="Execution status indicator.")
    results: List[Union[FilterOutput, RawTextFallback, Dict[str, Any]]] = Field(..., description="Filter agent response list.")