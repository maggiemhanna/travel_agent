# ✈️ Flights Search & Filtering Multi-Agent System

Welcome to the **Flights Search Multi-Agent System**! This project is a modular, event-driven travel platform built with **Google ADK (Agent Development Kit)**, **Google Gemini 2.5**, **FastAPI**, and **React**.

It enables users to search for simulated flights and interactively refine results through a conversational **ChatWidget**—supporting hard parameter filtering, deep semantic filtering with live web research, open-ended travel inspiration, and self-healing JSON correction.

---

## 🏗️ System Architecture

The application is organized into two standalone backend applications (**`flights_search_app`** and **`conversational_app`**) plus an interactive React **`frontend`**.

![Architecture](architecture.png)

---

> **Environment Parity (`localhost` & Google Cloud Run):** The codebase is environment-agnostic. By default, services run locally over `127.0.0.1` (`:8000`–`:8006` and `:5173`), and deploy reproducibly across **`dev`**, **`staging`**, and **`prod`** on **Google Cloud Run** via **Terraform** and **Google Cloud Build**.

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
| **Frontend** (`frontend`) | `5173` | React / Vite / Nginx | **User Interface**: Flight search exploration view with conversational ChatWidget. | [frontend/](frontend/) |

---

## 📁 Repository Structure

```text
travel_agent/
├── .cloudbuild/                 # Google Cloud Build CI/CD Pipelines
│   ├── pr_checks.yaml           # CI pipeline (unit tests, frontend build, terraform validate)
│   ├── dev.yaml                 # CD pipeline for Dev (travel-agent-511710)
│   ├── staging.yaml             # CD pipeline for Staging (travel-agent-staging-512211)
│   └── prod.yaml                # CD pipeline for Prod (travel-agent-prod-512211)
├── deployment/                  # Infrastructure as Code (Terraform) & Deployment Runners
│   ├── bootstrap.sh             # Bootstraps state bucket & meta APIs per GCP project
│   ├── deploy.sh                # One-command CI/CD & Cloud Run deployment runner
│   └── terraform/               # Reusable Terraform stack with dev/staging/prod parity
│       ├── apis.tf              # Declarative GCP API activation
│       ├── iam.tf               # Least-privilege Runtime & CI/CD Service Accounts
│       ├── registry.tf          # Artifact Registry Docker repository
│       ├── cloud_run.tf         # Cloud Run v2 services (flights-search, conversational, frontend)
│       ├── triggers.tf          # Automated Cloud Build Git triggers
│       ├── variables.tf         # Input variables
│       ├── outputs.tf           # Service URLs & registry outputs
│       ├── versions.tf          # Provider versions & GCS remote state backend
│       └── envs/                # Environment-specific configurations (.tfvars)
│           ├── dev.tfvars
│           ├── staging.tfvars
│           └── prod.tfvars
├── flights_search_app/          # Standalone Flights Search ADK Application (:8000)
│   ├── app/                     # Core ADK agent package (agent.py, main.py, prompt.py, schema.py)
│   │   └── app_utils/           # Shared logging and formatting utilities
│   ├── tests/                   # Unit, integration, and E2E test suites
│   ├── Dockerfile               # Production container definition for Cloud Run
│   ├── .env.example             # Example environment variables for flights_search_app
│   ├── pyproject.toml           # Project metadata and pytest configuration
│   ├── requirements.txt         # Pinned runtime Python dependencies
│   └── README.md                # Flights Search App documentation
├── conversational_app/          # Conversational Multi-Agent Application (:8001–8006)
│   ├── app/                     # Main Conversational entrypoint (:8001) (agent.py, main.py, schema.py)
│   │   ├── app_utils/           # Shared logging and formatting utilities
│   │   └── sub_agents/          # Specialized ADK sub-agent services (engage, filter, filter_smart, inspiration, json_parser)
│   ├── tests/                   # Unit, integration, E2E, and GEAP evaluation suites
│   ├── Dockerfile               # Production container definition for Cloud Run
│   ├── .env.example             # Example environment variables for conversational_app
│   ├── pyproject.toml           # Project metadata and pytest configuration
│   ├── requirements.txt         # Pinned runtime Python dependencies
│   └── README.md                # Conversational App & Sub-Agents documentation
└── frontend/                    # React + Vite frontend application & ChatWidget (:5173)
    ├── Dockerfile               # Multi-stage Node build + Nginx runtime with env-config injection
    └── nginx.conf.template      # Cloud Run Nginx template
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

---

## ☁️ CI/CD & Deployment to Google Cloud Run (Terraform + Cloud Build)

The platform uses **Terraform** ([`deployment/terraform/`](deployment/terraform/)) and **Google Cloud Build** ([`.cloudbuild/`](.cloudbuild/)) to maintain reproducible infrastructure and strict environment parity across three isolated GCP projects:

| Environment | GCP Project ID | Terraform Variables | Cloud Build Pipeline | Scaling (`min` / `max`) |
| :--- | :--- | :--- | :--- | :---: |
| **Dev** | `travel-agent-511710` | [`envs/dev.tfvars`](deployment/terraform/envs/dev.tfvars) | [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml) | `0` / `5` |
| **Staging** | `travel-agent-staging-512211` | [`envs/staging.tfvars`](deployment/terraform/envs/staging.tfvars) | [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) | `0` / `10` |
| **Prod** | `travel-agent-prod-512211` | [`envs/prod.tfvars`](deployment/terraform/envs/prod.tfvars) | [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml) | `1` / `20` |

### Least-Privilege Service Account Separation
Zero extra permissions are granted to Google's built-in Cloud Build or default Compute Engine service accounts. Instead, each environment uses three dedicated custom Service Accounts:

| Service Account | Provisioned By | Attached To | Granted Roles |
| :--- | :--- | :--- | :--- |
| `travel-agent-cicd` | [`deployment/bootstrap.sh`](deployment/bootstrap.sh) | Cloud Build pipelines & Git triggers | CI/CD & Terraform deployment roles (`run.admin`, `artifactregistry.admin`, `serviceAccountAdmin`, `projectIamAdmin`, `serviceUsageAdmin`, `storage.admin`, `logging.logWriter`) |
| `travel-agent-runtime` | [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) | `flights-search-app`, `conversational-app` | `aiplatform.user` (Gemini / Vertex AI), `logging.logWriter`, `cloudtrace.agent` |
| `travel-agent-frontend` | [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) | `frontend` | `logging.logWriter` only (**no** Vertex AI or admin access) |

### 1. Run CI Pull Request Checks
Validates backend unit tests (`pytest tests/unit`), frontend production build (`npm ci && npm run build`), and Terraform formatting/schema (`terraform fmt -check && terraform validate`):
```bash
./deployment/deploy.sh pr-check dev
```

### 2. Deploy to `dev`, `staging`, or `prod`
Each deployment automatically bootstraps the remote Terraform state bucket (`gs://<PROJECT_ID>-tfstate`) and dedicated `travel-agent-cicd` Service Account (while stripping any legacy CI/CD roles from built-in Google SAs), runs unit tests, provisions APIs/IAM/Artifact Registry via Terraform, builds & pushes all 3 container images (`flights-search-app`, `conversational-app`, `frontend`) tagged with the Git commit SHA, deploys the Cloud Run v2 services (wiring the backend URLs into `frontend` at runtime), and runs post-deploy HTTP smoke checks:
```bash
# Deploy to Dev (travel-agent-511710)
./deployment/deploy.sh dev

# Deploy to Staging (travel-agent-staging-512211)
./deployment/deploy.sh staging

# Deploy to Production (travel-agent-prod-512211)
./deployment/deploy.sh prod
```

