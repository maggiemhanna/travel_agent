import json
import os
import sys
from fastapi.testclient import TestClient

from app.app_utils.logging import format_dict_for_logs, setup_logging
from app.sub_agents.inspiration.main import api
from app.sub_agents.inspiration.schema import InspirationInput

logger = setup_logging(name=__name__)

FIXTURES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixtures", "inspiration.json")


def test_root_endpoint():
    """Test the root health-check endpoint."""
    with TestClient(api) as client:
        response = client.get("/")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}. Details: {response.text}"
        assert response.json() == {"message": "Inspiration Agent Service is running. Use the /run-inspiration endpoint via POST."}


def test_inspiration_schema():
    """Test input schema validation against fixtures and reject invalid payloads."""
    with open(FIXTURES_PATH) as f:
        tests = json.load(f)

    with TestClient(api) as client:
        for test in tests:
            payload = {
                "user_message": test["user_message"],
                "conversational_history": test["conversational_history"],
                "flights_search_input": test["flights_search_input"],
            }
            logger.info(f"Validating Payload:\n{format_dict_for_logs(payload)}")

            validated = InspirationInput(**payload)
            assert validated.flights_search_input.origin == test["flights_search_input"]["origin"]
            assert validated.flights_search_input.destination == test["flights_search_input"]["destination"]
            assert validated.user_message == test["user_message"]

        # Verify invalid empty payload is rejected with 422 Unprocessable Entity
        invalid_response = client.post("/run-inspiration", json={})
        assert invalid_response.status_code == 422, f"Expected 422, got {invalid_response.status_code}"


# --- Manual Execution Block ---
if __name__ == "__main__":
    logger.info("Running unit tests manually without pytest...")

    try:
        logger.info("Running test_root_endpoint...")
        test_root_endpoint()
        logger.info("✅ test_root_endpoint passed!")

        logger.info("Running test_inspiration_schema...")
        test_inspiration_schema()
        logger.info("✅ test_inspiration_schema passed!")

        logger.info("🎉 All tests completed successfully!")

    except AssertionError as e:
        logger.error(f"❌ Assertion Failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ An unexpected error occurred: {e}")
        sys.exit(1)
