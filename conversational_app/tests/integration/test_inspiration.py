import json
import os
import sys
from fastapi.testclient import TestClient

from app.app_utils.logging import format_dict_for_logs, setup_logging
from app.sub_agents.inspiration.main import api

logger = setup_logging(name=__name__)

FIXTURES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "inspiration.json")


def test_root_endpoint():
    """Test the root health-check endpoint."""
    with TestClient(api) as client:
        response = client.get("/")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Details: {response.text}"
        assert response.json() == {"message": "Inspiration Agent Service is running. Use the /run-inspiration endpoint via POST."}


def test_run_inspiration():
    """Test the inspiration endpoint in-process and validate the exact JSON structure."""
    with open(FIXTURES_PATH) as f:
        tests = json.load(f)

    with TestClient(api) as client:
        for test in tests:
            payload = {
                "origin": test["origin"],
                "destination": test["destination"],
                "departure_date": test["departure_date"],
                "return_date": test["return_date"],
                "passengers": test["passengers"],
                "user_message": test["user_message"],
                "conversational_history": test["conversational_history"],
            }
            logger.info(f"Payload:\n{format_dict_for_logs(payload)}")

            # Issue the POST request to the endpoint
            response = client.post("/run-inspiration", json=payload)

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
            assert "origin" in results, "Expected 'origin' key in the first result"
            assert isinstance(results["origin"], str), "Expected 'origin' value to be a string"

            assert "destination" in results, "Expected 'destination' key in the first result"
            assert isinstance(results["destination"], str), "Expected 'destination' value to be a string"


# --- Manual Execution Block ---
if __name__ == "__main__":
    logger.info("Running integration tests manually without pytest...")

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
