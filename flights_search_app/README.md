# ✈️ Flights Search Agent Service (`flights_search_app`)

The **Flights Search Agent Service** is an independent microservice built with **Google ADK (Agent Development Kit v2)** and **FastAPI** (default local port **`8000`**, Cloud Run port **`8080`**). It acts as a high-fidelity **Global Flight Data Simulator**, generating realistic airline itineraries from structured user search criteria (`origin`, `destination`, `departure_date`, `return_date`, `passengers`, and optional `filters`).

---

## 🌟 Architecture & Design Highlights

### 1. ADK Agent & Externalized Model Configuration
- **Externalized Primary & Backup Model Selection ([`app/config.py`](app/config.py)):** Uses `FLIGHTS_SEARCH_MODEL` (falling back to `GEMINI_MODEL`, default `gemini-3.5-flash-lite`), `FLIGHTS_SEARCH_FALLBACK_MODEL` (falling back to `FALLBACK_GEMINI_MODEL`, default `gemini-3.6-flash`), and `GEMINI_MODEL_LOCATION` (default `global`). Models can be swapped per environment via `.env` or Terraform `.tfvars` with zero code changes.
- **Low-Latency Structured Execution ([`app/agent.py`](app/agent.py)):** Configured with `BuiltInPlanner(thinking_config=ThinkingConfig(include_thoughts=False, thinking_budget=0))` and `include_contents='none'` for fast, deterministic structured output.
- **Resilience, Retry Policy & Automatic Backup Model Failover:** Configures `HttpRetryOptions` with **5 attempts** and exponential backoff (`5.0s` initial delay, `2.0x` multiplier, `60.0s` max delay) on transient HTTP errors (`408, 429, 500, 502, 503, 504`). If the primary model still fails or raises an upstream Vertex AI exception, `execute_agent_run()` ([`app/main.py`](app/main.py)) automatically fails over to an isolated `fallback_app` running `gemini-3.6-flash` inside a fresh `InMemorySessionService` session.
- **Simulation Rules ([`app/prompt.py`](app/prompt.py)):**
  - Generates 15 realistic flight options per query across budget, standard, and flagship carriers.
  - Obeys route duration, timezone shifts, overnight arrival offsets (`+1` / `+2`), and real multi-airport city codes (e.g., `CDG`/`ORY`, `JFK`/`EWR`, `LHR`/`LGW`).
  - Strictly enforces requested `direct`, `max_price`, and `max_stops` constraints.
- **Strict Pydantic Contracts & Input Boundary Guardrails ([`app/schema.py`](app/schema.py)):** Validates incoming requests via `FlightsSearchInput`—rejecting missing fields, blank/whitespace strings, oversized inputs (`> 4000` characters), out-of-range passenger counts (`< 1` or `> 9`), and negative filter values with `422 Unprocessable Entity` before invoking Gemini—and enforces agent output structure via `FlightsSearchOutput`.

### 2. FastAPI Runtime & Cloud-Native Packaging
- **Stateless Per-Request Isolation ([`app/main.py`](app/main.py)):** Generates an isolated `InMemorySessionService` and unique `session_id` / `user_id` (`uuid4()`) per HTTP request, with safe fallback handling if non-JSON text is returned.
- **Standardized Liveness & Readiness Probes ([`app/app_utils/health.py`](app/app_utils/health.py)):** Exposes `GET /healthz` (lightweight process liveness) and `GET /readyz` (deep readiness checking ADK `App` initialization, `GOOGLE_CLOUD_PROJECT`, and primary/fallback model configuration—returning `HTTP 503` if misconfigured) for Cloud Run `liveness_probe` and `startup_probe` enforcement, while preserving `GET /`.
- **Cross-Cutting ADK Runtime Plugin ([`app/app_utils/telemetry_plugin.py`](app/app_utils/telemetry_plugin.py)):** Registers `ExecutionTelemetryPlugin(BasePlugin)` on the ADK `App` container (`ENABLE_TELEMETRY_PLUGIN=true`) to log execution latency and Gemini prompt/output token counts per flight search invocation.
- **Configurable Server & CORS:** Reads `HOST`, `PORT`, and comma-separated `ALLOWED_ORIGINS` from [`app/config.py`](app/config.py).
- **Hardened Container ([`Dockerfile`](Dockerfile)):** Uses `python:3.11-slim`, runs under an unprivileged `appuser` (`UID 1000`), and executes on Cloud Run under the least-privilege `travel-agent-runtime` Service Account (`roles/aiplatform.user`, `roles/logging.logWriter`, `roles/cloudtrace.agent`).

---

## 📁 Directory Structure

