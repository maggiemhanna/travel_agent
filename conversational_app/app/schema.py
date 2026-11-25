from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Flight(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    origin: str = Field(..., description="The origin city for the flight search.")
    destination: str = Field(..., description="The destination city for the flight search.")
    departure_date: str = Field(..., description="The departure date for the flight search.")
    return_date: str = Field(..., description="The return date for the flight search.")
    departure_time: str = Field(..., description="The departure time for the flight search.")
    arrival_time: str = Field(..., description="The arrival time for the flight search.")
    return_time: str = Field(..., description="The return time for the flight search.")
    return_arrival_time: str = Field(..., description="The return arrival time for the flight search.")
    price: str = Field(..., description="The price of the flight.")
    airline: str = Field(..., description="The airline of the flight.")
    flight_number: str = Field(..., description="The flight number of the flight.")
    stops: int = Field(..., ge=0, description="The number of stops on the flight.")
    stopover_cities: List[str] = Field(..., description="The cities where the flight stops.")

    @field_validator("stops")
    @classmethod
    def _validate_stops(cls, value: int) -> int:
        if value < 0:
            raise ValueError("stops must be >= 0.")
        return value


class FlightParams(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    origin: str = Field(
        ..., min_length=1, max_length=200, description="The origin city for the flight search."
    )
    destination: str = Field(
        ..., min_length=1, max_length=200, description="The destination city for the flight search."
    )
    departure_date: str = Field(
        ..., min_length=1, max_length=200, description="The departure date for the flight search."
    )
    return_date: str = Field(
        ..., min_length=1, max_length=200, description="The return date for the flight search."
    )
    passengers: int = Field(
        ..., ge=1, le=9, description="The number of passengers for the flight search."
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

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    session_id: Optional[str] = Field(
        None,
        min_length=1,
        max_length=128,
        description=(
            "Optional server-managed session identifier to continue an existing "
            "multi-turn conversation. Omit to start a new session."
        ),
    )
    user_message: str = Field(
        ..., min_length=1, max_length=4000, description="The message from the user."
    )
    conversational_history: List[str] = Field(
        default_factory=list,
        description=(
            "Optional initial conversation history where each string is formatted as "
            "'role: message' (e.g., 'bot: Hello' or 'user: flights under $500'). "
            "Managed automatically by the backend across turns when session_id is reused."
        ),
    )
    flights_input: List[Flight] = Field(default_factory=list, description="The flights to filter.")
    flights_search_input: FlightParams = Field(..., description="The flights search input.")

    @field_validator("session_id")
    @classmethod
    def _validate_session_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 128:
            raise ValueError("session_id must be a non-empty string up to 128 characters.")
        return cleaned

    @field_validator("user_message")
    @classmethod
    def _validate_user_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 4000:
            raise ValueError("user_message must be a non-empty string up to 4000 characters.")
        return value


class ConversationalOutput(BaseModel):
    """Output schema for the Conversational Agent."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    agent_response: str = Field(..., description="The response from the agent.")
    agent_decision: Literal["filter", "filter_smart", "inspiration", "continue"] = Field(
        ..., description="The decision of the agent."
    )
    filter_type: Optional[Literal["direct", "max_price", "max_stops"]] = Field(
        None, description="The type of filter to apply."
    )
    filter_value: Optional[int] = Field(None, description="The value of the filter to apply.")
    flights_output: Optional[List[Flight]] = Field(None, description="The flights filtered by the smart filter.")
    flights_search_output: Optional[FlightParams] = Field(None, description="The flights search output.")


class ConversationalState(ConversationalInput, ConversationalOutput):
    """State schema for the Conversational Workflow combining ConversationalInput and ConversationalOutput."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    agent_response: Optional[str] = Field(None, description="The response from the agent.")
    agent_decision: Optional[Literal["filter", "filter_smart", "inspiration", "continue"]] = Field(
        None, description="The decision of the agent."
    )


class RawTextFallback(BaseModel):
    """Fallback payload returned when an upstream LLM emits non-JSON plain text."""

    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(..., description="Unparsed plain-text response returned safely when JSON decoding fails.")


class ConversationalResponse(BaseModel):
    """HTTP response envelope for POST /api/v1/run-conversational (and legacy /run-conversational)."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    status: Literal["success"] = Field("success", description="Execution status indicator.")
    session_id: Optional[str] = Field(
        None,
        description="Server-managed session identifier to send on subsequent turns.",
    )
    results: Union[ConversationalOutput, RawTextFallback, Dict[str, Any]] = Field(
        ..., description="Normalized multi-agent workflow output (or graceful plain-text fallback)."
    )


class SessionDeleteResponse(BaseModel):
    """HTTP response payload for DELETE /api/v1/sessions/{session_id}."""

    status: Literal["deleted", "not_found"] = Field(
        ..., description="Whether an active in-memory session was found and deleted."
    )
    session_id: str = Field(..., description="The targeted session identifier.")


class RootInfoResponse(BaseModel):
    """Informational root endpoint banner payload."""

    message: str = Field(..., description="Service status banner message.")
