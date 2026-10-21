# ✈️ Flights Search & Conversational Multi-Agent Platform

A modular, cloud-native travel search and conversational assistant platform built with **Google ADK (Agent Development Kit v2)**, **Google Gemini on Vertex AI**, **FastAPI**, **React**, **Terraform**, and **Google Cloud Build**.

Users can search simulated global flight itineraries and interactively refine or explore trips through an embedded **ChatWidget**—supporting deterministic parameter filtering, semantic amenity filtering grounded in live Google Search, open-ended destination inspiration, and self-healing JSON repair.

---

## 🏗️ System Architecture

The platform is composed of **three independently deployable services**—**`flights_search_app`**, **`conversational_app`**, and **`frontend`**—with strict environment parity across local development (`127.0.0.1`) and **Google Cloud Run** (`dev`, `staging`, `prod`).

![Architecture](architecture.png)

---

## 🤖 Applications & Agents Overview

All AI model versions, Vertex AI locations, and service endpoints are **externalized via environment configuration** (`app/config.py`, `.env`, and Terraform `.tfvars`) rather than hardcoded.

| Service / Agent | Local Port | Default Model / Tech | Role & Responsibility | Docs |
| :--- | :---: | :--- | :--- | :---: |
| **Flights Search Service** (`flights_search_app`) | `8000` | `gemini-3.5-flash-lite` *(configurable)* | **Flight Simulator**: Generates 15 realistic, route-appropriate flight itineraries obeying timezone, duration, and filter rules. | [README](flights_search_app/README.md) |
| **Conversational Workflow** (`conversational_app/app`) | `8001` | ADK v2 `Workflow` + FastAPI | **Orchestrator Gateway**: Executes the multi-agent graph (`engage` → specialist → `finalize_output`) in-process via `POST /run-conversational`. | [README](conversational_app/README.md#1-conversational-workflow-entrypoint--port-8001) |
| **Engage Sub-Agent** (`sub_agents/engage`) | `8002`* | `gemini-3.5-flash-lite` *(configurable)* | **Intent Triage**: Classifies user messages into `continue`, `filter`, `filter_smart`, or `inspiration_agent`. | [README](conversational_app/README.md#2-engage-sub-agent-port-8002) |
| **Filter Sub-Agent** (`sub_agents/filter`) | `8003`* | `gemini-3.5-flash-lite` *(configurable)* | **Hard Filter Extractor**: Translates natural language into structured filters (`direct`, `max_price`, `max_stops`). | [README](conversational_app/README.md#3-filter-sub-agent-port-8003) |
| **Smart Filter Sub-Agent** (`sub_agents/filter_smart`) | `8004`* | `gemini-3.5-flash-lite` + `google_search` | **Semantic Filter**: Filters flights by airline, time window, aircraft, or amenities (WiFi, legroom) using live Google Search grounding. | [README](conversational_app/README.md#4-smart-filter-sub-agent-port-8004) |
| **Inspiration Sub-Agent** (`sub_agents/inspiration`) | `8005`* | `gemini-3.5-flash-lite` *(configurable)* | **Discovery Architect**: Turns open-ended trip ideas (*"somewhere warm in December"*) into concrete search parameters. | [README](conversational_app/README.md#5-inspiration-sub-agent-port-8005) |
| **JSON Parser Sub-Agent** (`sub_agents/json_parser`) | `8006`* | `gemini-3.5-flash-lite` *(configurable)* | **Self-Healing Repair**: Repairs malformed or markdown-wrapped JSON from `filter_smart` into strict schema compliance. | [README](conversational_app/README.md#6-json-parser-sub-agent-port-8006) |
| **Web Frontend** (`frontend`) | `5173` | React + Vite + Nginx | **User Interface**: Interactive flight search, filters, pagination, and conversational `ChatWidget` with runtime URL injection. | [README](frontend/README.md) |

*\*Note: In standard operation (local & Cloud Run), `conversational_app` (`:8001`) executes all 5 sub-agents in-process inside its ADK v2 `Workflow`. Ports `8002`–`8006` are optional standalone FastAPI servers for isolated sub-agent debugging and component E2E tests.*

---

## ✨ Key Architectural Pillars

- **Modularity & Externalized Configuration**:
  - Centralized config modules ([`flights_search_app/app/config.py`](flights_search_app/app/config.py) and [`conversational_app/app/config.py`](conversational_app/app/config.py)) externalize Gemini model IDs (both global and per-sub-agent overrides), model locations, CORS origins, and service URLs.
  - **Build-Once, Deploy-Anywhere Frontend**: [`frontend/Dockerfile`](frontend/Dockerfile) generates `/env-config.js` (`window.__ENV__`) at Nginx startup from Cloud Run environment variables so the same image works across `dev`, `staging`, and `prod`.
- **Resilience & Graceful Degradation**:
  - **Exponential Backoff Retries**: All 6 AI agents configure `HttpRetryOptions` (`5` attempts, `5s`–`60s` exponential backoff on HTTP `408, 429, 500, 502, 503, 504`).
  - **Self-Healing JSON Fallback**: If `filter_smart`'s Google Search-grounded output fails deterministic JSON parsing, the workflow automatically routes to `json_parser` (`repair_json`) instead of failing the request.
  - **UI Feature Isolation**: Because Flight Search and Chat are decoupled services, an error in `conversational-app` stays contained inside `ChatWidget` while flight search and manual filters keep working.
  - **Timeout & Rollout Safeguards**: Cloud Run services use `300s` request timeouts for multi-step AI turns, zero-downtime revision traffic switching, and automated post-deploy smoke retries.
- **Security & Least-Privilege IAM**:
  - Uses **three isolated custom Service Accounts** per GCP project (`travel-agent-cicd`, `travel-agent-runtime`, `travel-agent-frontend`) and actively strips extra CI/CD roles from Google's built-in default accounts.
  - Zero static API keys (native Vertex AI Workload Identity / ADC), non-root `appuser` (`UID 1000`) backend containers, configurable CORS origins, and production deletion protection.
- **Multi-Tier Testing & AI Evaluation**:
  - **4 testing & quality layers**: fast offline **Unit Tests**, real-LLM in-process **Integration Tests**, live HTTP **End-to-End (E2E) Tests** (targeting `localhost` or Cloud Run), and a **7-metric GEAP AI Evaluation & Loss Analysis Suite** (`tests/eval/`).

---

## 📁 Repository Structure

```text
travel_agent/
├── .cloudbuild/                 # Google Cloud Build CI/CD Pipelines
│   ├── pr_checks.yaml           # Pull Request CI (unit tests, frontend build, terraform fmt/validate)
│   ├── dev.yaml                 # 5-step CD pipeline for Dev (travel-agent-511710)
│   ├── staging.yaml             # 5-step CD pipeline for Staging (travel-agent-staging-512211)
│   └── prod.yaml                # 5-step CD pipeline for Prod (travel-agent-prod-512211)
├── deployment/                  # Infrastructure as Code (Terraform) & Deployment Runners
│   ├── bootstrap.sh             # Provisions state bucket, travel-agent-cicd SA & cleans default SAs
│   ├── deploy.sh                # Unified runner for PR checks and dev/staging/prod deployments
│   └── terraform/               # Single declarative Terraform stack across dev, staging & prod
│       ├── apis.tf              # GCP API enablement (Cloud Run, Vertex AI, Artifact Registry, IAM, etc.)
│       ├── iam.tf               # 3-SA separation (agent_runtime, frontend_runtime, cicd_runner)
│       ├── registry.tf          # Artifact Registry Docker repository + retention policy
│       ├── cloud_run.tf         # Cloud Run v2 services, scaling, model & URL env injection
│       ├── triggers.tf          # Automated Cloud Build Git triggers (PR, main -> staging, v* -> prod)
│       ├── variables.tf         # Input variables (models, scaling, CPU/memory, CORS)
│       ├── outputs.tf           # Deployed Cloud Run URLs & Service Account emails
│       ├── versions.tf          # Provider constraints & GCS remote state backend
│       └── envs/                # Environment-specific configurations (dev, staging, prod .tfvars)
├── flights_search_app/          # Standalone Flights Search ADK Application (:8000)
│   ├── app/                     # ADK agent, FastAPI server, externalized config, prompt & schemas
│   ├── tests/                   # Unit, integration, and E2E test suites + JSON fixtures
│   ├── Dockerfile               # Hardened non-root Python 3.11 container for Cloud Run
│   ├── .env.example             # Template environment & model configuration
│   └── README.md                # Flights Search documentation
├── conversational_app/          # Conversational Multi-Agent Workflow Application (:8001–8006)
│   ├── app/                     # ADK v2 Workflow (:8001), externalized config & 5 sub_agents/
│   ├── tests/                   # Unit, integration, E2E, and 7-metric GEAP evaluation suite (eval/)
│   ├── Dockerfile               # Hardened non-root Python 3.11 container for Cloud Run
│   ├── .env.example             # Template environment, per-agent model & endpoint configuration
│   └── README.md                # Conversational Workflow, Sub-Agents & Evaluation documentation
└── frontend/                    # React + Vite SPA & Nginx Cloud Run Container (:5173 / :8080)
    ├── src/                     # App.jsx (search & filters) and ChatWidget.jsx (conversational UI)
    ├── Dockerfile               # Multi-stage Node build + Nginx runtime /env-config.js injection
    ├── nginx.conf.template      # Cloud Run Nginx SPA & cache-control configuration
    └── README.md                # Frontend & runtime configuration documentation
```

---

## 💻 Running the Application Locally

### 1. Prerequisites & Virtual Environment
- **Python >= 3.11** and **Node.js >= 18**
- Authenticate Application Default Credentials (ADC) for Vertex AI:
```bash
gcloud auth application-default login
```

Create a virtual environment and install backend dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r flights_search_app/requirements.txt -r conversational_app/requirements.txt
```

### 2. Configure Environment Files (`.env`)
Copy `.env.example` to `.env` in each app if not already present:
```bash
cp -n flights_search_app/.env.example flights_search_app/.env
cp -n conversational_app/.env.example conversational_app/.env
cp -n frontend/.env.example frontend/.env
```
Verify `GOOGLE_CLOUD_PROJECT` in both backend `.env` files points to an active GCP project with Vertex AI enabled (e.g., `travel-agent-511710`). You can also override `GEMINI_MODEL`, `FLIGHTS_SEARCH_MODEL`, `CONVERSATIONAL_MODEL`, or individual sub-agent models (`FILTER_SMART_MODEL`, etc.) directly in `.env`.

### 3. Start the Platform (Standard 3-Terminal Setup)

**Terminal 1 — Flights Search Backend (`:8000`):**
```bash
cd flights_search_app
python3 -m app.main
```

**Terminal 2 — Conversational Multi-Agent Workflow (`:8001`):**
```bash
cd conversational_app
python3 -m app.main
```

**Terminal 3 — React Frontend (`:5173`):**
```bash
cd frontend
npm install
npm run dev
```

Open **`http://localhost:5173`** in your browser.

<details>
<summary><b>Optional: Run Individual Sub-Agents as Standalone Microservices (<code>:8002</code>–<code>:8006</code>)</b></summary>

If you want to debug individual sub-agents over HTTP or run sub-agent-specific E2E tests (`tests/e2e/test_<sub_agent>.py`), start them from `conversational_app/`:
```bash
cd conversational_app
python3 -m app.sub_agents.engage.main        # Port 8002
python3 -m app.sub_agents.filter.main        # Port 8003
python3 -m app.sub_agents.filter_smart.main  # Port 8004
python3 -m app.sub_agents.inspiration.main   # Port 8005
python3 -m app.sub_agents.json_parser.main   # Port 8006
```
</details>

---

## 🧪 Testing & AI Evaluation

Both backend applications include structured test suites plus an AI evaluation flywheel in `conversational_app/tests/eval/`:

| Layer | Location | What It Verifies |
| :--- | :--- | :--- |
| **Unit Tests** | `tests/unit/` | Fast, offline health checks, Pydantic schema validation against fixtures, and `422` rejection of invalid requests (runs on every CI/CD build). |
| **Integration Tests** | `tests/integration/` | In-process `FastAPI TestClient` execution with live Vertex AI Gemini calls across both apps and all 5 sub-agents. |
| **End-to-End (E2E) Tests** | `tests/e2e/` | Live HTTP client tests against `localhost` or deployed Cloud Run URLs (via `FLIGHTS_SEARCH_BASE_URL` / `CONVERSATIONAL_BASE_URL`). |
| **AI Evaluation (GEAP)** | `conversational_app/tests/eval/` | 50-case synthetic travel benchmark scored on 7 metrics: task success, trajectory quality, Google Search tool quality, coherence, deterministic schema/non-hallucination (`>= 0.95`), plan alignment, and latency (`<= 15s`). |

```bash
# Run Unit, Integration, or E2E suites
(cd flights_search_app && pytest tests/unit -v)
(cd conversational_app && pytest tests/unit -v)

# Run E2E tests against live Cloud Run deployments
(cd flights_search_app && FLIGHTS_SEARCH_BASE_URL="https://<flights-cloud-run-url>" pytest tests/e2e -v)
(cd conversational_app && CONVERSATIONAL_BASE_URL="https://<conversational-cloud-run-url>" pytest tests/e2e/test_conversational.py -v)

# Run the Conversational GEAP Evaluation Suite
(cd conversational_app && python3 -m tests.eval.scripts.run_evaluation --run-name baseline)
```

---

## ☁️ CI/CD & Google Cloud Run Deployment (Terraform + Cloud Build)

Infrastructure and releases are automated across three isolated GCP projects in `europe-west9` using [`deployment/terraform/`](deployment/terraform/) and [`.cloudbuild/`](.cloudbuild/):

| Environment | GCP Project ID | Config File | Pipeline & Trigger | Scaling (`min` / `max`) |
| :--- | :--- | :--- | :--- | :---: |
| **Pull Requests** | `travel-agent-511710` | — | [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml) — PRs targeting `main` | — |
| **Dev** | `travel-agent-511710` | [`envs/dev.tfvars`](deployment/terraform/envs/dev.tfvars) | [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml) — Active feature iteration | `0` / `5` |
| **Staging** | `travel-agent-staging-512211` | [`envs/staging.tfvars`](deployment/terraform/envs/staging.tfvars) | [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) — Push / merge to `main` | `0` / `10` |
| **Prod** | `travel-agent-prod-512211` | [`envs/prod.tfvars`](deployment/terraform/envs/prod.tfvars) | [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml) — `v*` Git tag + **Manual Approval Gate** | `1` / `20` |

### 5-Stage Automated Delivery Pipeline
Each CD pipeline (`dev.yaml`, `staging.yaml`, `prod.yaml`) runs as the dedicated `travel-agent-cicd` Service Account through 5 stages:
1. **CI Unit Test Gate**: Runs `pytest tests/unit` across both backend applications (PR checks additionally run `npm ci && npm run build` and `terraform fmt -check && terraform validate`).
2. **Targeted Terraform Bootstrap**: Enables required GCP APIs, provisions Artifact Registry, and configures runtime Service Accounts (`travel-agent-runtime` and `travel-agent-frontend`) before images are pushed.
3. **Parallel Container Build & Push**: Builds `flights-search-app`, `conversational-app`, and `frontend` in parallel with Docker layer caching and pushes `:GitSHA` and `:latest` tags.
4. **Zero-Downtime Cloud Run Rollout**: Runs full `terraform apply` (with `-lock-timeout=5m`) to roll out Cloud Run revisions, inject model configurations, and wire backend URLs into `frontend`.
5. **Post-Deploy Smoke Verification**: Pings live health endpoints on both backend services and verifies `/env-config.js` on the live frontend with automatic retries.

### Least-Privilege Service Account Separation
[`deployment/bootstrap.sh`](deployment/bootstrap.sh) strips extra CI/CD permissions from Google's built-in Cloud Build and Compute Engine default service accounts and enforces strict 3-way identity separation:

| Service Account | Provisioned By | Attached To | Permissions |
| :--- | :--- | :--- | :--- |
| `travel-agent-cicd` | [`deployment/bootstrap.sh`](deployment/bootstrap.sh) | Cloud Build pipelines & Git triggers | Terraform & deployment roles (`run.admin`, `artifactregistry.admin`, `serviceAccountAdmin`, `projectIamAdmin`, `serviceUsageAdmin`, `cloudbuild.builds.editor`, `storage.admin`, `logging.logWriter`) |
| `travel-agent-runtime` | [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) | `flights-search-app`, `conversational-app` | `roles/aiplatform.user` (Vertex AI Gemini), `roles/logging.logWriter`, `roles/cloudtrace.agent` |
| `travel-agent-frontend` | [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) | `frontend` | `roles/logging.logWriter` only (**zero** Vertex AI, storage, or admin access) |

### Commands
```bash
# 1. Run Pull Request CI checks (unit tests + frontend build + terraform fmt/validate)
./deployment/deploy.sh pr-check dev

# 2. Bootstrap & deploy to any environment
./deployment/deploy.sh dev
./deployment/deploy.sh staging
./deployment/deploy.sh prod
```
