# Travel Agent Platform — Engineer & Operator Onboarding Guide

| Metadata | Value |
| :--- | :--- |
| **Document ID** | `OPS-ONBOARD-001` |
| **Related Docs** | [Operational Hub](operational_documentation.md) · [Deployment Guide](deployment_guide.md) · [Runbooks](runbooks.md) · [Troubleshooting](troubleshooting_guide.md) · [API Docs](api_documentation.md) |
| **Target Audience** | New Backend / AI Engineers, Frontend Engineers, SRE / Platform Operators |
| **Estimated Time to First Local Flight Search & Chat** | **~15 minutes** (once GCP Vertex AI access is active) |

---

## Table of Contents

1. [Progressive Onboarding Roadmap](#1-progressive-onboarding-roadmap)
2. [Workstation Prerequisites & Version Matrix](#2-workstation-prerequisites--version-matrix)
3. [Access & GCP Permissions Request Checklist](#3-access--gcp-permissions-request-checklist)
4. [15-Minute Local Quickstart](#4-15-minute-local-quickstart)
5. [Architectural Mental Model (How the System Works)](#5-architectural-mental-model-how-the-system-works)
6. [Codebase Tour & Where to Change What](#6-codebase-tour--where-to-change-what)
7. [Developer Workflow, Testing Pyramid & Guardrails](#7-developer-workflow-testing-pyramid--guardrails)
8. [First-Week Onboarding Verification Checklist](#8-first-week-onboarding-verification-checklist)

---

## 1. Progressive Onboarding Roadmap

| Phase | Timeframe | Goal | Key Deliverables |
| :--- | :---: | :--- | :--- |
| **Phase 1: Local Boot** | **First 30 Min** | Authenticate ADC, install dependencies, run offline unit tests, and boot all 3 services locally. | Execute a flight search & chat turn at `http://localhost:5173`. |
| **Phase 2: System Fluency** | **Day 1** | Understand the ADK v2 5-agent workflow graph, contract-first OpenAPI governance, and test pyramid. | Run integration/E2E suites, inspect Swagger UI (`/docs`), and trace `ADK Plugin Telemetry` logs. |
| **Phase 3: Production Readiness** | **Week 1** | Master CI/CD promotion, GEAP 7-metric AI evaluation, and multi-region DR drills. | Run `./deployment/deploy.sh pr-check dev`, execute local DR/backup self-tests, and ship first PR. |

---

## 2. Workstation Prerequisites & Version Matrix

Verify the following tools before starting setup:

| Tool | Required Version | Pinned Production Equivalent | Verification Command |
| :--- | :--- | :--- | :--- |
| **Python** | `>= 3.11` (`3.11`–`3.13` supported locally) | `python:3.11-slim` | `python3 --version` |
| **Node.js & npm** | `>= 18.0` (`20.x` recommended) | `node:20-alpine` | `node --version && npm --version` |
| **Google Cloud SDK (`gcloud`)** | `>= 460.0.0` | Cloud Build managed | `gcloud --version` |
| **Git** | `>= 2.30` | — | `git --version` |
| **Docker / Terraform** *(Optional)* | Optional locally | Built & applied remotely in Cloud Build (`terraform:1.9.8`) | — |

---

## 3. Access & GCP Permissions Request Checklist

Request access from your Platform / GCP Project Owner according to your role:

| Role | Target GCP Project(s) | Required IAM Roles | Why It's Needed |
| :--- | :--- | :--- | :--- |
| **All Developers (Local AI Dev)** | `travel-agent-511710` (`dev`) | `roles/aiplatform.user`, `roles/serviceusage.serviceUsageConsumer` | Allows keyless local `gcloud auth application-default login` calls to Vertex AI Gemini & GEAP Eval. |
| **Application Contributor (CI / Dev Deploy)** | `travel-agent-511710` (`dev`) | Above + `roles/cloudbuild.builds.editor`, `roles/iam.serviceAccountUser` (on `travel-agent-cicd`), `roles/run.viewer`, `roles/logging.viewer` | Allows running `./deployment/deploy.sh pr-check dev` and `./deployment/deploy.sh dev`. |
| **SRE / Release Engineer** | `travel-agent-staging-512211`, `travel-agent-prod-512211` | Above + `roles/cloudbuild.builds.approver`, `roles/run.admin`, `roles/storage.admin` (state recovery) | Approving `v*` production releases, executing `RB-01`–`RB-07` runbooks, and running live DR drills. |

---

## 4. 15-Minute Local Quickstart

### Step 1: Clone & Authenticate Keyless Vertex AI Credentials (ADC)
The platform never uses hardcoded Gemini API keys. Authenticate your local Application Default Credentials:
```bash
git clone <REPO_URL> travel_agent
cd travel_agent

gcloud auth login
gcloud auth application-default login
gcloud config set project travel-agent-511710
```

### Step 2: Create Local `.env` Files from Templates
```bash
cp -n flights_search_app/.env.example flights_search_app/.env
cp -n conversational_app/.env.example conversational_app/.env
cp -n frontend/.env.example frontend/.env
```
*(Verify `GOOGLE_CLOUD_PROJECT=travel-agent-511710` in both backend `.env` files, or set it to your sandbox GCP project with `aiplatform.googleapis.com` enabled.)*

### Step 3: Install Backend & Frontend Dependencies
```bash
# Python virtual environment (shared across both backend apps for local convenience)
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r flights_search_app/requirements.txt -r conversational_app/requirements.txt pytest==9.0.2 httpx==0.28.1

# Frontend dependencies
(cd frontend && npm install)
```

### Step 4: Verify Offline Unit Tests (Zero Cloud Calls Needed — `< 10s`)
```bash
(cd flights_search_app && python3 -m pytest tests/unit -v)
(cd conversational_app && python3 -m pytest tests/unit -v)
(cd frontend && npm test)
```

### Step 5: Launch the 3 Services Locally
Open **three terminal tabs** from the repository root (activating `source .venv/bin/activate` in Terminals 1 & 2):

- **Terminal 1 — Flights Search Service (`:8000`):**
  ```bash
  cd flights_search_app && python3 -m app.main
  ```
- **Terminal 2 — Conversational Multi-Agent Workflow (`:8001`):**
  ```bash
  cd conversational_app && python3 -m app.main
  ```
- **Terminal 3 — React Web Frontend (`:5173`):**
  ```bash
  cd frontend && npm run dev
  ```

### Step 6: Smoke-Test Your Local Stack
```bash
# 1. Verify deep readiness probes (HTTP 200)
curl -fsS http://127.0.0.1:8000/readyz | python3 -m json.tool
curl -fsS http://127.0.0.1:8001/readyz | python3 -m json.tool

# 2. Open Interactive Swagger UIs & Web App
# - Web Dashboard : http://localhost:5173
# - Flights Docs  : http://127.0.0.1:8000/docs
# - Chat Docs     : http://127.0.0.1:8001/docs
```

Open **`http://localhost:5173`**, click **Search Flights** (`Paris` → `New York`), then click the **`💬`** chat button and test all four intent branches:
1. **Greeting (`continue`):** *"Hi! What can you help me with?"*
2. **Hard Filter (`filter`):** *"Only direct flights under 700 euros"* → watch top-bar filter controls sync automatically.
3. **Smart Filter + Google Search (`filter_smart`):** *"Which morning flights have reliable Wi-Fi for remote work?"* → watch Terminal 2 log `Google Search Grounding Queries` in the `ADK Plugin Telemetry` table!
4. **Inspiration (`inspiration_agent`):** *"Take me somewhere warm and sunny in December instead"* → watch the search form update and trigger a fresh flight search automatically.

---

## 5. Architectural Mental Model (How the System Works)

Keep five core design principles in mind when working on this codebase:

1. **100% Stateless Per-Request Execution:**
   There is no database or Redis cache. On each search, `flights-search-app` generates 15 simulated itineraries and returns them to the browser (`App.jsx`). When the user chats, `ChatWidget.jsx` sends `user_message`, `conversational_history`, `flights_search_input`, and the current `flights_input` array to `conversational-app`, which spins up an ephemeral `InMemorySessionService` keyed by `uuid4()` and discards it once the response returns.
2. **Graph Orchestration Over Monolithic Prompts (`ADK v2 Workflow`):**
   [`conversational_app/app/agent.py`](../conversational_app/app/agent.py) defines an explicit directed workflow graph:
   - `START` → `engage` (classifies intent into `continue`, `filter`, `filter_smart`, or `inspiration_agent`) → `route_engage`
   - `filter_smart` is the **only** agent equipped with `google_search`. Because Gemini cannot enforce constrained JSON decoding simultaneously with live `google_search` tool calls, `parse_filter_smart` validates the output and automatically routes malformed JSON to `json_parser` (`repair_json`) before `finalize_output`.
3. **Dual-Mode Execution (In-Process vs. Standalone Ports `8002`–`8006`):**
   In production and standard local runs, `conversational_app` (`:8001`) executes all 5 sub-agents in-process with zero internal HTTP calls. However, every sub-agent folder (`app/sub_agents/<name>/main.py`) also defines a standalone FastAPI server (`:8002`–`:8006`) so you can develop, curl, and E2E-test a single specialist in total isolation.
4. **Build-Once, Configure-at-Boot Frontend (`/env-config.js`):**
   `frontend` never hardcodes Cloud Run URLs at `npm run build` time. On Cloud Run startup, `40-generate-env-config.sh` writes `/usr/share/nginx/html/env-config.js` (`window.__ENV__`) from Terraform-injected env vars, enabling transparent client-side cross-region failover (`europe-west9` → `europe-west1`).
5. **Dual-Layer Resilience (Retries → Backup Model → Regional Standby):**
   Every agent retries transient Vertex AI errors 5 times (`HttpRetryOptions`), then fails over to an isolated `fallback_app` (`gemini-3.6-flash`) before ever returning `HTTP 500`.

---

## 6. Codebase Tour & Where to Change What

| Common Engineering Task | Files to Touch | Follow-Up Step |
| :--- | :--- | :--- |
| **Tune intent classification rules** | [`conversational_app/app/sub_agents/engage/prompt.py`](../conversational_app/app/sub_agents/engage/prompt.py) | Run `tests/unit`, `tests/integration/test_red_team.py`, and GEAP eval (`run_evaluation.py`). |
| **Tune Google Search grounding / amenity rules** | [`conversational_app/app/sub_agents/filter_smart/prompt.py`](../conversational_app/app/sub_agents/filter_smart/prompt.py) | Check `tool_use_quality` and `schema_and_contract_valid` in GEAP eval. |
| **Tune flight realism / duration / carrier rules** | [`flights_search_app/app/prompt.py`](../flights_search_app/app/prompt.py) | Run `flights_search_app/tests/integration`. |
| **Add a new conversational sub-agent** | 1. Copy `app/sub_agents/filter/` (`agent.py`, `main.py`, `prompt.py`, `schema.py`)<br/>2. Add port/model vars in [`conversational_app/app/config.py`](../conversational_app/app/config.py)<br/>3. Wire node & edge in [`conversational_app/app/agent.py`](../conversational_app/app/agent.py) (`build_conversational_workflow`) | Export `openapi.json` if `ConversationalOutput` changed; add unit + integration tests. |
| **Modify request/response API fields** | [`flights_search_app/app/schema.py`](../flights_search_app/app/schema.py) & [`conversational_app/app/schema.py`](../conversational_app/app/schema.py) | **Mandatory:** Run `python3 -m app.export_openapi` in both apps ([`RB-08`](runbooks.md#rb-08-intentional-api-schema-change--openapi-31-snapshot-regeneration)). |
| **Change default Gemini models or scaling** | [`deployment/terraform/envs/*.tfvars`](../deployment/terraform/envs/) & `.env.example` | Deploy via `./deployment/deploy.sh <env>`. |
| **Modify Cloud Run probes, CPU/RAM, or IAM** | [`deployment/terraform/cloud_run.tf`](../deployment/terraform/cloud_run.tf), [`iam.tf`](../deployment/terraform/iam.tf) | Validate via `./deployment/deploy.sh pr-check dev`. |
| **Update UI components or cross-region failover** | [`frontend/src/App.jsx`](../frontend/src/App.jsx), [`ChatWidget.jsx`](../frontend/src/ChatWidget.jsx), [`apiClient.js`](../frontend/src/apiClient.js) | Run `(cd frontend && npm test && npm run build)`. |

---

## 7. Developer Workflow, Testing Pyramid & Guardrails

Before opening any Pull Request targeting `main`:

1. **Tier 1 — Offline Unit, Fault-Injection & Contract Tests (Mandatory on every edit):**
   ```bash
   (cd flights_search_app && python3 -m pytest tests/unit -v)
   (cd conversational_app && python3 -m pytest tests/unit -v)
   (cd frontend && npm test && npm run build)
   ```
   > [!IMPORTANT]
   > CI runs [`test_api_versioning_and_contracts.py`](../conversational_app/tests/unit/test_api_versioning_and_contracts.py) on every PR and CD run. If you modify any Pydantic schema or route signature without running `python3 -m app.export_openapi`, **CI will fail Stage 1**.

2. **Tier 2 — Live In-Process Gemini Integration & Red-Team Safety Tests (Run when changing prompts, schemas, or ADK wiring):**
   ```bash
   (cd flights_search_app && python3 -m pytest tests/integration -v)
   (cd conversational_app && python3 -m pytest tests/integration -v)
   ```

3. **Tier 3 — Standalone Sub-Agent Isolation Debugging (Optional):**
   If debugging a single sub-agent (e.g., `filter_smart` on port `8004`):
   ```bash
   # Terminal A
   cd conversational_app && python3 -m app.sub_agents.filter_smart.main
   # Terminal B
   cd conversational_app && python3 -m pytest tests/e2e/test_filter_smart.py -v -s
   ```

4. **Tier 4 — 50-Scenario GEAP Evaluation Suite (Run when changing prompts or models):**
   ```bash
   # Requires extra eval dependencies if not yet installed in .venv: pandas, tqdm, google-cloud-aiplatform
   cd conversational_app
   python3 -m tests.eval.scripts.run_evaluation --run-name my_feature_branch
   ```

5. **Resilience Script Self-Checks:**
   ```bash
   ./deployment/validate_dr.sh --local-self-test
   ./deployment/verify_backups.sh --local-self-test
   ```

---

## 8. First-Week Onboarding Verification Checklist

Track your onboarding completion with these self-verifiable milestones:

- [ ] Authenticated local ADC (`gcloud auth application-default login`) without downloading any service account JSON keys.
- [ ] Passed all offline unit suites across `flights_search_app`, `conversational_app`, and `frontend`.
- [ ] Booted `:8000`, `:8001`, and `:5173` locally and exercised `continue`, `filter`, `filter_smart`, and `inspiration_agent` flows in the browser.
- [ ] Located the `ADK Plugin Telemetry` latency/token/grounding table in your local `conversational_app` terminal output.
- [ ] Inspected live OpenAPI 3.1 docs at `http://127.0.0.1:8000/docs` and `http://127.0.0.1:8001/docs` and observed `X-API-Version: 1.0.0` response headers.
- [ ] Executed `./deployment/validate_dr.sh --local-self-test` and `./deployment/verify_backups.sh --local-self-test` locally.
- [ ] Reviewed [Production Runbooks (`docs/runbooks.md`)](runbooks.md) and [Troubleshooting Guide (`docs/troubleshooting_guide.md`)](troubleshooting_guide.md) prior to joining the on-call rotation.
