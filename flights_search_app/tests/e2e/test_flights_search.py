import json
import os
import sys
import requests

from app.app_utils.logging import format_dict_for_logs, setup_logging

logger = setup_logging(name=__name__)

BASE_URL = os.getenv("FLIGHTS_SEARCH_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
FIXTURES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "flights_search.json")


def test_root_endpoint():
    """Test the root health-check endpoint."""
    response = requests.get(f"{BASE_URL}/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}. Details: {response.text}"
    assert response.json() == {"message": "Flights Search Agent Service is running. Use the /run-flights-search endpoint via POST."}


def test_run_flights_search():
    """Test the flights search microservice endpoint and validate the exact JSON structure."""
    with open(FIXTURES_PATH) as f:
        tests = json.load(f)

    for test in tests:
        payload = {
            "origin": test["origin"],
            "destination": test["destination"],
            "departure_date": test["departure_date"],
            "return_date": test["return_date"],
            "passengers": test["passengers"],
            "filters": test["filters"],
        }
        logger.info(f"Payload:\n{format_dict_for_logs(payload)}")

        # Issue the POST request to the deployed microservice endpoint
        response = requests.post(f"{BASE_URL}/run-flights-search", json=payload)

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
        assert "flights" in results, "Expected 'flights' key in the first result"
        assert isinstance(results["flights"], list), "Expected 'flights' value to be a list"
        assert len(results["flights"]) > 0, "Expected at least one flight in the 'flights' list"

        # Check a specific flight's structure
        first_flight = results["flights"][0]
        assert "flight_number" in first_flight, "Missing 'flight_number'"
        assert "price" in first_flight, "Missing 'price'"
        assert "departure_time" in first_flight, "Missing 'departure_time'"
        assert "return_time" in first_flight, "Missing 'return_time'"


# --- Manual Execution Block ---
if __name__ == "__main__":
    logger.info(f"Running e2e microservice tests against {BASE_URL}...")

    try:
        logger.info("Running test_root_endpoint...")
        test_root_endpoint()
        logger.info("✅ test_root_endpoint passed!")

        logger.info("Running test_run_flights_search...")
        # Note: If this hits a real LLM, it might take a few seconds to return.
        test_run_flights_search()
        logger.info("✅ test_run_flights_search passed!")

        logger.info("🎉 All tests completed successfully!")

    except AssertionError as e:
        logger.error(f"❌ Assertion Failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ An unexpected error occurred: {e}")
        sys.exit(1)
