from typing import List, Optional
from pydantic import BaseModel, Field, field_validator

class Filters(BaseModel):
    """
    The structure for the user's initial filters.
    """
    direct: Optional[bool] = Field(
        None, 
        description="Whether the flight should be direct."
    )
    max_price: Optional[int] = Field(
        None, 
        description="The maximum price of the flight."
    )
    max_stops: Optional[int] = Field(
        None, 
        description="The maximum number of stops on the flight."
    )

    @field_validator("max_price", "max_stops")
    @classmethod
    def _validate_non_negative_filter(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 0:
            raise ValueError("Filter numeric bounds must be >= 0.")
        return value


class FlightsSearchInput(BaseModel):
    """
    The structure for the user's raw request provided to the Flight Search agent.
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
    filters: Filters = Field(
        ..., 
        description="The filters for the flight search."
    )

    @field_validator("origin", "destination", "departure_date", "return_date")
    @classmethod
    def _validate_non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 200:
            raise ValueError("Field must be a non-empty string up to 200 characters.")
        return cleaned

    @field_validator("passengers")
    @classmethod
    def _validate_passengers(cls, value: int) -> int:
        if value < 1 or value > 9:
            raise ValueError("passengers must be between 1 and 9.")
        return value
    
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

class FlightsSearchOutput(BaseModel):
    """
    The structure for the final output of the flight search agent.
    """

    flights: List[Flight] = Field(
        ..., 
        description="A list of flights that match the search criteria."
    )