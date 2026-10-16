from typing import List, Optional
from pydantic import BaseModel, Field

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

class FlightsSearchOutput(BaseModel):
    """
    The structure for the final output of the flight search agent.
    """

    flights: List[Flight] = Field(
        ..., 
        description="A list of flights that match the search criteria."
    )