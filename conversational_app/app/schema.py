from typing import Literal, List, Optional
from pydantic import BaseModel, Field, field_validator

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

    @field_validator("stops")
    @classmethod
    def _validate_stops(cls, value: int) -> int:
        if value < 0:
            raise ValueError("stops must be >= 0.")
        return value

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

    @field_validator("origin", "destination", "departure_date", "return_date")
    @classmethod
    def _validate_non_empty_params(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 200:
            raise ValueError("Flight search fields must be non-empty strings up to 200 characters.")
        return cleaned

    @field_validator("passengers")
    @classmethod
    def _validate_passengers(cls, value: int) -> int:
        if value < 1 or value > 9:
            raise ValueError("passengers must be between 1 and 9.")
        return value

class ConversationalInput(BaseModel):
    """Input schema for the Conversational Agent."""
    user_message: str = Field(..., description="The message from the user.")
    conversational_history: List[str] = Field(..., description="The history of the conversation where each string is formatted as 'role: message' (e.g., 'bot: Hello' or 'user: flights under $500').")
    flights_input: List[Flight] = Field(..., description="The flights to filter.")
    flights_search_input: FlightParams = Field(..., description="The flights search input.")

    @field_validator("user_message")
    @classmethod
    def _validate_user_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 4000:
            raise ValueError("user_message must be a non-empty string up to 4000 characters.")
        return value

class ConversationalOutput(BaseModel):
    """Output schema for the Conversational Agent."""
    agent_response: str = Field(..., description="The response from the agent.")
    agent_decision: Literal["filter", "filter_smart", "inspiration_agent", "continue"] = Field(..., description="The decision of the agent.")
    filter_type: Optional[str] = Field(None, description="The type of filter to apply.")
    filter_value: Optional[int] = Field(None, description="The value of the filter to apply.")
    flights_output: Optional[List[Flight]] = Field(None, description="The flights filtered by the smart filter.")
    flights_search_output: Optional[FlightParams] = Field(None, description="The flights search output.")

class ConversationalState(ConversationalInput, ConversationalOutput):
    """State schema for the Conversational Workflow combining ConversationalInput and ConversationalOutput."""
    agent_response: Optional[str] = Field(None, description="The response from the agent.")
    agent_decision: Optional[Literal["filter", "filter_smart", "inspiration_agent", "continue"]] = Field(None, description="The decision of the agent.")