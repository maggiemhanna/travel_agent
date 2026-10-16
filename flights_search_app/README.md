# ✈️ Flights Search Agent Application (`flights_search_app`)

The **Flights Search Agent** is a standalone application built with **Google ADK (Agent Development Kit)** and **FastAPI** (running on port **`8000`**). It acts as a realistic **Global Flight Data Simulator**, generating high-fidelity flight search results based on user-provided travel criteria (origin, destination, dates, passengers, and budget/stop filters).

---

## 🌟 How the Agent & Backend Work

### 1. The Agent Architecture (`Google ADK` + `Gemini 2.5 Flash Lite`)
- **Role:** Acts as a mock flight search engine / simulator producing realistic airline itineraries across budget, standard, and premium carriers.
- **Model:** Powered by Google's `gemini-2.5-flash-lite` through `google-adk`.
- **Planner & Performance:** Configured with `BuiltInPlanner` with thinking disabled (`thinking_budget=0`) for maximum speed, minimal latency, and consistent structured output.
- **Simulation Rules & Temporal Logic:**
  - Generates exactly 15 diverse flight options per query.
  - Accounts for flight duration, time zones, and overnight flights (marking next-day arrivals with `+1` or `+2`).
  - Uses realistic IATA flight numbers, route-appropriate airlines, and multiple city airport codes (e.g., LHR, LGW, STN for London; CDG, ORY for Paris).
  - Strictly adheres to filter criteria such as `max_price`, `max_stops`, or `direct` only.
- **Data Contracts:** Input and output data formats are enforced using **Pydantic** models (`FlightsSearchInput` and `FlightsSearchOutput`).

### 2. The FastAPI Backend Architecture
- **Framework:** FastAPI with Uvicorn ASGI server running on port **`8000`**.
- **Environment Setup:** Loads environment settings (such as `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION`) from [`.env`](.env) on startup using `python-dotenv`.
- **CORS:** Configured to allow cross-origin requests from the React frontend.
- **Per-Request Session Isolation:**
  - For each incoming request, a unique `session_id` and `user_id` are generated using `uuid4()`.
  - An `InMemorySessionService` is instantiated with the initial state containing the user's search parameters.
  - An ADK `Runner` executes the agent with the prompt `"Follow the system instructions."` in debug mode.
  - The model's response parts are extracted and parsed into JSON.

---

## 📁 Directory Structure

```text
flights_search_app/
├── app/
│   ├── __init__.py
│   ├── agent.py             # ADK Agent & App instantiation (gemini-2.5-flash-lite)
│   ├── main.py              # FastAPI backend & Uvicorn entrypoint (Port 8000)
│   ├── prompt.py            # System instruction prompt & simulation rules
│   ├── schema.py            # Pydantic models (Filters, FlightsSearchInput, Flight, FlightsSearchOutput)
│   └── app_utils/           # Shared logging and formatting utilities
├── tests/
│   ├── fixtures/            # Sample JSON payloads (flights_search.json)
│   ├── unit/                # Offline unit tests (mocked ADK Runner)
│   ├── integration/         # In-process integration tests (real Gemini calls via TestClient)
│   └── e2e/                 # Live HTTP microservice tests against localhost:8000
├── .env                     # Environment variables (GOOGLE_CLOUD_PROJECT, etc.)
├── pyproject.toml           # Package metadata & pytest configuration
└── requirements.txt         # Python dependencies
```

---

## 📊 Data Schemas

### Request Model: `FlightsSearchInput`
```json
{
  "origin": "Paris",
  "destination": "New York",
  "departure_date": "2026-05-10",
  "return_date": "2026-05-20",
  "passengers": 1,
  "filters": {
    "direct": false,
    "max_price": 800,
    "max_stops": 1
  }
}
```

### Response Model: `FlightsSearchOutput` (Envelope)
```json
{
  "status": "success",
  "results": [
    {
      "flights": [
        {
          "origin": "Paris (CDG)",
          "destination": "New York (JFK)",
          "departure_date": "2026-05-10",
          "return_date": "2026-05-20",
          "departure_time": "10:30",
          "arrival_time": "13:00",
          "return_time": "17:30",
          "return_arrival_time": "06:45 +1",
          "price": "520 EUR",
          "airline": "Air France",
          "flight_number": "AF006",
          "stops": 0,
          "stopover_cities": []
        }
      ]
    }
  ]
}
```

---

## 🔌 API Endpoints

### 1. Health Check
- **Method:** `GET`
- **Path:** `/`
- **Response:**
  ```json
  {
    "message": "Flights Search Agent Service is running. Use the /run-flights-search endpoint via POST."
  }
  ```

### 2. Run Flight Search
- **Method:** `POST`
- **Path:** `/run-flights-search`
- **Headers:** `Content-Type: application/json`
- **Body:** `FlightsSearchInput`
- **Example cURL:**
  ```bash
  curl -X POST "http://localhost:8000/run-flights-search" \
    -H "Content-Type: application/json" \
    -d '{
      "origin": "Paris",
      "destination": "New York",
      "departure_date": "2026-05-10",
      "return_date": "2026-05-20",
      "passengers": 1,
      "filters": {
        "max_price": 900,
        "max_stops": 1
      }
    }'
  ```

---

## 🚀 Running Locally

### 1. Environment Configuration (`.env`)
Ensure `flights_search_app/.env` is configured:
```dotenv
GOOGLE_CLOUD_PROJECT=travel-agent-511710
GOOGLE_CLOUD_LOCATION=europe-west9
GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

### 2. Installation
From `flights_search_app/`:
```bash
pip install -r requirements.txt
```

### 3. Start the Service (Port `8000`)
From `flights_search_app/`:
```bash
python3 -m app.main
```
Or via Uvicorn:
```bash
uvicorn app.main:api --host 127.0.0.1 --port 8000 --reload
```

---

## 🧪 Testing

Run the test suite from `flights_search_app/` using `pytest` or by invoking individual test modules directly:

```bash
# Run all tests (unit, integration, e2e)
python3 -m pytest -v -s

# 1. Unit tests (offline, mocked LLM)
python3 -m pytest tests/unit -v -s
python3 -m tests.unit.test_flights_search

# 2. Integration tests (in-process TestClient with real Gemini calls)
python3 -m pytest tests/integration -v -s
python3 -m tests.integration.test_flights_search

# 3. End-to-End tests (requires server running on localhost:8000)
python3 -m pytest tests/e2e -v -s
python3 -m tests.e2e.test_flights_search
```
