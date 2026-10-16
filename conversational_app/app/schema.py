from typing import Literal, List, Optional
from pydantic import BaseModel, Field

class Flight(BaseModel):
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
    departure_time: str = Field(
        ..., 
        description="The departure time for the flight search."
    )
    arrival_time: str = Field(
        ..., 
        description="The arrival time for the flight search."
    )
    return_time: str = Field(
        ..., 
        description="The return time for the flight search."
    )
    return_arrival_time: str = Field(
        ..., 
        description="The return arrival time for the flight search."
    )
    price: str = Field(
        ..., 
        description="The price of the flight."
    )
    airline: str = Field(
        ..., 
        description="The airline of the flight."
    )
    flight_number: str = Field(
        ..., 
        description="The flight number of the flight."
    )
    stops: int = Field(
        ..., 
        description="The number of stops on the flight."
    )
    stopover_cities: List[str] = Field(
        ..., 
        description="The cities where the flight stops."
    )

class FlightParams(BaseModel):
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

class OrchestratorInput(BaseModel):
    """Input schema for the Orchestrator Agent."""
    user_message: str = Field(..., description="The message from the user.")
    conversational_history: List[str] = Field(..., description="The history of the conversation where each string is formatted as 'role: message' (e.g., 'bot: Hello' or 'user: flights under $500').")
    flights_input: List[Flight] = Field(..., description="The flights to filter.")
    flights_search_input: FlightParams = Field(..., description="The flights search input.")

class OrchestratorOutput(BaseModel):
    """Output schema for the Orchestrator Agent."""
    agent_response: str = Field(..., description="The response from the agent.")
    agent_decision: Literal["filter", "filter_smart", "inspiration_agent", "continue"] = Field(..., description="The decision of the agent.")
    filter_response: Optional[str] = Field(None, description="The response from the filter or filter_smart agent.")
    filter_type: Optional[str] = Field(None, description="The type of filter to apply.")
    filter_value: Optional[int] = Field(None, description="The value of the filter to apply.")
    flights_output: Optional[List[Flight]] = Field(None, description="The flights filtered by the smart filter.")
    flights_search_output: Optional[FlightParams] = Field(None, description="The flights search output.")
    inspiration_response: Optional[str] = Field(None, description="The response from the inspiration agent.")