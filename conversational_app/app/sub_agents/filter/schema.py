from typing import Literal, List
from pydantic import BaseModel, Field

class FilterInput(BaseModel):
    """Input schema for the Filter Agent."""
    user_message: str = Field(..., description="The message from the user.")
    conversational_history: List[str] = Field(..., description="The history of the conversation where each string is formatted as 'role: message' (e.g., 'bot: Hello' or 'user: flights under $500').")

class FilterOutput(BaseModel):
    """Output schema for the Filter Agent."""
    filter_response: str = Field(..., description="The response from the agent.")
    filter_type: Literal["direct", "max_price", "max_stops"] = Field(..., description="The type of filter to apply.")
    filter_value: int = Field(..., description="The value of the filter.")