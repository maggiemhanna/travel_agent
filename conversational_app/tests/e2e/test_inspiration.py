import json
import os
import sys
import requests

from app.app_utils.logging import format_dict_for_logs, setup_logging
from app.config import INSPIRATION_BASE_URL as BASE_URL

logger = setup_logging(name=__name__)

FIXTURES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "inspiration.json")


def test_root_endpoint():
    """Test the root health-check endpoint."""
    response = requests.get(f"{BASE_URL}/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}. Details: {response.text}"
    assert response.json() == {"message": "Inspiration Agent Service is running. Use the /run-inspiration endpoint via POST."}


def test_run_inspiration():
    """Test the inspiration microservice endpoint and validate the exact JSON structure."""
    with open(FIXTURES_PATH) as f:
        tests = json.load(f)

    for test in tests:
        payload = {
            "user_message": test["user_message"],
            "conversational_history": test["conversational_history"],
            "flights_search_input": test["flights_search_input"],
        }
        logger.info(f"Payload:\n{format_dict_for_logs(payload)}")

        # Issue the POST request to the deployed microservice endpoint
        response = requests.post(f"{BASE_URL}/run-inspiration", json=payload)

        # Verify HTTP status code
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Details: {response.text}"

        # Parse JSON
        data = response.json()
        assert data["status"] == "success"

        # Extract the actual agent results from the endpoint envelope
        results = data["results"][0]
        logger.info(f"Agent Response:\n{format_dict_for_logs(results)}")

        # --- User-Defined Assertions ---
        assert isinstance(results, dict), "Expected 'results' to be a dict"
        assert "agent_response" in results, "Expected 'agent_response' key in the first result"
        assert isinstance(results["agent_response"], str), "Expected 'agent_response' value to be a string"

        assert "flights_search_output" in results, "Expected 'flights_search_output' key in the first result"
        flights_search_output = results["flights_search_output"]
        assert isinstance(flights_search_output, dict), "Expected 'flights_search_output' value to be a dict"
        assert "origin" in flights_search_output, "Expected 'origin' key in flights_search_output"
        assert isinstance(flights_search_output["origin"], str), "Expected 'origin' value to be a string"

        assert "destination" in flights_search_output, "Expected 'destination' key in flights_search_output"
        assert isinstance(flights_search_output["destination"], str), "Expected 'destination' value to be a string"


# --- Manual Execution Block ---
if __name__ == "__main__":
    logger.info(f"Running e2e microservice tests against {BASE_URL}...")

    try:
        logger.info("Running test_root_endpoint...")
        test_root_endpoint()
        logger.info("✅ test_root_endpoint passed!")

        logger.info("Running test_run_inspiration...")
        # Note: If this hits a real LLM, it might take a few seconds to return.
        test_run_inspiration()
        logger.info("✅ test_run_inspiration passed!")

        logger.info("🎉 All tests completed successfully!")

    except AssertionError as e:
        logger.error(f"❌ Assertion Failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ An unexpected error occurred: {e}")
        sys.exit(1)