```text
flights_search_app/
├── app/
│   ├── __init__.py
│   ├── agent.py             # Primary & fallback ADK Agent / App definitions (reads models from app/config.py)
│   ├── config.py            # Centralized env configuration (primary/fallback models, host/port, URLs, CORS)
│   ├── main.py              # FastAPI server, /healthz & /readyz probes, CORS & ADK Runner failover execution
│   ├── prompt.py            # System instruction prompt & flight simulation rules
│   ├── schema.py            # Pydantic contracts & input boundary guardrails (Filters, FlightsSearchInput, Flight, FlightsSearchOutput)
│   └── app_utils/           # health.py (/healthz & /readyz), logging.py & telemetry_plugin.py
├── tests/
│   ├── fixtures/            # Sample test payloads (flights_search.json)
│   ├── unit/                # Offline health, readiness, model failover, fault-injection, boundary & brownout tests
│   ├── integration/         # In-process FastAPI TestClient tests with live Gemini calls
│   └── e2e/                 # Live HTTP client tests (configurable via FLIGHTS_SEARCH_BASE_URL)
├── Dockerfile               # Production non-root container image definition
├── .dockerignore            # Excludes local caches/tests from container build context
├── .env.example             # Template environment & model variables
├── pyproject.toml           # Project metadata & pytest configuration
└── requirements.txt         # Pinned runtime Python dependencies
```

---

## ⚙️ Configuration Variables (`.env` / Cloud Run)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `GOOGLE_GENAI_USE_VERTEXAI` | `1` | Enables Vertex AI authentication via Application Default Credentials (ADC). |
| `GOOGLE_CLOUD_PROJECT` | `travel-agent-511710` | Target GCP Project ID for Vertex AI inference. |
| `GOOGLE_CLOUD_LOCATION` | `europe-west9` | Primary GCP region. |
| `FLIGHTS_SEARCH_MODEL` | `GEMINI_MODEL` (`gemini-3.5-flash-lite`) | Primary Gemini model ID used by the `flights_search` agent. |
| `FLIGHTS_SEARCH_FALLBACK_MODEL` | `FALLBACK_GEMINI_MODEL` (`gemini-3.6-flash`) | Automatic backup Gemini model ID invoked if the primary model run fails. |
| `GEMINI_MODEL_LOCATION` | `global` | Vertex AI model endpoint location passed to `Gemini(client_kwargs=...)`. |
| `HOST` / `PORT` | `0.0.0.0` / `8000` | Bind address and port for Uvicorn (`8080` on Cloud Run). |
| `FLIGHTS_SEARCH_BASE_URL` | `http://127.0.0.1:8000` | Target service URL used by `tests/e2e/test_flights_search.py`. |
| `ALLOWED_ORIGINS` | `*` | Comma-separated list of allowed CORS browser origins. |
| `ENABLE_TELEMETRY_PLUGIN` | `true` | Enables the ADK `ExecutionTelemetryPlugin` for per-request latency and token logs. |

---

## 🔌 API Reference

### 1. Health & Readiness Probes — `GET /`, `GET /healthz`, `GET /readyz`
- **`GET /`** *(legacy informational check)*:
  ```json
  {
    "message": "Flights Search Agent Service is running. Use the /run-flights-search endpoint via POST."
  }
  ```
- **`GET /healthz`** *(Cloud Run `liveness_probe`)*:
  ```json
  {
    "status": "ok",
    "service": "flights_search_app"
  }
  ```
- **`GET /readyz`** *(Cloud Run `startup_probe` — returns `HTTP 200` when ready or `HTTP 503` if misconfigured)*:
  ```json
  {
    "status": "ready",
    "service": "flights_search_app",
    "project": "travel-agent-511710",
    "location": "global",
    "primary_model": "gemini-3.5-flash-lite",
    "fallback_model": "gemini-3.6-flash"
  }
  ```

### 2. Search Flights — `POST /run-flights-search`

**Request (`FlightsSearchInput`):**
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

**Response (`FlightsSearchOutput` Envelope):**
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

## 🚀 Running Locally

```bash
cd flights_search_app
cp -n .env.example .env
pip install -r requirements.txt

# Start FastAPI + Uvicorn on port 8000
python3 -m app.main
```

Example request:
```bash
curl -X POST "http://127.0.0.1:8000/run-flights-search" \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "Paris",
    "destination": "New York",
    "departure_date": "2026-05-10",
    "return_date": "2026-05-20",
    "passengers": 1,
    "filters": {"max_price": 900, "max_stops": 1}
  }'
```

---

## 🧪 Testing

Run from `flights_search_app/`:

```bash
# 1. Unit tests (offline health/readiness, model failover, fault-injection, boundary & brownout suites)
python3 -m pytest tests/unit -v -s

# 2. Integration tests (in-process TestClient with live Gemini calls)
python3 -m pytest tests/integration -v -s

# 3. End-to-End tests against local server (http://127.0.0.1:8000)
python3 -m pytest tests/e2e -v -s

# 4. End-to-End tests against a deployed Cloud Run environment
FLIGHTS_SEARCH_BASE_URL="https://flights-search-app-5tqnsbwara-od.a.run.app" python3 -m pytest tests/e2e -v -s
```
