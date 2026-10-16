import json
import os
import sys
from fastapi.testclient import TestClient

from app.app_utils.logging import format_dict_for_logs, setup_logging
from app.sub_agents.filter.main import api

logger = setup_logging(name=__name__)

FIXTURES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "filter.json")


def test_root_endpoint():
    """Test the root health-check endpoint."""
    with TestClient(api) as client:
        response = client.get("/")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Details: {response.text}"
        assert response.json() == {"message": "Filter Agent Service is running. Use the /run-filter endpoint via POST."}


def test_run_filter():
    """Test the filter endpoint in-process and validate the exact JSON structure."""
    with open(FIXTURES_PATH) as f:
        tests = json.load(f)

    with TestClient(api) as client:
        for test in tests:
            payload = {
                "user_message": test["user_message"],
                "conversational_history": test["conversational_history"],
            }
            logger.info(f"Payload:\n{format_dict_for_logs(payload)}")

            # Issue the POST request to the endpoint
            response = client.post("/run-filter", json=payload)

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

            assert "filter_type" in results, "Expected 'filter_type' key in the first result"
            assert isinstance(results["filter_type"], str), "Expected 'filter_type' value to be a string."
            assert results["filter_type"] == test["expected_filter_type"], f"Expected 'filter_type' value to be {test['expected_filter_type']}, got {results['filter_type']}"

            assert "filter_value" in results, "Missing 'filter_value'"
            assert isinstance(results["filter_value"], int), "Expected 'filter_value' value to be an int."
            assert results["filter_value"] == test["expected_filter_value"], f"Expected 'filter_value' value to be {test['expected_filter_value']}, got {results['filter_value']}"

            assert "filter_response" in results, "Missing 'filter_response'"
            assert isinstance(results["filter_response"], str), "Expected 'filter_response' value to be a string"


# --- Manual Execution Block ---
if __name__ == "__main__":
    logger.info("Running integration tests manually without pytest...")

    try:
        logger.info("Running test_root_endpoint...")
        test_root_endpoint()
        logger.info("✅ test_root_endpoint passed!")

        logger.info("Running test_run_filter...")
        # Note: If this hits a real LLM, it might take a few seconds to return.
        test_run_filter()
        logger.info("✅ test_run_filter passed!")

        logger.info("🎉 All tests completed successfully!")

    except AssertionError as e:
        logger.error(f"❌ Assertion Failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ An unexpected error occurred: {e}")
        sys.exit(1)
