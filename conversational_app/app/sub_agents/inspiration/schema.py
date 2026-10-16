from typing import List, Optional
from pydantic import BaseModel, Field

class InspirationInput(BaseModel):
    """Input schema for the Inspiration Agent."""
    origin: str = Field(
        ..., 
        description="The origin city for the flight search."
    )
    destination: str = Field(
        ..., 
        description="The destination city for the flight search."
    )
    departure_date: str = Field(
        ..., 
        description="The departure date for the flight search."
    )
    return_date: str = Field(
        ..., 
        description="The return date for the flight search."
    )
    passengers: int = Field(
        ..., 
        description="The number of passengers for the flight search."
    )
    user_message: str = Field(..., description="The message from the user.")
    conversational_history: List[str] = Field(..., description="The history of the conversation where each string is formatted as 'role: message' (e.g., 'bot: Hello' or 'user: flights under $500').")


class InspirationOutput(BaseModel):
    """
    The structure for the user's raw request provided to the Inspiration agent.
    """
    origin: str = Field(
        ..., 
        description="The origin city for the flight search."
    )
    destination: str = Field(
        ..., 
        description="The destination city for the flight search."
    )
    departure_date: str = Field(
        ..., 
        description="The departure date for the flight search."
    )
    return_date: str = Field(
        ..., 
        description="The return date for the flight search."
    )
    passengers: int = Field(
        ..., 
        description="The number of passengers for the flight search."
    )
    inspiration_response: str = Field(
        ..., 
        description="The inspiration response for the new flight search."
    )
        
    