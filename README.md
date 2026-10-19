# ✈️ Flights Search & Filtering Multi-Agent System

Welcome to the **Flights Search Multi-Agent System**! This project is a modular, event-driven travel platform built with **Google ADK (Agent Development Kit)**, **Google Gemini 2.5**, **FastAPI**, and **React**.

It enables users to search for simulated flights and interactively refine results through a conversational **ChatWidget**—supporting hard parameter filtering, deep semantic filtering with live web research, open-ended travel inspiration, and self-healing JSON correction.

---

## 🏗️ System Architecture

The application is organized into two standalone backend applications (**`flights_search_app`** and **`conversational_app`**) plus an interactive React **`frontend`**.

![Architecture](architecture.png)

---

> **Note on Branches:** This branch (`local`) is configured for **local development and testing**, where all microservices and the frontend communicate over `localhost`. For production deployment to **Google Cloud Run**, please refer to the `main` branch.

---

## 🤖 Applications & Microservices Overview

| Application / Service | Port | Model / Tech | Role & Description | Documentation |
| :--- | :---: | :--- | :--- | :---: |
| **Flights Search Agent** (`flights_search_app`) | `8000` | Gemini 3.5 Flash Lite | **Flight Simulator**: Generates 15 realistic, route-appropriate flight options obeying temporal and timezone logic. | [README](flights_search_app/README.md) |
| **Conversational Agent** (`conversational_app/app`) | `8001` | ADK v2 Workflow / FastAPI | **Conversational Workflow**: Entrypoint for the conversational app; triages user requests via `engage` and routes to sub-agents. | [README](conversational_app/README.md#1-conversational-workflow-entrypoint--port-8001) |
| **Engage Sub-Agent** (`sub_agents/engage`) | `8002` | Gemini 3.1 Pro | **Triage Specialist**: Analyzes user intent to route to `continue`, `filter`, `filter_smart`, or `inspiration_agent`. | [README](conversational_app/README.md#2-engage-sub-agent-port-8002) |
| **Filter Sub-Agent** (`sub_agents/filter`) | `8003` | Gemini 3.1 Pro | **Filter Extraction**: Translates natural language into deterministic parameters (`direct`, `max_price`, `max_stops`). | [README](conversational_app/README.md#3-filter-sub-agent-port-8003) |
| **Smart Filter Sub-Agent** (`sub_agents/filter_smart`) | `8004` | Gemini 3.1 Pro + Search | **Semantic Filter**: Evaluates qualitative amenities (WiFi, legroom, aircraft) via contextual reasoning and live Google Search. | [README](conversational_app/README.md#4-smart-filter-sub-agent-port-8004) |
| **Inspiration Sub-Agent** (`sub_agents/inspiration`) | `8005` | Gemini 3.1 Pro | **Discovery Architect**: Suggests destinations and date ranges for open-ended travel requests (*"somewhere sunny in December"*). | [README](conversational_app/README.md#5-inspiration-sub-agent-port-8005) |
| **JSON Parser Sub-Agent** (`sub_agents/json_parser`) | `8006` | Gemini 3.1 Pro | **Structure Corrector**: Repairs malformed JSON outputs and guarantees strict schema compliance. | [README](conversational_app/README.md#6-json-parser-sub-agent-port-8006) |
| **Frontend** (`frontend`) | `5173` | React / Vite | **User Interface**: Flight search exploration view with conversational ChatWidget. | [frontend/](frontend/) |

---

## 📁 Repository Structure

```text
travel_agent/
├── flights_search_app/          # Standalone Flights Search ADK Application (:8000)
│   ├── app/                     # Core ADK agent package (agent.py, main.py, prompt.py, schema.py)
│   │   └── app_utils/           # Shared logging and formatting utilities
│   ├── tests/                   # Unit, integration, and E2E test suites
│   │   ├── fixtures/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   ├── .env                     # Environment variables for flights_search_app
│   ├── pyproject.toml           # Project metadata and pytest configuration
│   ├── requirements.txt         # Python dependencies for flights_search_app
│   └── README.md                # Flights Search App documentation
├── conversational_app/          # Conversational Multi-Agent Application (:8001–8006)
│   ├── app/                     # Main Conversational entrypoint (:8001) (agent.py, main.py, schema.py)
│   │   ├── app_utils/           # Shared logging and formatting utilities
│   │   └── sub_agents/          # Specialized ADK sub-agent services
│   │       ├── engage/          # Intent triage and routing (:8002)
│   │       ├── filter/          # Deterministic parameter extraction (:8003)
│   │       ├── filter_smart/    # Semantic filtering + live Google Search (:8004)
│   │       ├── inspiration/     # Open-ended travel discovery (:8005)
│   │       └── json_parser/     # Self-healing JSON syntax & schema correction (:8006)
│   ├── tests/                   # Unit, integration, and E2E test suites
│   │   ├── fixtures/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   ├── .env                     # Environment variables for conversational_app
│   ├── pyproject.toml           # Project metadata and pytest configuration
│   ├── requirements.txt         # Python dependencies for conversational_app
│   └── README.md                # Conversational App & Sub-Agents documentation
└── frontend/                    # React + Vite frontend application & ChatWidget (:5173)
```

---

## 💻 Running the Application Locally

In this branch, all microservices and the React frontend communicate locally over `127.0.0.1` on their designated ports (`8000`–`8006` and `5173`).

### 1. Prerequisites & Environment Setup
- **Python >= 3.11**
- **Node.js >= 18**
- Authenticate with Google Cloud for Gemini / Vertex AI models:
```bash
gcloud auth application-default login
```

Create and activate a virtual environment, then install dependencies for both applications:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r flights_search_app/requirements.txt -r conversational_app/requirements.txt
```

### 2. Configure Environment Variables (`.env`)
Each backend application loads its configuration automatically via `python-dotenv` from its own `.env` file:
- [`flights_search_app/.env`](flights_search_app/.env)
- [`conversational_app/.env`](conversational_app/.env)

Ensure both `.env` files are configured with your Google Cloud settings:
```dotenv
GOOGLE_CLOUD_PROJECT=travel-agent-511710
GOOGLE_CLOUD_LOCATION=europe-west9
GOOGLE_GENAI_USE_VERTEXAI=TRUE
```

### 3. Start Backend Microservices (Local Uvicorn Servers)

#### Start `flights_search_app` (Port `8000`)
From `flights_search_app/`:
```bash
cd flights_search_app
python3 -m app.main
```

#### Start `conversational_app` Orchestrator & Sub-Agents (Ports `8001`–`8006`)
From `conversational_app/` (in separate terminals or background processes):
```bash
cd conversational_app

# Terminal 1: Main Orchestrator Gateway (Port 8001)
python3 -m app.main

# Terminal 2: Engage Sub-Agent (Port 8002)
python3 -m app.sub_agents.engage.main

# Terminal 3: Filter Sub-Agent (Port 8003)
python3 -m app.sub_agents.filter.main

# Terminal 4: Smart Filter Sub-Agent (Port 8004)
python3 -m app.sub_agents.filter_smart.main

# Terminal 5: Inspiration Sub-Agent (Port 8005)
python3 -m app.sub_agents.inspiration.main

# Terminal 6: JSON Parser Sub-Agent (Port 8006)
python3 -m app.sub_agents.json_parser.main
```

### 4. Start the Frontend (Port `5173`)
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```
Open **`http://localhost:5173`** in your browser to interact with the flight search engine and conversational chat widget.

---

## 🧪 Running Tests Locally

Both [`flights_search_app/tests/`](flights_search_app/tests/) and [`conversational_app/tests/`](conversational_app/tests/) are organized into three test tiers:
- **`tests/unit/`**: Fast, offline tests with mocked LLM/HTTP dependencies (`FastAPI TestClient`).
- **`tests/integration/`**: In-process tests hitting real Gemini/Vertex AI models via `FastAPI TestClient` (no running Uvicorn server required for single-agent tests).
- **`tests/e2e/`**: Live HTTP client tests (`requests.post`) against running local Uvicorn servers (`localhost:8000`–`8006`).

### Test `flights_search_app`
```bash
cd flights_search_app

# Run all tiers (unit, integration, e2e)
python3 -m pytest -v -s

# Run a specific tier
python3 -m pytest tests/unit -v -s
python3 -m pytest tests/integration -v -s
python3 -m pytest tests/e2e -v -s
```

### Test `conversational_app`
```bash
cd conversational_app

# Run all tiers (unit, integration, e2e)
python3 -m pytest -v -s

# Run a specific tier
python3 -m pytest tests/unit -v -s
python3 -m pytest tests/integration -v -s
python3 -m pytest tests/e2e -v -s
```
