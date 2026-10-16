from typing import Literal, List
from pydantic import BaseModel, Field

class EngageInput(BaseModel):
    """Input schema for the Engage Agent."""
    user_message: str = Field(..., description="The message from the user.")
    conversational_history: List[str] = Field(..., description="The history of the conversation where each string is formatted as 'role: message' (e.g., 'bot: Hello' or 'user: flights under $500').")

class EngageOutput(BaseModel):
    """Output schema for the Engage Agent."""
    agent_response: str = Field(..., description="The response from the agent.")
    agent_decision: Literal["continue", "filter", "smart_filter", "inspiration_agent"] = Field(..., description="The decision from the agent to continue the conversation or direct to another agent filter, smart_filter, inspiration_agent.")