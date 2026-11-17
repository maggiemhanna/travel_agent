from typing import Any, Dict, List, Literal, Union
from pydantic import BaseModel, ConfigDict, Field

from app.schema import Flight, RawTextFallback

class JSONParserInput(BaseModel):
    """Input schema for the Filter Agent."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    agent_response: str = Field(..., description="The response from the filter_smart agent.")

class JSONParserOutput(BaseModel):
    """Output schema for the Filter Agent."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    agent_response: str = Field(..., description="The response from the agent.")
    flights_output: List[Flight] = Field(..., description="The flights to filter.")


class JSONParserResponse(BaseModel):
    """HTTP response envelope for standalone JSON Parser service."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    status: Literal["success"] = Field("success", description="Execution status indicator.")
    results: List[Union[JSONParserOutput, RawTextFallback, Dict[str, Any]]] = Field(..., description="JSON Parser agent response list.")
