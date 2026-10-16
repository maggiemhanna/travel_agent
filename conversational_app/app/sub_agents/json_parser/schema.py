from typing import Literal, List
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

class JSONParserInput(BaseModel):
    """Input schema for the Filter Agent."""
    response_text: str = Field(..., description="The response from the filter_smart agent.")

class JSONParserOutput(BaseModel):
    """Output schema for the Filter Agent."""
    filter_response: str = Field(..., description="The response from the agent.")
    flights_output: List[Flight] = Field(..., description="The flights to filter.")
