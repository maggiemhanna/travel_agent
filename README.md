# ✈️ Flights Search & Conversational Multi-Agent Platform

**Flights Search & Conversational Multi-Agent Platform** is a modular, cloud-native travel search and conversational assistant built with **Google ADK (Agent Development Kit v2)**, **Google Cloud Vertex AI (Gemini)**, **Google Search Grounding**, **FastAPI**, **React**, **Terraform**, and **Google Cloud Build**.

Instead of relying on a single monolithic prompt or static form filters, the platform pairs a realistic flight itinerary simulator with a coordinated multi-agent conversational assistant. Through the web dashboard or REST APIs, users can:

- **Search Simulated Global Flights (`POST /api/v1/run-flights-search`)**: Generate 15 realistic flight itineraries per search across budget, standard, and flagship airlines—accounting for real multi-airport city codes, route durations, timezone differences, overnight arrivals, and user filter preferences (direct flights, maximum price, and maximum stops).
- **Refine Trips Through a Conversational Assistant (`POST /api/v1/run-conversational`)**: Chat in natural language with a multi-agent workflow that interprets the user's request alongside their active flight search and routes the turn to the appropriate specialist agent.
- **Apply Direct Filters via Natural Language (`POST /api/v1/run-filter`)**: Convert everyday requests (such as *"show me direct flights under 600 euros"*) into structured price, stop, and direct-flight filters that immediately update the search controls and results on screen.
- **Filter by Qualitative Amenities with Live Google Search (`POST /api/v1/run-filter-smart`)**: Narrow down candidate flights by specific airlines, morning or afternoon departure windows, layover cities, or on-board amenities (such as reliable Wi-Fi for remote work, extra legroom, or in-flight entertainment) verified through live Google Search, backed by an automatic JSON repair step (`POST /api/v1/run-json-parser`) if the response formatting needs cleanup.
- **Explore Open-Ended Travel Ideas (`POST /api/v1/run-inspiration`)**: Turn broad travel goals (such as *"somewhere warm and sunny in December"*) into concrete origin, destination, and date parameters that automatically trigger a fresh flight search in the dashboard.

---

## 📑 Outline

- [**Core Agentic Architecture (Agentic & Multi-Agent Systems)**](#-core-agentic-architecture-agentic--multi-agent-systems)
  - [1. Agent Orchestration (Stateful Multi-Agent Workflow Graph)](#1-agent-orchestration-stateful-multi-agent-workflow-graph)
  - [2. Tool & Function Calling (Conditional Google Search Grounding)](#2-tool--function-calling-conditional-google-search-grounding)
  - [3. Planning & Reasoning Loops (Intent Triage, Constraint Reasoning & Self-Healing Repair)](#3-planning--reasoning-loops-intent-triage-constraint-reasoning--self-healing-repair)
  - [4. Multi-Agent Coordination (Typed State Handoffs, In-Process Execution & Microservice Isolation)](#4-multi-agent-coordination-typed-state-handoffs-in-process-execution--microservice-isolation)
- [**Cloud Architecture & Production Engineering Layers**](#-cloud-architecture--production-engineering-layers)
  - [**I. Cloud Architecture**](#i-cloud-architecture)
    - [1. Cloud Deployment (Cloud Architecture & Google Cloud Services Used)](#1-cloud-deployment-cloud-architecture--google-cloud-services-used)
  - [**II. Operational Excellence**](#ii-operational-excellence)
    - [1. Infrastructure as Code (IaC)](#1-infrastructure-as-code-iac)
    - [2. CI/CD & Deployment](#2-cicd--deployment)
    - [3. Testing & Quality Engineering](#3-testing--quality-engineering)
  - [**III. Designing for Change**](#iii-designing-for-change)
    - [1. Configuration Management](#1-configuration-management)
    - [2. Modularity & Abstraction](#2-modularity--abstraction)
    - [3. Extensibility](#3-extensibility)
    - [4. API Design & Versioning](#4-api-design--versioning)
  - [**IV. Performance & Cost Optimization**](#iv-performance--cost-optimization)
    - [1. Scalability & Elasticity](#1-scalability--elasticity)
    - [2. Resource Efficiency](#2-resource-efficiency)
    - [3. AI Cost Management](#3-ai-cost-management)
  - [**V. Security, Privacy, and Compliance**](#v-security-privacy-and-compliance)
    - [1. Authentication & Authorization](#1-authentication--authorization)
  - [**VI. Reliability & Resilience**](#vi-reliability--resilience)
    - [1. Availability Design](#1-availability-design)
    - [2. Graceful Degradation](#2-graceful-degradation)
    - [3. Failure & Recovery Testing](#3-failure--recovery-testing)
- [**Repository Structure**](#-repository-structure)
- [**Local Setup & Prerequisites**](#-local-setup--prerequisites)
  - [1. Authenticate with Google Cloud & Configure `.env` Files](#1-authenticate-with-google-cloud--configure-env-files)
  - [2. Install Python Backend Dependencies](#2-install-python-backend-dependencies)
  - [3. Install Frontend Dependencies](#3-install-frontend-dependencies)
- [**Running Locally**](#-running-locally)
- [**Deploying to Google Cloud (Terraform + Cloud Build)**](#-deploying-to-google-cloud-terraform--cloud-build)
- [**Testing, AI Evaluation & Verification**](#-testing-ai-evaluation--verification)
  - [1. Offline Unit Test Suites](#1-offline-unit-test-suites)
  - [2. Live In-Process Integration & HTTP End-to-End (E2E) Suites](#2-live-in-process-integration--http-end-to-end-e2e-suites)
  - [3. GEAP 10-Metric AI Quality, Latency & Cost Evaluation Flywheel](#3-geap-10-metric-ai-quality-latency--cost-evaluation-flywheel)
  - [4. Manual API Testing via `curl`](#4-manual-api-testing-via-curl)
  - [5. Interactive Web Dashboard Workflow](#5-interactive-web-dashboard-workflow)
  - [6. Multi-Region Failover & Infrastructure Backup Drills](#6-multi-region-failover--infrastructure-backup-drills)
- [**API, Integration & SDK Documentation (`docs/api_documentation.md`)**](docs/api_documentation.md)
- [**Operational Documentation Hub (`docs/operational_documentation.md`)**](docs/operational_documentation.md)
  - [Deployment & Release Management Guide (`docs/deployment_guide.md`)](docs/deployment_guide.md)
  - [Production Operational Runbooks (`docs/runbooks.md`)](docs/runbooks.md)
  - [Engineer & Operator Onboarding Guide (`docs/onboarding_guide.md`)](docs/onboarding_guide.md)
  - [Symptom-Driven Troubleshooting Guide (`docs/troubleshooting_guide.md`)](docs/troubleshooting_guide.md)

---

## 🧠 Core Agentic Architecture (Agentic & Multi-Agent Systems)

### 1. Agent Orchestration (Stateful Multi-Agent Workflow Graph)
- **Graph-Based Multi-Agent Workflow vs. Single-Prompt Chaining:** Instead of trying to handle every travel request inside a single oversized prompt or hardcoding brittle conditional chains in the web server, the conversational service uses **Google ADK (Agent Development Kit v2)** to orchestrate a directed workflow graph across five specialized sub-agents. Every user message enters through an intent triage agent, branches dynamically to the appropriate specialist, and converges on a single output normalization step.  
  — *Implemented in [`conversational_app/app/agent.py`](conversational_app/app/agent.py) & [`conversational_app/app/schema.py`](conversational_app/app/schema.py)*  
  — *Called in [`conversational_app/app/main.py`](conversational_app/app/main.py)*
- **Dynamic Conditional Routing:** Dedicated routing steps in the workflow inspect the output of each upstream agent to decide which path to take next—returning a conversational follow-up question, extracting hard database filters, filtering itineraries semantically with live web search, suggesting a new destination and travel dates, or routing a malformed response to a JSON repair agent.  
  — *Implemented in [`conversational_app/app/agent.py`](conversational_app/app/agent.py)*
- **Isolated Per-Request Session State:** Every incoming API request runs inside a fresh in-memory session with a unique per-request session and user ID. Two users searching for flights or chatting simultaneously never share state or overwrite each other's active itineraries.  
  — *Implemented in [`flights_search_app/app/main.py`](flights_search_app/app/main.py), [`conversational_app/app/main.py`](conversational_app/app/main.py) & [`conversational_app/app/sub_agents/engage/main.py`](conversational_app/app/sub_agents/engage/main.py)*
- **Focused Context Window Scoping:** Each specialist agent receives only the specific structured inputs required for its role (such as the user's message, conversation history, or candidate flights) rather than accumulating raw intermediate prompt transcripts from earlier agents, keeping prompts small, fast, and focused.  
  — *Implemented in [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py), [`conversational_app/app/sub_agents/engage/agent.py`](conversational_app/app/sub_agents/engage/agent.py), [`conversational_app/app/sub_agents/filter/agent.py`](conversational_app/app/sub_agents/filter/agent.py), [`conversational_app/app/sub_agents/filter_smart/agent.py`](conversational_app/app/sub_agents/filter_smart/agent.py), [`conversational_app/app/sub_agents/inspiration/agent.py`](conversational_app/app/sub_agents/inspiration/agent.py) & [`conversational_app/app/sub_agents/json_parser/agent.py`](conversational_app/app/sub_agents/json_parser/agent.py)*

### 2. Tool & Function Calling (Conditional Google Search Grounding)
- **Live Google Search Grounding for On-Board Amenities:** Standard flight listings contain prices, airlines, and times, but do not indicate whether a carrier's transatlantic Wi-Fi is fast enough for remote work or how comfortable its long-haul cabin is. The Smart Filter specialist is equipped with ADK's built-in **Google Search** tool to look up real-world airline and aircraft reviews before filtering the user's flights.  
  — *Implemented in [`conversational_app/app/sub_agents/filter_smart/agent.py`](conversational_app/app/sub_agents/filter_smart/agent.py) & [`conversational_app/app/sub_agents/filter_smart/prompt.py`](conversational_app/app/sub_agents/filter_smart/prompt.py)*
- **Selective Tool-Calling Rules (When to Search vs. When Not to Search):** To avoid unnecessary external search latency and cost, the Smart Filter specialist follows strict decision rules (verified by the automated tool-use quality judge in the evaluation suite):
  - *Mandatory Web Search:* Must invoke Google Search whenever the user asks about qualitative or on-board amenities (such as Wi-Fi reliability, legroom, seat comfort, food, or in-flight entertainment)—even if a basic boolean flag is present in the flight data.
  - *No Web Search Needed:* Must skip Google Search and filter directly from the session's flight data whenever the user only asks about explicit fields already present in the itinerary list (such as airline name, morning departure times between `06:00` and `12:00`, layover cities, number of stops, or price).  
  — *Implemented in [`conversational_app/app/sub_agents/filter_smart/prompt.py`](conversational_app/app/sub_agents/filter_smart/prompt.py)*  
  — *Verified in [`conversational_app/tests/eval/metrics/custom_metrics.py`](conversational_app/tests/eval/metrics/custom_metrics.py)*
- **Least-Privilege Tool Access Across Agents:** Only the Smart Filter specialist has access to the Google Search tool. All other agents in the platform run without external tools and enforce strict output schemas, preventing unintended web searches during intent routing, basic filtering, or JSON repair.  
  — *Implemented in [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py), [`conversational_app/app/sub_agents/engage/agent.py`](conversational_app/app/sub_agents/engage/agent.py), [`conversational_app/app/sub_agents/filter/agent.py`](conversational_app/app/sub_agents/filter/agent.py), [`conversational_app/app/sub_agents/filter_smart/agent.py`](conversational_app/app/sub_agents/filter_smart/agent.py), [`conversational_app/app/sub_agents/inspiration/agent.py`](conversational_app/app/sub_agents/inspiration/agent.py) & [`conversational_app/app/sub_agents/json_parser/agent.py`](conversational_app/app/sub_agents/json_parser/agent.py)*

### 3. Planning & Reasoning Loops (Intent Triage, Constraint Reasoning & Self-Healing Repair)
- **Prioritized Four-Way Intent Triage:** At the beginning of every chat turn, the Engage specialist evaluates the user's message and conversation history in priority order to classify the request into one of four intents: (1) open-ended destination or date discovery, (2) hard database filtering (price, stops, or direct flights), (3) semantic or amenity-based filtering, or (4) conversational clarification and greetings.  
  — *Implemented in [`conversational_app/app/sub_agents/engage/prompt.py`](conversational_app/app/sub_agents/engage/prompt.py) & [`conversational_app/app/sub_agents/engage/agent.py`](conversational_app/app/sub_agents/engage/agent.py)*
- **Multi-Step Constraint & Consistency Reasoning:** When filtering flights semantically, the Smart Filter specialist follows a four-step reasoning process: (1) separates explicit schedule criteria from soft amenity preferences, (2) narrows the candidate flights using explicit criteria first, (3) researches soft preferences via Google Search, and (4) verifies that every flight number mentioned as kept or removed in its natural-language explanation matches the final returned flight list without modifying prices or inventing flights.  
  — *Implemented in [`conversational_app/app/sub_agents/filter_smart/prompt.py`](conversational_app/app/sub_agents/filter_smart/prompt.py)*
- **Self-Healing JSON Parse-and-Repair Loop:** Because the model cannot enforce strict JSON schema output mode at the same time as it calls the live Google Search tool, the workflow checks the Smart Filter specialist's output as soon as it finishes. If the text contains valid JSON, it passes straight through; if the text contains markdown wrappers or syntax errors, the workflow automatically routes it to a dedicated JSON Parser specialist that repairs the response into valid JSON without altering any flight details.  
  — *Implemented in [`conversational_app/app/agent.py`](conversational_app/app/agent.py), [`conversational_app/app/sub_agents/json_parser/agent.py`](conversational_app/app/sub_agents/json_parser/agent.py) & [`conversational_app/app/sub_agents/json_parser/prompt.py`](conversational_app/app/sub_agents/json_parser/prompt.py)*
- **Fast Single-Pass Planning for Flight Simulation:** Generating 15 flight itineraries from a search form requires adherence to geographic and scheduling rules rather than extended chain-of-thought deliberation. The Flight Search agent disables extra thinking budget overhead so it can generate 15 realistic itineraries (with accurate airport codes, flight durations, and overnight arrival offsets) with low latency.  
  — *Implemented in [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py) & [`flights_search_app/app/prompt.py`](flights_search_app/app/prompt.py)*

### 4. Multi-Agent Coordination (Typed State Handoffs, In-Process Execution & Microservice Isolation)

| Service / Agent | Local Port | Default Model / Tech | Role & Responsibility | Docs |
| :--- | :---: | :--- | :--- | :---: |
| **Flights Search Service** (`flights_search_app`) | `8000` | `gemini-3.5-flash-lite` *(configurable)* | **Flight Simulator**: Generates 15 realistic, route-appropriate flight itineraries obeying timezone, duration, and filter rules via `POST /api/v1/run-flights-search`. | [API](docs/api_documentation.md) |
| **Conversational Workflow** (`conversational_app/app`) | `8001` | ADK v2 `Workflow` + FastAPI | **Orchestrator Gateway**: Executes the multi-agent workflow (`engage` → specialist → output normalization) in-process via `POST /api/v1/run-conversational`. | [API](docs/api_documentation.md) |
| **Engage Sub-Agent** (`sub_agents/engage`) | `8002`* | `gemini-3.5-flash-lite` *(configurable)* | **Intent Triage**: Classifies user messages into `continue`, `filter`, `filter_smart`, or `inspiration`. | [API](docs/api_documentation.md) |
| **Filter Sub-Agent** (`sub_agents/filter`) | `8003`* | `gemini-3.5-flash-lite` *(configurable)* | **Hard Filter Extractor**: Translates natural language into structured filters (`direct`, `max_price`, `max_stops`). | [API](docs/api_documentation.md) |
| **Smart Filter Sub-Agent** (`sub_agents/filter_smart`) | `8004`* | `gemini-3.5-flash-lite` + Google Search | **Semantic & Amenity Filter**: Filters flights by airline, time window, or amenities using live Google Search grounding. | [API](docs/api_documentation.md) |
| **Inspiration Sub-Agent** (`sub_agents/inspiration`) | `8005`* | `gemini-3.5-flash-lite` *(configurable)* | **Discovery Architect**: Turns open-ended trip ideas (*"somewhere warm in December"*) into concrete search parameters. | [API](docs/api_documentation.md) |
| **JSON Parser Sub-Agent** (`sub_agents/json_parser`) | `8006`* | `gemini-3.5-flash-lite` *(configurable)* | **Self-Healing Repair**: Repairs malformed or markdown-wrapped JSON from `filter_smart` into strict schema compliance. | [API](docs/api_documentation.md) |
| **Web Frontend** (`frontend`) | `5173` | React + Vite + Nginx | **User Interface**: Interactive flight search, filters, pagination, and conversational chat assistant. | [README](frontend/README.md) |

*\*Note: In standard operation (local & Cloud Run), `conversational_app` (`:8001`) executes all 5 sub-agents in-process inside its workflow. Ports `8002`–`8006` are optional standalone FastAPI servers for isolated sub-agent debugging and component E2E tests.*

- **Validated State Handoffs Between Agents:** All five conversational sub-agents coordinate through shared, schema-validated state objects so triage decisions, extracted filter values, filtered flight lists, and suggested search parameters pass cleanly from one specialist to the next and are combined into a single unified JSON response.  
  — *Implemented in [`conversational_app/app/schema.py`](conversational_app/app/schema.py), [`conversational_app/app/agent.py`](conversational_app/app/agent.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*
- **In-Process Workflow Execution with Optional Standalone Microservices:** In production on Cloud Run and during standard local runs, all five conversational sub-agents execute in-process inside the main Conversational service (port `8001`), eliminating internal network hops between agents. For isolated debugging and component-level testing, each sub-agent can also be launched as its own standalone HTTP microservice on ports `8002`–`8006`.  
  — *Implemented in [`conversational_app/app/agent.py`](conversational_app/app/agent.py), [`conversational_app/app/main.py`](conversational_app/app/main.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*
- **Cross-Service Synchronization in the Web Interface:** The React chat assistant coordinates between the Conversational service and the Flights Search service based on the workflow's decision—updating the page's filter controls and visible cards when hard filters are returned, displaying Google Search-verified flights when smart filtering runs, or updating the search form and automatically triggering a new flight search when a new destination or date is suggested.  
  — *Implemented in [`frontend/src/ChatWidget.jsx`](frontend/src/ChatWidget.jsx) & [`frontend/src/App.jsx`](frontend/src/App.jsx)*

<br>

<p align="center">
  <img src="./docs/diagrams/agentic_architecture.png" alt="Agentic Architecture" />
</p>

## 🏗 Cloud Architecture & Production Engineering Layers

The platform is engineered for reproducible multi-environment deployment (`dev`, `staging`, `prod`) on **Google Cloud Platform (GCP)** across **6 architectural domains (`I`–`VI`) and 14 production engineering layers**:

| Domain | Layer | Pillars & Focus Areas |
| :--- | :--- | :--- |
| [**I. Cloud Architecture**](#i-cloud-architecture) | [**1. Cloud Deployment**](#1-cloud-deployment-cloud-architecture--google-cloud-services-used) | Three-service Cloud Run setup across separate `dev`, `staging`, and `prod` Google Cloud projects (with warm backup servers in Belgium for `prod`), automatic backend URL wiring, and managed Google Cloud services for compute, AI, live web search, image storage, CI/CD, permissions, and logging |
| [**II. Operational Excellence**](#ii-operational-excellence) | [**1. Infrastructure as Code (IaC)**](#1-infrastructure-as-code-iac) | Version-controlled Terraform setup, versioned multi-region Cloud Storage state backups, automated Terraform runs in Cloud Build, two-step first-run project setup, and identical `dev`/`staging`/`prod` infrastructure files |
| [**II. Operational Excellence**](#ii-operational-excellence) | [**2. CI/CD & Deployment**](#2-cicd--deployment) | Pull Request test checks, 5-stage deployment pipelines across `dev`, `staging`, and `prod` (with a manual approval step on `prod`), zero-downtime Cloud Run updates with automated health checks, and one-command rollbacks to previous releases |
| [**II. Operational Excellence**](#ii-operational-excellence) | [**3. Testing & Quality Engineering**](#3-testing--quality-engineering) | Four-level test pyramid (fast offline unit & prompt-cost checks, live Gemini integration tests, live end-to-end tests, and a 50-scenario 10-check AI quality, speed & cost evaluation suite), automated pipeline test gates, and dedicated tests for every service and specialist agent |
| [**III. Designing for Change**](#iii-designing-for-change) | [**1. Configuration Management**](#1-configuration-management) | External settings for backend services and Terraform, automatic backend URL configuration when the web frontend starts, isolated `dev`/`staging`/`prod` vs. local environments, and feature/infrastructure toggles |
| [**III. Designing for Change**](#iii-designing-for-change) | [**2. Modularity & Abstraction**](#2-modularity--abstraction) | Independent Flight Search, Chat, and Frontend services, 5 self-contained specialist agent folders, strict input/output validation, global and per-agent Gemini model switching, and reusable session setup |
| [**III. Designing for Change**](#iii-designing-for-change) | [**3. Extensibility**](#3-extensibility) | Step-by-step event routing between agents, automatic performance and token-tracking plugins, plug-and-play specialist agent and evaluation folders, and GitHub webhook deployment triggers |
| [**III. Designing for Change**](#iii-designing-for-change) | [**4. API Design & Versioning**](#4-api-design--versioning) | Versioned `/api/v1` API addresses with working legacy URLs and deprecation notices, formal response formats with CI-checked OpenAPI contract files, and safe field updates with matching flight formats across services |
| [**IV. Performance & Cost Optimization**](#iv-performance--cost-optimization) | [**1. Scalability & Elasticity**](#1-scalability--elasticity) | Independent scaling per service, running chat agents together without extra network calls, automatic container scaling (`0–5` dev, `0–10` staging, `2–20` prod Paris + `1–20` warm Belgium backup), configurable CPU/memory, Cloud Run HTTPS load balancing, and global Vertex AI capacity |
| [**IV. Performance & Cost Optimization**](#iv-performance--cost-optimization) | [**2. Resource Efficiency**](#2-resource-efficiency) | Right-sized CPU & memory per service, fast default AI models & lean search/prompt usage, `$0` idle shutdown in `dev`/`staging` with pay-per-request CPU billing, and automatic cleanup of old container images with cached builds and compressed responses |
| [**IV. Performance & Cost Optimization**](#iv-performance--cost-optimization) | [**3. AI Cost Management**](#3-ai-cost-management) | Per-agent token & search tracking, offline Vertex AI & Google Search (`$14/1k` queries) cost calculator, 10-check evaluation cost/token limits with per-agent cost breakdowns, free "what-if" model cost comparisons, caching savings projections, and automatic Pull Request prompt-size & cost checks |
| [**V. Security, Privacy, and Compliance**](#v-security-privacy-and-compliance) | [**1. Authentication & Authorization**](#1-authentication--authorization) | Three separate Service Accounts per project, version-controlled permissions, automatic removal of extra permissions from default Google accounts, non-root backend containers, and keyless Vertex AI authentication with configurable allowed website origins |
| [**VI. Reliability & Resilience**](#vi-reliability--resilience) | [**1. Availability Design**](#1-availability-design) | Always-on backup containers in production, automatic backup Gemini model & safe updates that block broken releases, two-level health checks ("alive" vs. "ready"), and a warm backup region in Belgium with automatic browser failover & one-command regional recovery |
| [**VI. Reliability & Resilience**](#vi-reliability--resilience) | [**2. Graceful Degradation**](#2-graceful-degradation) | Automatic repair of messy JSON replies, safe handling of plain-text replies, separate Flight Search and Chat failure boundaries, 3-step backend address fallback, 5-attempt automatic retries across all 6 agents, and 5-minute backend request timeouts |
| [**VI. Reliability & Resilience**](#vi-reliability--resilience) | [**3. Failure & Recovery Testing**](#3-failure--recovery-testing) | Simulated AI, network & regional outage tests, prompt-safety & flight-price protection checks, automated Paris-to-Belgium failover drills, safe infrastructure state backup restore checks, and multi-user slowdown & incomplete-data testing |

---

## I. Cloud Architecture

### 1. Cloud Deployment (Cloud Architecture & Google Cloud Services Used)

The platform runs as three containerized services on **Google Cloud Run** in Paris (`europe-west9`)—paired in production with warm backup services in Belgium (`europe-west1`)—promoted across three separate Google Cloud projects (**Dev**: `travel-agent-511710`, **Staging**: `travel-agent-staging-512211`, **Prod**: `travel-agent-prod-512211`).

- **1.1 End-to-End Cloud Architecture & Request Routing**
  - **Three Independently Deployed Serverless Services:**
    - **Web Frontend (`frontend`):** Serves the React web app and creates a small startup configuration file with the live primary and backup backend URLs so the browser always knows where to send requests.
    - **Flights Search Service (`flights-search-app`):** Runs the flight search API (`/api/v1/run-flights-search`, plus backward-compatible URLs and health checks) to generate 15 realistic flight itineraries per search.
    - **Conversational Multi-Agent Service (`conversational-app`):** Runs the chat assistant API (`/api/v1/run-conversational`, plus backward-compatible URLs and health checks) to coordinate all five specialist agents inside a single service.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf), [`deployment/terraform/outputs.tf`](deployment/terraform/outputs.tf) & [`deployment/terraform/envs/`](deployment/terraform/envs/)*  
    — *Implemented in [`frontend/Dockerfile`](frontend/Dockerfile), [`flights_search_app/app/main.py`](flights_search_app/app/main.py) & [`conversational_app/app/main.py`](conversational_app/app/main.py)*

- **1.2 Managed Google Cloud Services Used**
  - **Google Cloud Run (Serverless Containers):** Runs `flights-search-app`, `conversational-app`, and `frontend` with automatic HTTPS, startup and ongoing health checks, zero-downtime updates, automatic scaling, warm backup services in Belgium for `prod`, and accidental-deletion protection in `prod`.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*
  - **Google Cloud Vertex AI (Gemini Models & AI Evaluation):** Runs all Gemini AI calls (`gemini-3.5-flash-lite` primary with automatic backup switching to `gemini-3.6-flash`) across all six agents and powers the AI-graded quality checks in the evaluation suite.  
    — *Provisioned in [`deployment/terraform/apis.tf`](deployment/terraform/apis.tf), [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) & [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Implemented in [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py), [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/) & [`conversational_app/tests/eval/scripts/run_evaluation.py`](conversational_app/tests/eval/scripts/run_evaluation.py)*
  - **Google Search Grounding:** Connects the Smart Filter agent to live Google Search results whenever a user asks about real-world airline or cabin amenities (such as Wi-Fi quality or legroom).  
    — *Implemented in [`conversational_app/app/sub_agents/filter_smart/agent.py`](conversational_app/app/sub_agents/filter_smart/agent.py)*
  - **Google Artifact Registry:** Stores private versioned container images for all three services in Paris (`europe-west9`, plus a second independent copy in Belgium `europe-west1` for `prod`) and automatically cleans up older images beyond the 15 most recent versions.  
    — *Provisioned in [`deployment/terraform/registry.tf`](deployment/terraform/registry.tf) & [`deployment/terraform/apis.tf`](deployment/terraform/apis.tf)*
  - **Google Cloud Build:** Runs Pull Request test checks, 5-stage deployment pipelines across `dev`, `staging`, and `prod`, and automated GitHub triggers with a manual approval step for production releases.  
    — *Provisioned in [`deployment/terraform/triggers.tf`](deployment/terraform/triggers.tf) & [`deployment/terraform/apis.tf`](deployment/terraform/apis.tf)*  
    — *Implemented in [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml), [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) & [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml)*
  - **Google Cloud Storage (Terraform State Backup):** Stores versioned infrastructure state backups (`gs://<PROJECT_ID>-tfstate`) in a multi-region European storage bucket, separated per project and environment.  
    — *Provisioned in [`deployment/bootstrap.sh`](deployment/bootstrap.sh) & [`deployment/terraform/versions.tf`](deployment/terraform/versions.tf)*
  - **Google Cloud IAM & Resource Manager:** Controls least-privilege permissions across three dedicated Service Accounts per project (`travel-agent-cicd`, `travel-agent-runtime`, `travel-agent-frontend`).  
    — *Provisioned in [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) & [`deployment/bootstrap.sh`](deployment/bootstrap.sh)*
  - **Google Cloud Logging & Google Cloud Trace:** Collects application logs, deployment pipeline logs, and request timing data.  
    — *Provisioned in [`deployment/terraform/apis.tf`](deployment/terraform/apis.tf) & [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf)*  
    — *Implemented in [`flights_search_app/app/app_utils/logging.py`](flights_search_app/app/app_utils/logging.py) & [`conversational_app/app/app_utils/logging.py`](conversational_app/app/app_utils/logging.py)*

<br>

<p align="center">
  <img src="./docs/diagrams/gcp_cloud_architecture.svg" alt="GCP Cloud Architecture" />
</p>

---

## II. [OPERATIONAL EXCELLENCE]

### 1. Infrastructure as Code (IaC)

All cloud APIs, service accounts, permissions, container storage, Cloud Run services, and automated build triggers are defined in version-controlled Terraform files rather than configured manually in the cloud console:

- **1.1 Pillar 1 — Version-Controlled Terraform Setup & Remote State**
  - **Modular Terraform Configuration:** Separate Terraform files set up all 10 required Google Cloud APIs, the container image registry and cleanup rules, dedicated runtime Service Accounts and permissions, all three Cloud Run services, and GitHub build triggers.  
    — *Provisioned in [`deployment/terraform/apis.tf`](deployment/terraform/apis.tf), [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf), [`deployment/terraform/registry.tf`](deployment/terraform/registry.tf), [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf), [`deployment/terraform/triggers.tf`](deployment/terraform/triggers.tf), [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf), [`deployment/terraform/outputs.tf`](deployment/terraform/outputs.tf) & [`deployment/terraform/versions.tf`](deployment/terraform/versions.tf)*
  - **Remote Versioned State Storage:** Terraform saves its infrastructure state in a dedicated, version-tracked Google Cloud Storage bucket per project. Bucket names and environment folders are passed in at startup so the same Terraform files work across any project without hardcoding names.  
    — *Provisioned in [`deployment/bootstrap.sh`](deployment/bootstrap.sh) & [`deployment/terraform/versions.tf`](deployment/terraform/versions.tf)*  
    — *Called in [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) & [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml)*

- **1.2 Pillar 2 — Automated Terraform Runs in Cloud Build**
  - **No Local Terraform Setup Needed:** All Terraform formatting checks, validation, initial project setup, and Cloud Run deployments run automatically inside Google Cloud Build using a fixed Terraform version (`1.9.8`) under the dedicated deployment account—so developers do not need Terraform installed on their laptops.  
    — *Implemented in [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml), [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml), [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml) & [`deployment/deploy.sh`](deployment/deploy.sh)*

- **1.3 Pillar 3 — Reproducible Environments**
  - **Two-Step First-Run Setup & Automatic URL Wiring:** So brand-new Google Cloud projects deploy cleanly on the very first run, the pipeline first creates the foundational APIs, image registry, and service accounts before building and uploading container images. Once the images are ready, Terraform deploys the backend services and automatically passes their live web addresses to the frontend.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Implemented in [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) & [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml)*
  - **Locked Software Versions & Input Checks:** Every container build and pipeline locks exact tool and runtime versions (Python 3.11, Node 20, Nginx 1.27, Terraform 1.9.8), installs frontend packages from a lockfile for repeatable builds, and checks environment names before making cloud changes.  
    — *Provisioned in [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf)*  
    — *Implemented in [`flights_search_app/Dockerfile`](flights_search_app/Dockerfile), [`conversational_app/Dockerfile`](conversational_app/Dockerfile), [`frontend/Dockerfile`](frontend/Dockerfile) & [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml)*

- **1.4 Pillar 4 — Environment Parity**
  - **One Shared Terraform Setup Across `dev`, `staging` & `prod`:** Development, staging, and production use the exact same Terraform files. Small per-environment settings files (`.tfvars`) control project IDs and scaling limits, while production-only safeguards—like accidental-deletion protection—turn on automatically in `prod`.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf) & [`deployment/terraform/envs/`](deployment/terraform/envs/)*
  - **Build-Once, Run-Anywhere Frontend Image:** The built frontend container has no environment URLs baked into it, so the exact same image can be promoted unchanged from development to staging to production.  
    — *Implemented in [`frontend/Dockerfile`](frontend/Dockerfile) & [`frontend/nginx.conf.template`](frontend/nginx.conf.template)*

> **Note on Unimplemented / Non-Relevant Pillars:**
> - **Pulumi (*Not Implemented — Not Relevant*):** Pulumi is not used because 100% of our Google Cloud infrastructure across `dev`, `staging`, and `prod` is managed with **Terraform** ([`deployment/terraform/*.tf`](deployment/terraform/)), which integrates directly with our versioned Cloud Storage state backups and Cloud Build pipelines.

---

### 2. CI/CD & Deployment

Code checks, container builds, cloud updates, and post-release health checks run automatically through Google Cloud Build pipelines across three separate GCP projects:

| Environment | GCP Project ID | Terraform Vars | Pipeline & Trigger | Scaling (`min` / `max`) |
| :--- | :--- | :--- | :--- | :---: |
| **Pull Requests** | `travel-agent-511710` | — | [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml) — PRs targeting `main` | — |
| **Dev** | `travel-agent-511710` | [`envs/dev.tfvars`](deployment/terraform/envs/dev.tfvars) | [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml) — Active feature iteration | `0` / `5` |
| **Staging** | `travel-agent-staging-512211` | [`envs/staging.tfvars`](deployment/terraform/envs/staging.tfvars) | [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) — Automated on merge to `main` | `0` / `10` |
| **Prod** | `travel-agent-prod-512211` | [`envs/prod.tfvars`](deployment/terraform/envs/prod.tfvars) | [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml) — `v*` Git tag + **Manual Approval Gate** | `2` / `20` *(+ `1` / `20` standby)* |

- **2.1 Pillar 1 — Pipeline Design**
  - **Automated Pull Request Checks:** Runs automatically whenever a Pull Request targets `main` (or manually via `./deployment/deploy.sh pr-check dev`). It runs fast offline tests for both backends and the web frontend, checks the disaster-recovery and backup scripts, verifies that the frontend builds cleanly, and checks that all Terraform files are properly formatted and valid before code can be merged.  
    — *Provisioned in [`deployment/terraform/triggers.tf`](deployment/terraform/triggers.tf)*  
    — *Implemented in [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml) & [`deployment/deploy.sh`](deployment/deploy.sh)*
  - **Five-Stage Delivery Pipeline (`dev`, `staging`, `prod`):**
    1. **Stage 1 — Automated Unit Tests:** Runs offline tests for both backend services and stops the deployment immediately if anything fails.
    2. **Stage 2 — Core Cloud Setup:** Turns on required Google Cloud APIs, creates container image registries (including the Belgium backup registry in production), and sets up the dedicated runtime service accounts.
    3. **Stage 3 — Parallel Container Builds:** Builds all three service containers at the same time (running frontend tests first), reuses previous build steps for speed, and uploads each image tagged with both the Git commit ID and `latest`.
    4. **Stage 4 — Cloud Run Rollout:** Runs Terraform to deploy the new service versions, apply primary and backup AI model settings, and connect the live primary and backup backend URLs to the frontend.
    5. **Stage 5 — Post-Release Health Verification:** Checks that every deployed backend (including Belgium backups in production) is alive and ready, and confirms the frontend loaded its live backend URLs cleanly—retrying automatically while fresh containers finish starting up.  
    — *Implemented in [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml), [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml) & [`deployment/deploy.sh`](deployment/deploy.sh)*
  - **Manual Approval for Production Releases:** Production deployments only start when a release tag (`v*`) is pushed and require a human to approve the release in Cloud Build before anything goes live.  
    — *Provisioned in [`deployment/terraform/triggers.tf`](deployment/terraform/triggers.tf)*

- **2.2 Pillar 2 — Deployment Strategies**
  - **Zero-Downtime Service Updates:** Every deployment creates a brand-new Cloud Run release alongside the old one rather than changing running servers in place. Cloud Run starts the new version and checks its health first, then smoothly switches live traffic over with zero downtime, followed immediately by Stage 5 health checks.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Called in [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) & [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml)*

- **2.3 Pillar 3 — Rollback Support**
  - **One-Command Rollbacks to Previous Releases:** Because every container image is tagged with its exact Git commit ID (and the 15 most recent versions are kept in Artifact Registry), an operator can roll all three services back to any previous release with a single command (`IMAGE_TAG=<previous-git-sha> ./deployment/deploy.sh prod`).  
    — *Provisioned in [`deployment/terraform/registry.tf`](deployment/terraform/registry.tf) & [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Called in [`deployment/deploy.sh`](deployment/deploy.sh)*
  - **Versioned Infrastructure State Recovery:** Because Cloud Storage keeps a history of Terraform state files, operators can restore an earlier infrastructure state if a cloud configuration change causes issues.  
    — *Provisioned in [`deployment/bootstrap.sh`](deployment/bootstrap.sh)*

> **Note on Unimplemented Pillars:**
> - **Gradual Traffic Splitting (Blue/Green & Canary) & Automatic Rollbacks (*Not Implemented — Relevant*):** While Cloud Run performs zero-downtime updates, runs post-release health checks, and supports one-command rollbacks, gradually shifting a small percentage of live users to a new version (canary/blue-green releases) and automatically rolling back on error spikes are not yet implemented and remain valuable future upgrades.

---

### 3. Testing & Quality Engineering

Response accuracy, agent routing, hallucination prevention, speed, and AI cost are verified across four levels of automated testing:

- **3.1 Pillar 1 — Four-Level Testing & AI Evaluation Pyramid**
  - **Tier 1 — Fast Offline Unit Tests:** Runs locally and in CI without calling Google Cloud or spending AI tokens. It checks health endpoints, rejects invalid user inputs, enforces prompt-size and AI cost guardrails, and simulates AI outages, regional failovers, broken JSON repair, and simultaneous users across both backends, all five specialist agents, and the web frontend.  
    — *Implemented in [`flights_search_app/tests/unit/`](flights_search_app/tests/unit/), [`conversational_app/tests/unit/`](conversational_app/tests/unit/) & [`frontend/src/apiClient.test.js`](frontend/src/apiClient.test.js)*
  - **Tier 2 — Live Integration Tests:** Runs the real backend services directly in memory against live Vertex AI Gemini models across Flight Search, the Conversational workflow, all five specialist agents, and adversarial prompt-safety tests—confirming every live AI reply follows its expected format and safety rules.  
    — *Implemented in [`flights_search_app/tests/integration/test_flights_search.py`](flights_search_app/tests/integration/test_flights_search.py), [`conversational_app/tests/integration/test_conversational.py`](conversational_app/tests/integration/test_conversational.py), [`conversational_app/tests/integration/test_engage.py`](conversational_app/tests/integration/test_engage.py), [`conversational_app/tests/integration/test_filter.py`](conversational_app/tests/integration/test_filter.py), [`conversational_app/tests/integration/test_filter_smart.py`](conversational_app/tests/integration/test_filter_smart.py), [`conversational_app/tests/integration/test_inspiration.py`](conversational_app/tests/integration/test_inspiration.py), [`conversational_app/tests/integration/test_json_parser.py`](conversational_app/tests/integration/test_json_parser.py) & [`conversational_app/tests/integration/test_red_team.py`](conversational_app/tests/integration/test_red_team.py)*
  - **Tier 3 — Live End-to-End (E2E) Tests:** Sends real web requests over the network to locally running servers or live Cloud Run URLs to verify that the deployed services are reachable and return valid responses.  
    — *Implemented in [`flights_search_app/tests/e2e/test_flights_search.py`](flights_search_app/tests/e2e/test_flights_search.py), [`conversational_app/tests/e2e/test_conversational.py`](conversational_app/tests/e2e/test_conversational.py), [`conversational_app/tests/e2e/test_engage.py`](conversational_app/tests/e2e/test_engage.py), [`conversational_app/tests/e2e/test_filter.py`](conversational_app/tests/e2e/test_filter.py), [`conversational_app/tests/e2e/test_filter_smart.py`](conversational_app/tests/e2e/test_filter_smart.py), [`conversational_app/tests/e2e/test_inspiration.py`](conversational_app/tests/e2e/test_inspiration.py) & [`conversational_app/tests/e2e/test_json_parser.py`](conversational_app/tests/e2e/test_json_parser.py)*
  - **Tier 4 — 10-Check AI Quality, Speed & Cost Evaluation Suite:** Tests the chat assistant against 50 realistic travel scenarios across 10 automated checks—measuring task completion, whether the right specialist agent was chosen, whether Google Search was used only when needed, answer clarity, strict output format with zero invented flights or altered prices (`>= 95%`), alignment with expected travel plans, response speed (`<= 15s`), total AI + search cost (`<= $15 per 1,000 requests`), model-only token cost (`<= $5 per 1,000 requests`), and total tokens used (`<= 6,000 per request`). It also breaks down costs by agent, estimates caching savings, lets teams test cheaper/stronger models on past runs for free, groups failure causes automatically, and tracks experiment history over time.  
    — *Implemented in [`conversational_app/tests/eval/configs/eval_config.json`](conversational_app/tests/eval/configs/eval_config.json), [`conversational_app/tests/eval/configs/pricing_config.json`](conversational_app/tests/eval/configs/pricing_config.json), [`conversational_app/tests/eval/metrics/cost_estimator.py`](conversational_app/tests/eval/metrics/cost_estimator.py), [`conversational_app/tests/eval/metrics/custom_metrics.py`](conversational_app/tests/eval/metrics/custom_metrics.py), [`conversational_app/tests/eval/scripts/generate_scenarios.py`](conversational_app/tests/eval/scripts/generate_scenarios.py), [`conversational_app/tests/eval/scripts/run_evaluation.py`](conversational_app/tests/eval/scripts/run_evaluation.py) & [`conversational_app/tests/eval/scripts/run_loss_analysis.py`](conversational_app/tests/eval/scripts/run_loss_analysis.py)*

- **3.2 Pillar 2 — Test Automation**
  - **Automated Quality Gates Before & After Deployment:** Every Cloud Build pipeline and frontend container build automatically runs offline unit tests before shipping code or updating cloud infrastructure. Pull Request checks also verify disaster-recovery scripts, frontend compilation, and Terraform validity, while deployment pipelines verify live service health immediately after release.  
    — *Implemented in [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml), [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml), [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml) & [`frontend/Dockerfile`](frontend/Dockerfile)*

- **3.3 Pillar 3 — Test Coverage Across Services & Sub-Agents**
  - **Dedicated Tests for Every Service & Specialist Agent:** Both main backends, all five conversational specialist agents, and the web frontend each have their own offline unit tests, sample test data, live integration tests, and end-to-end tests.  
    — *Implemented in [`flights_search_app/tests/`](flights_search_app/tests/), [`conversational_app/tests/`](conversational_app/tests/) & [`frontend/src/apiClient.test.js`](frontend/src/apiClient.test.js)*

> **Note on Unimplemented Pillars:**
> - **High-Traffic Load Testing, Automated Browser UI Tests & Code-Coverage Gates (*Not Implemented — Relevant*):** While the AI evaluation suite measures response speed (`<= 15s`) across 50 scenarios, dedicated high-traffic load tests (such as Locust or k6), automated browser click-through tests (such as Playwright or Cypress), and minimum code-coverage percentage gates in CI are not yet set up and remain practical future additions.

---

## III. [DESIGNING FOR CHANGE]

### 1. Configuration Management

AI model choices, cloud regions, server ports, allowed website origins, scaling limits, and backend URLs are all kept in external settings rather than hardcoded in application code:

- **1.1 Pillar 1 — Externalized Configuration**
  - **Central Backend Settings:** Each backend loads its settings—such as primary and backup Gemini models (globally or per specialist agent), Vertex AI region, server ports, and allowed website origins—from environment variables in one central configuration file.  
    — *Implemented in [`flights_search_app/app/config.py`](flights_search_app/app/config.py) & [`conversational_app/app/config.py`](conversational_app/app/config.py)*
  - **Flexible Terraform Settings:** Separate settings files per environment control Google Cloud project IDs, primary and backup regions, AI models, scaling limits, CPU/memory sizes, allowed website origins, and GitHub trigger toggles without editing the core Terraform code.  
    — *Provisioned in [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf), [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf) & [`deployment/terraform/envs/`](deployment/terraform/envs/)*
  - **Startup Backend URL Configuration for the Web Frontend:** Web apps normally bake backend addresses into their files at build time—before cloud URLs even exist. Instead, when the frontend container starts on Cloud Run, it reads the live primary and backup backend URLs from Terraform and writes a small uncached startup file (`/env-config.js`) that the browser loads before starting the app.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Implemented in [`frontend/Dockerfile`](frontend/Dockerfile), [`frontend/nginx.conf.template`](frontend/nginx.conf.template), [`frontend/index.html`](frontend/index.html), [`frontend/src/apiClient.js`](frontend/src/apiClient.js), [`frontend/src/App.jsx`](frontend/src/App.jsx) & [`frontend/src/ChatWidget.jsx`](frontend/src/ChatWidget.jsx)*

- **1.2 Pillar 2 — Environment Separation**
  - **Isolated Cloud Projects (`dev`, `staging`, `prod`) vs. Local Development:** On a developer's machine, each service reads a local `.env` file and runs on local ports (`8000`–`8006` and `5173`). In the cloud, `dev` (`travel-agent-511710`), `staging` (`travel-agent-staging-512211`), and `prod` (`travel-agent-prod-512211`) run in completely separate Google Cloud projects with their own state storage, scaling rules, and safety protections.  
    — *Provisioned in [`deployment/bootstrap.sh`](deployment/bootstrap.sh), [`deployment/deploy.sh`](deployment/deploy.sh) & [`deployment/terraform/envs/`](deployment/terraform/envs/)*  
    — *Implemented in [`flights_search_app/.env.example`](flights_search_app/.env.example), [`conversational_app/.env.example`](conversational_app/.env.example) & [`frontend/.env.example`](frontend/.env.example)*

- **1.3 Pillar 3 — Feature & Infrastructure Flags**
  - **On/Off Toggles for Cloud Features:** Simple true/false settings let operators control two-step initial project setup, turn warm Belgium backup servers on or off, enable or disable automated GitHub triggers, control public web access, and enforce accidental-deletion protection in production.  
    — *Provisioned in [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf), [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf) & [`deployment/terraform/triggers.tf`](deployment/terraform/triggers.tf)*

> **Note on Unimplemented Pillars:**
> - **Live Remote Feature Flags (*Not Implemented — Relevant*):** Toggles currently come from Cloud Run environment settings, which require a quick service update to change in production. Adding a live feature-flag service (such as Firebase Remote Config or OpenFeature) for instant per-user rollouts without redeploying is a useful future enhancement.

---

### 2. Modularity & Abstraction

The platform separates services cleanly, enforces strict data formats, allows swapping AI models without code changes, and keeps agent logic reusable across environments:

- **2.1 Pillar 1 — Loose Coupling**
  - **Three Independent Services:** Flight Search, the Conversational Assistant, and the Web Frontend each live in their own folder with their own container setup, package lists, settings, and tests—sharing no code imports or databases between them.  
    — *Implemented in [`flights_search_app/`](flights_search_app/), [`conversational_app/`](conversational_app/) & [`frontend/`](frontend/)*
  - **Self-Contained Specialist Agent Folders:** Each of the five chat specialists (`engage`, `filter`, `filter_smart`, `inspiration`, `json_parser`) keeps its own instructions, data rules, agent setup, and optional standalone server in a separate folder—so editing one specialist never breaks the others.  
    — *Implemented in [`conversational_app/app/sub_agents/engage/`](conversational_app/app/sub_agents/engage/), [`conversational_app/app/sub_agents/filter/`](conversational_app/app/sub_agents/filter/), [`conversational_app/app/sub_agents/filter_smart/`](conversational_app/app/sub_agents/filter_smart/), [`conversational_app/app/sub_agents/inspiration/`](conversational_app/app/sub_agents/inspiration/) & [`conversational_app/app/sub_agents/json_parser/`](conversational_app/app/sub_agents/json_parser/)*

- **2.2 Pillar 2 — Clear Data Contracts**
  - **Upfront Input & Output Validation:** Every web endpoint and AI agent defines the exact fields it accepts and returns—checking search parameters, flight lists, routing decisions, and filter values upfront and immediately rejecting malformed requests before calling Gemini.  
    — *Implemented in [`flights_search_app/app/schema.py`](flights_search_app/app/schema.py), [`conversational_app/app/schema.py`](conversational_app/app/schema.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*

- **2.3 Pillar 3 — Model Swappability**
  - **Global & Per-Agent Gemini Model Switching:** Because model names come from configuration rather than code, operators can switch the default Gemini model across a whole service or upgrade just one specialist (for example, giving only the Smart Filter agent a stronger model while keeping quick intent routing on `gemini-3.5-flash-lite`) via `.env` or Terraform settings with zero code changes.  
    — *Provisioned in [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf) & [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Implemented in [`flights_search_app/app/config.py`](flights_search_app/app/config.py), [`conversational_app/app/config.py`](conversational_app/app/config.py), [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*  
    — *Verified in [`conversational_app/tests/eval/results/experiments_history.md`](conversational_app/tests/eval/results/experiments_history.md)*

- **2.4 Pillar 4 — Reusable Agent & Session Setup**
  - **Same Agent Code Across Live API, Tests & Evaluations:** Rather than tying AI agents directly to the web server, each request passes a fresh temporary session into the agent runner, and specialist agents plug into the main workflow as reusable building blocks. This lets the exact same agent code run unchanged in production, automated integration tests, and batch AI evaluations.  
    — *Implemented in [`flights_search_app/app/main.py`](flights_search_app/app/main.py), [`conversational_app/app/main.py`](conversational_app/app/main.py), [`conversational_app/app/agent.py`](conversational_app/app/agent.py) & [`conversational_app/tests/eval/scripts/run_evaluation.py`](conversational_app/tests/eval/scripts/run_evaluation.py)*

> **Note on Unimplemented Pillars:**
> - **Swappable Mock AI Models for Offline Testing (*Not Implemented — Relevant*):** While session and runner setup is already reusable, allowing API routes to swap in fake offline AI responses during unit tests without calling Vertex AI is a useful future improvement.

---

### 3. Extensibility

New specialist agents, external tools, evaluation checks, and deployment pipelines can be added without rewriting existing services:

- **3.1 Pillar 1 — Step-by-Step Workflow Routing**
  - **Transparent Event Routing Between Agents:** Inside the chat workflow, each routing step passes an event naming which specialist agent should run next along with the updated conversation data. These step-by-step events stream in real time so the evaluation suite can see which agents ran, whether Google Search was used, and how long each step took.  
    — *Implemented in [`conversational_app/app/agent.py`](conversational_app/app/agent.py), [`conversational_app/app/main.py`](conversational_app/app/main.py) & [`conversational_app/tests/eval/scripts/run_evaluation.py`](conversational_app/tests/eval/scripts/run_evaluation.py)*

- **3.2 Pillar 2 — Plugin Patterns**
  - **Automatic Performance & Token-Tracking Plugin:** Both backend services use a shared monitoring plugin (which can be turned on or off in settings) that automatically watches the start, finish, and failure of every AI agent and model call. Keeping concurrent users completely separate, it records response times, token counts, and Google Search queries without cluttering individual agent code with manual logging.  
    — *Implemented in [`conversational_app/app/app_utils/telemetry_plugin.py`](conversational_app/app/app_utils/telemetry_plugin.py), [`flights_search_app/app/app_utils/telemetry_plugin.py`](flights_search_app/app/app_utils/telemetry_plugin.py), [`conversational_app/app/agent.py`](conversational_app/app/agent.py), [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*  
    — *Verified in [`conversational_app/tests/unit/test_conversational.py`](conversational_app/tests/unit/test_conversational.py) & [`flights_search_app/tests/unit/test_flights_search.py`](flights_search_app/tests/unit/test_flights_search.py)*
  - **Plug-and-Play Specialist Agents & Tools:** Every conversational specialist uses the same four-file folder layout—separating its AI setup, instructions, data formats, and optional standalone server. Adding a new specialist (such as a hotel or baggage assistant) only requires adding a new folder, connecting it as a workflow branch, and optionally giving it tools like Google Search.  
    — *Implemented in [`conversational_app/app/agent.py`](conversational_app/app/agent.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*
  - **Plug-and-Play Evaluation Checks:** Automated rule-based checks and AI-graded quality scores live in a central registry inside the evaluation suite, so teams can add new checks and turn them on or off from a simple JSON config file without changing the main evaluation script.  
    — *Implemented in [`conversational_app/tests/eval/metrics/custom_metrics.py`](conversational_app/tests/eval/metrics/custom_metrics.py) & [`conversational_app/tests/eval/configs/eval_config.json`](conversational_app/tests/eval/configs/eval_config.json)*

- **3.3 Pillar 3 — Automated GitHub Triggers**
  - **Webhook-Driven Cloud Build Triggers:** Terraform sets up Cloud Build triggers that listen for GitHub Pull Requests and code pushes to start test checks and deployments automatically.  
    — *Provisioned in [`deployment/terraform/triggers.tf`](deployment/terraform/triggers.tf)*

> **Note on Unimplemented Pillars:**
> - **Cloud Message Queues (Pub/Sub / Eventarc) & Outbound User Notifications (*Not Implemented — Relevant*):** While agents pass events inside the workflow, a monitoring plugin tracks activity, and GitHub triggers start deployments automatically, an external cloud message queue (such as Google Cloud Pub/Sub or Eventarc) and outbound user notifications (for example, background flight price alerts) are not yet set up and remain useful future additions.

---

### 4. API Design & Versioning

Because Flight Search, the Conversational Assistant, and the Web Frontend deploy independently across Paris and Belgium—and users with already-open browser tabs pass flight results directly between services—all web APIs use versioned addresses, saved API contract files, and safe rules for adding new fields over time:

- **4.1 Pillar 1 — Backward Compatibility**
  - **Versioned `/api/v1` Addresses Alongside Working Legacy URLs:** Both main backends and all five standalone specialist servers expose their endpoints under `/api/v1` while keeping the original `/run-*` addresses connected to the exact same logic. While the web app calls `/api/v1/run-*`, already-open browser tabs, test scripts, and failover drills using older `/run-*` URLs keep working without interruption.  
    — *Implemented in [`flights_search_app/app/main.py`](flights_search_app/app/main.py), [`conversational_app/app/main.py`](conversational_app/app/main.py), [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/), [`frontend/src/apiClient.js`](frontend/src/apiClient.js), [`frontend/src/App.jsx`](frontend/src/App.jsx) & [`frontend/src/ChatWidget.jsx`](frontend/src/ChatWidget.jsx)*  
    — *Verified in [`flights_search_app/tests/unit/test_api_versioning_and_contracts.py`](flights_search_app/tests/unit/test_api_versioning_and_contracts.py), [`conversational_app/tests/unit/test_api_versioning_and_contracts.py`](conversational_app/tests/unit/test_api_versioning_and_contracts.py) & [`frontend/src/apiClient.test.js`](frontend/src/apiClient.test.js)*
  - **Version & Deprecation Notices on Responses:** Every backend reply includes an API version header (`X-API-Version: 1.0.0`), and calls to older `/run-*` URLs automatically include standard deprecation headers pointing callers to the `/api/v1` address—without changing the response body.  
    — *Implemented in [`flights_search_app/app/app_utils/versioning.py`](flights_search_app/app/app_utils/versioning.py) & [`conversational_app/app/app_utils/versioning.py`](conversational_app/app/app_utils/versioning.py)*
  - **Safe Defaults for Optional Fields:** Optional inputs—such as search filters or empty chat history and flight lists on a user's first message—default to empty values automatically instead of failing with a validation error when omitted.  
    — *Implemented in [`flights_search_app/app/schema.py`](flights_search_app/app/schema.py), [`conversational_app/app/schema.py`](conversational_app/app/schema.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*

- **4.2 Pillar 2 — Contract-First Design**
  - **Formal Response & Health-Check Formats:** Rather than returning unstructured JSON, every endpoint defines its exact response format—covering normal AI replies, safe plain-text fallbacks, and healthy/unhealthy status checks—so every possible reply is clearly documented.  
    — *Implemented in [`flights_search_app/app/schema.py`](flights_search_app/app/schema.py), [`conversational_app/app/schema.py`](conversational_app/app/schema.py), [`flights_search_app/app/app_utils/health.py`](flights_search_app/app/app_utils/health.py) & [`conversational_app/app/app_utils/health.py`](conversational_app/app/app_utils/health.py)*
  - **OpenAPI Contract Files Checked Automatically in CI:** Both backends save their complete **OpenAPI 3.1** API specification in Git (`openapi.json`). Automated tests on every Pull Request and deployment compare the live API against the saved contract file, catching accidental breaking changes before containers are built.  
    — *Implemented in [`flights_search_app/openapi.json`](flights_search_app/openapi.json), [`conversational_app/openapi.json`](conversational_app/openapi.json), [`flights_search_app/app/export_openapi.py`](flights_search_app/app/export_openapi.py), [`conversational_app/app/export_openapi.py`](conversational_app/app/export_openapi.py) & [`docs/api_documentation.md`](docs/api_documentation.md)*  
    — *Verified in [`flights_search_app/tests/unit/test_api_versioning_and_contracts.py`](flights_search_app/tests/unit/test_api_versioning_and_contracts.py), [`conversational_app/tests/unit/test_api_versioning_and_contracts.py`](conversational_app/tests/unit/test_api_versioning_and_contracts.py) & [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml)*

- **4.3 Pillar 3 — Safe Data Evolution**
  - **Ignoring Unknown New Fields & Accepting Shorthand Names:** Incoming requests safely ignore unfamiliar extra fields sent by newer clients during rolling updates (while keeping Gemini's output rules strict), and accept shorthand filter names (`price` and `stops`) alongside `max_price` and `max_stops` so minor naming differences never break callers.  
    — *Implemented in [`flights_search_app/app/schema.py`](flights_search_app/app/schema.py) & [`conversational_app/app/schema.py`](conversational_app/app/schema.py)*
  - **Shared Flight Formats Across Services & Specialists:** Inside the Conversational service, all specialist agents share one central definition for flight cards and search parameters rather than keeping duplicate copies, and automated tests confirm that flights produced by Flight Search always match what the Conversational service expects.  
    — *Implemented in [`conversational_app/app/schema.py`](conversational_app/app/schema.py), [`conversational_app/app/sub_agents/filter_smart/schema.py`](conversational_app/app/sub_agents/filter_smart/schema.py), [`conversational_app/app/sub_agents/inspiration/schema.py`](conversational_app/app/sub_agents/inspiration/schema.py) & [`conversational_app/app/sub_agents/json_parser/schema.py`](conversational_app/app/sub_agents/json_parser/schema.py)*  
    — *Verified in [`flights_search_app/tests/unit/test_api_versioning_and_contracts.py`](flights_search_app/tests/unit/test_api_versioning_and_contracts.py) & [`conversational_app/tests/unit/test_api_versioning_and_contracts.py`](conversational_app/tests/unit/test_api_versioning_and_contracts.py)*

> **Note on Unimplemented / Non-Relevant Pillars:**
> - **Database Schema Migrations (*Not Implemented — Not Relevant*):** Database migration tools (such as Alembic or Flyway) do not apply because none of the services store records in a database—all flight lists and chat messages are sent in each request and processed in temporary memory.
> - **Running Multiple Major API Versions (`v1` + `v2`) & External API Gateways (*Not Implemented — Relevant*):** While `/api/v1` URLs and legacy `/run-*` aliases protect rolling updates and existing scripts, running separate `v1` and `v2` business logic side-by-side or placing an external API gateway (such as Google Cloud API Gateway or Apigee) in front for third-party developer keys and rate quotas remains a future step if public partner APIs are opened.

---

## IV. [PERFORMANCE & COST OPTIMIZATION]

### 1. Scalability & Elasticity

The platform separates flight generation from multi-step chat reasoning, runs chat sub-agents together inside one service to avoid extra network delays, and scales automatically across Cloud Run and global Vertex AI capacity:

- **1.1 Pillar 1 — Horizontal & Vertical Scaling Strategies**
  - **Independent Scaling per Service:** Running Flight Search (`flights-search-app`), the Conversational Assistant (`conversational-app`), and the Web Frontend (`frontend`) as three separate Cloud Run services lets each one add or remove containers based on its own traffic without competing for CPU or memory.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*
  - **Configurable CPU & Memory per Container:** CPU and memory limits for each container (`2 vCPU / 2 GiB` for the Python AI backends and `1 vCPU / 512 MiB` for the web frontend) are controlled through Terraform settings so capacity can be adjusted per environment without changing code.  
    — *Provisioned in [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf), [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf) & [`deployment/terraform/envs/`](deployment/terraform/envs/)*

- **1.2 Pillar 2 — Environment-Tiered Autoscaling Policies**
  - **Environment-Specific Minimum & Maximum Container Counts:** Cloud Run automatically adds or removes containers based on live traffic using limits tailored to each environment:
    - **Dev ([`envs/dev.tfvars`](deployment/terraform/envs/dev.tfvars)):** `0` to `5` containers per service.
    - **Staging ([`envs/staging.tfvars`](deployment/terraform/envs/staging.tfvars)):** `0` to `10` containers per service.
    - **Prod ([`envs/prod.tfvars`](deployment/terraform/envs/prod.tfvars)):** `2` always-ready containers per primary service in Paris (`europe-west9`)—plus `1` warm backup container per service in Belgium (`europe-west1`)—scaling up to `20` containers per service during busy periods.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf), [`deployment/terraform/envs/dev.tfvars`](deployment/terraform/envs/dev.tfvars), [`deployment/terraform/envs/staging.tfvars`](deployment/terraform/envs/staging.tfvars) & [`deployment/terraform/envs/prod.tfvars`](deployment/terraform/envs/prod.tfvars)*

- **1.3 Pillar 3 — Load Balancing & High-Throughput API Design**
  - **Built-In Cloud Run HTTPS Load Balancing:** Every Cloud Run service sits behind Google Cloud's managed HTTPS load balancer, which handles encryption automatically and spreads incoming user requests across healthy running containers.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*
  - **Running Chat Sub-Agents Together Without Extra Network Calls:** Running all five conversational agents inside the same `conversational-app` container avoids 2–3 extra network hops on every chat message.  
    — *Implemented in [`conversational_app/app/agent.py`](conversational_app/app/agent.py) & [`conversational_app/app/main.py`](conversational_app/app/main.py)*
  - **Handling Multiple Users at Once per Container:** Backend servers handle requests concurrently with separate temporary memory for each user, allowing a single container to serve many people at the same time while waiting for Gemini replies.  
    — *Implemented in [`flights_search_app/app/main.py`](flights_search_app/app/main.py) & [`conversational_app/app/main.py`](conversational_app/app/main.py)*

- **1.4 Pillar 4 — Scalable Managed Vertex AI Capacity**
  - **Global Vertex AI Routing:** All six agents send Gemini requests through Vertex AI's `global` endpoint by default, drawing from Google Cloud's shared worldwide AI capacity for higher rate limits and steadier response times.  
    — *Provisioned in [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf) & [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Implemented in [`flights_search_app/app/config.py`](flights_search_app/app/config.py), [`conversational_app/app/config.py`](conversational_app/app/config.py), [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*

> **Note on Unimplemented / Non-Relevant Pillars:**
> - **Self-Managed GPU Clusters (*Not Implemented — Not Relevant*):** Managing dedicated GPU or Kubernetes clusters is not needed because all AI model calls and web searches run on fully managed **Google Cloud Vertex AI** APIs while application containers run on serverless **Google Cloud Run**.
> - **Single Global Load Balancer Across All Services (*Not Implemented — Relevant*):** Each service currently uses Cloud Run's built-in `.run.app` web address; placing all services behind one shared Global External Application Load Balancer with a custom domain and Cloud Armor firewall rules is a practical future upgrade.

---

### 2. Resource Efficiency

Server sizes, AI token usage, idle container shutdowns, and image storage cleanup are tuned so development and staging environments cost `$0` when idle while active traffic avoids wasted compute and AI calls:

- **2.1 Pillar 1 — Right-Sizing Servers & AI Usage**
  - **Right-Sized CPU & Memory per Service:** Resources match what each service actually does—giving `2 vCPU` and `2 GiB` of RAM to the Python AI backends (`flights-search-app` and `conversational-app`) and a lightweight `1 vCPU` and `512 MiB` of RAM to the static web `frontend`.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf) & [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf)*
  - **Fast Model Defaults & Lean Prompt/Search Usage:**
    - Following our 4-experiment model benchmark in [`experiments_history.md`](conversational_app/tests/eval/results/experiments_history.md), all conversational sub-agents default to `gemini-3.8-flash` (with thinking disabled on fast routing/extraction steps and capped at `512` tokens on `filter_smart`), delivering `0.923` task success, `0.980` response coherence, `1.000` tool-use and schema validity, `7.91s` average latency, and `$12.09 per 1,000 requests` (see [3. AI Cost Management](#3-ai-cost-management)) while still allowing individual agents to be switched via configuration.
    - The Flight Search agent turns off extra internal "thinking" steps that aren't needed when generating flight schedules, every agent receives only the exact inputs it needs, and the Smart Filter agent skips Google Search whenever the flight list already contains the answer.  
    — *Implemented in [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py), [`conversational_app/app/config.py`](conversational_app/app/config.py) & [`conversational_app/app/sub_agents/filter_smart/prompt.py`](conversational_app/app/sub_agents/filter_smart/prompt.py)*

- **2.2 Pillar 2 — Cost-Aware Autoscaling & Pay-Per-Request Billing**
  - **Automatic Shutdown When Idle in `dev` & `staging`:** Development and staging environments set their minimum container count to zero so servers shut down completely whenever no one is using them.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf), [`deployment/terraform/envs/dev.tfvars`](deployment/terraform/envs/dev.tfvars) & [`deployment/terraform/envs/staging.tfvars`](deployment/terraform/envs/staging.tfvars)*
  - **Pay-Per-Request CPU Billing:** Whenever scale-to-zero is active (and on the web frontend in every environment), Cloud Run bills for CPU time only during the moments a container is actively answering a web request.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*

- **2.3 Pillar 3 — Storage, Build & Bandwidth Efficiency**
  - **Automatic Cleanup of Old Container Images:** Artifact Registry automatically deletes older container images beyond the 15 most recent versions per service so storage costs never grow unchecked.  
    — *Provisioned in [`deployment/terraform/registry.tf`](deployment/terraform/registry.tf)*
  - **Cached Builds, Slim Frontend Images & Compressed Responses:** Cloud Build reuses previously built container layers to speed up deployments, the frontend build leaves out heavy build tools from the final container to keep it small, and the web server compresses files with Gzip for faster page loads.  
    — *Implemented in [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`frontend/Dockerfile`](frontend/Dockerfile), [`frontend/nginx.conf.template`](frontend/nginx.conf.template), [`flights_search_app/Dockerfile`](flights_search_app/Dockerfile) & [`conversational_app/Dockerfile`](conversational_app/Dockerfile)*

> **Note on Unimplemented / Non-Relevant Pillars:**
> - **GPU Sizing & Spot Virtual Machines (*Not Implemented — Not Relevant*):** GPU sizing and Spot/Preemptible virtual machines do not apply because the project manages zero virtual machines or GPUs—AI calls are billed per token on **Vertex AI** and containers run on serverless **Cloud Run**.

---

### 3. AI Cost Management

AI token usage, Google Search fees, per-agent costs, caching savings, and prompt-size growth are tracked and controlled through lightweight runtime monitoring, an offline Vertex AI cost calculator in the evaluation suite, and fast Pull Request checks. Following our 4-experiment model benchmark ([`experiments_history.md`](conversational_app/tests/eval/results/experiments_history.md)), all conversational sub-agents now run on `gemini-3.8-flash` (with thinking budget `0` on `engage`, `filter`, `inspiration`, and `json_parser`, and `512` on `filter_smart`):

| Sub-Agent (`20261124_124413_all_3_8_flash`) | Model | Used In (% of Cases) | Avg Input / Output (+ Thinking) Tokens | Google Searches (50 cases) | Cost per 1,000 Requests | Share of Total Cost |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `engage` | `gemini-3.8-flash` | `100.0%` | `1,422` / `32` (+ `77`) | `0` | `$1.4742` | `12.2%` |
| `filter` | `gemini-3.8-flash` | `20.0%` | `1,014` / `39` (+ `11`) | `0` | `$0.1895` | `1.6%` |
| `filter_smart` | `gemini-3.8-flash` | `40.0%` | `3,932` / `1,416` (+ `273`) | `23` | `$10.1534` | `84.0%` |
| `inspiration` | `gemini-3.8-flash` | `20.0%` | `1,256` / `119` (+ `0`) | `0` | `$0.2775` | `2.3%` |
| **Total Active Baseline** | `gemini-3.8-flash` | `1.80` calls/req | `3,448` / `630` (+ `188`; avg `4,266` tot) | `23` (`0.46`/req) | **`$12.0945`** *(`$5.65` tokens + `$6.44` search)* | **`100.0%`** |

- **3.1 Pillar 1 — Lightweight Usage Tracking & Offline Cost Calculation**
  - **Tracking Raw Usage Without Slowing Down Live Traffic:** A built-in monitoring plugin records each agent's response time, input tokens, cached tokens, output tokens, internal thinking tokens, and exact Google Search count—while keeping all dollar-pricing math out of live production servers so real user requests stay fast and unaffected when cloud prices change.  
    — *Implemented in [`conversational_app/app/app_utils/telemetry_plugin.py`](conversational_app/app/app_utils/telemetry_plugin.py)*
  - **Offline Vertex AI & Google Search Pricing Calculator:** Inside the evaluation suite, a versioned pricing file calculates exact Vertex AI pay-as-you-go costs offline. It automatically matches model names, accounts for `90%` discounts on cached input tokens, bills thinking tokens at output rates, applies long-prompt pricing tiers over `200k` tokens, and adds Gemini 3's Google Search fee (`$14.00 per 1,000` live searches).  
    — *Implemented in [`conversational_app/tests/eval/configs/pricing_config.json`](conversational_app/tests/eval/configs/pricing_config.json) & [`conversational_app/tests/eval/metrics/cost_estimator.py`](conversational_app/tests/eval/metrics/cost_estimator.py)*  
    — *Verified in [`conversational_app/tests/unit/test_cost_and_eval_metrics.py`](conversational_app/tests/unit/test_cost_and_eval_metrics.py)*

- **3.2 Pillar 2 — Automated Cost Budgets & Per-Agent Breakdown**
  - **Cost & Token Limits in the 10-Check Evaluation Suite:** Every 50-scenario evaluation checks three cost limits—total cost per 1,000 requests (`<= $15.00`), model token cost per 1,000 requests (`<= $5.00`), and total tokens per request (`<= 6,000`). On `gemini-3.8-flash`, total cost (`$12.09/1k`) and token usage (`4,266` avg/req) pass while token-only spend (`$5.65/1k`) sits slightly above the `$5.00` target as an intentional quality trade-off. The report also shows cost per 1,000 *successful* tasks (`$13.10`), typical vs. worst-case request costs, how often JSON repair was needed (`0.0%`), and keeps actual assistant costs (`$0.605`) strictly separate from the AI grading judge's own cost (`$1.893`).  
    — *Implemented in [`conversational_app/tests/eval/configs/eval_config.json`](conversational_app/tests/eval/configs/eval_config.json), [`conversational_app/tests/eval/metrics/custom_metrics.py`](conversational_app/tests/eval/metrics/custom_metrics.py) & [`conversational_app/tests/eval/scripts/run_evaluation.py`](conversational_app/tests/eval/scripts/run_evaluation.py)*  
    — *Recorded in [`conversational_app/tests/eval/results/experiments_history.md`](conversational_app/tests/eval/results/experiments_history.md) & [`conversational_app/tests/eval/results/20261124_124413_all_3_8_flash/eval_summary.md`](conversational_app/tests/eval/results/20261124_124413_all_3_8_flash/eval_summary.md)*
  - **Seeing Exactly Where Money Goes:** Splitting AI token spend (`46.8%`, `$5.65/1k`) from Google Search fees (`53.2%`, `$6.44/1k`) and breaking costs down by specialist makes it clear that `filter_smart` drives `84.0%` of total spend even though it only runs on `40%` of requests—showing exactly where optimization has the biggest payoff.  
    — *Recorded in [`conversational_app/tests/eval/results/20261124_124413_all_3_8_flash/eval_summary.md`](conversational_app/tests/eval/results/20261124_124413_all_3_8_flash/eval_summary.md)*

- **3.3 Pillar 3 — Free "What-If" Model Comparisons & Caching Estimates**
  - **Instant `$0` Model Cost Comparisons:** Teams can replay saved evaluation logs with different model choices (for example, testing a stronger model on `filter_smart` only) to see the exact cost impact before spending a cent on live Vertex AI calls.  
    — *Implemented in [`conversational_app/tests/eval/scripts/run_evaluation.py`](conversational_app/tests/eval/scripts/run_evaluation.py) & [`conversational_app/tests/eval/metrics/cost_estimator.py`](conversational_app/tests/eval/metrics/cost_estimator.py)*  
    — *Verified in [`conversational_app/tests/unit/test_cost_and_eval_metrics.py`](conversational_app/tests/unit/test_cost_and_eval_metrics.py)*
  - **Automatic Caching Savings Projections:** Every evaluation summary estimates how much money and time two caching strategies would save:
    - *Reusing Recent Answers (Response Caching):* Skips both Gemini calls and `$14/1k` Google Search fees for repeat questions, projecting up to `50%` lower cost (`-$6.05/1k`) and `3.95s` average latency (down from `7.91s`) if half of requests hit the cache.
    - *Gemini Context Caching:* Discounts repeated prompt instructions (while keeping output and search costs the same) and checks Gemini 3's `4,096`-token minimum requirement—showing that after prompt optimization, all four sub-agents (including `filter_smart` at `3,932` average input tokens) currently stay just below the `4,096`-token threshold (`0%` threshold-gated savings today, vs. up to `-18.3%` / `-$2.21/1k` theoretically if prompt prefixes exceed `4,096` tokens).  
    — *Implemented in [`conversational_app/tests/eval/metrics/cost_estimator.py`](conversational_app/tests/eval/metrics/cost_estimator.py) & [`conversational_app/tests/eval/scripts/run_evaluation.py`](conversational_app/tests/eval/scripts/run_evaluation.py)*

- **3.4 Pillar 4 — Automatic Pull Request Prompt-Size & Cost Guardrails**
  - **Fast `$0` Cost-Regression Check on Every Pull Request:** Runs in under a second during Pull Request checks with zero live AI calls to catch accidental cost increases early:
    - *Per-Agent Prompt Size Limits:* Fails the check if any agent's instructions grow past its size limit (~`15%` above baseline) or if a new agent is added without setting a budget.
    - *End-to-End Path Cost Caps:* Caps the baseline input token count and minimum cost across all five chat paths (`continue`, `filter`, `inspiration`, `filter_smart`, and `filter_smart` with JSON repair).
    - *Cache-Friendly Prompt Structure Checks:* Catches duplicated instruction sections and confirms that changing user inputs (like the user's message and flight list) stay at the end of each prompt so the fixed instructions at the top remain eligible for Gemini caching.  
    — *Implemented in [`conversational_app/tests/unit/test_prompt_size_guardrails.py`](conversational_app/tests/unit/test_prompt_size_guardrails.py)*  
    — *Called in [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml)*

> **Note on Unimplemented / Non-Relevant Pillars:**
> - **Live Response Cache & Vertex AI Context Caching (*Not Implemented — Relevant*):** The evaluation suite already measures the exact savings from both caching layers (up to `-50%` from response caching) and CI checks keep prompts cache-friendly if they grow past Gemini 3's `4,096`-token prefix threshold; turning on a live response cache (such as Memorystore/Redis) is ready as a next step as production traffic grows.
> - **Cloud Billing Budget Alerts & Per-User Spend Limits (*Not Implemented — Relevant*):** Automated Google Cloud billing alerts and per-user rate or spend caps are not yet configured in Terraform and remain practical upgrades once user accounts are added.

---

## V. [SECURITY, PRIVACY, AND COMPLIANCE]

### 1. Authentication & Authorization

Cloud infrastructure and running services follow a strict least-privilege setup across three separate service accounts per project, version-controlled permissions, non-root containers, and keyless cloud authentication:

| Service Account | Provisioned By | Attached To | Granted IAM Roles |
| :--- | :--- | :--- | :--- |
| `travel-agent-cicd` | [`deployment/bootstrap.sh`](deployment/bootstrap.sh) | Cloud Build pipelines & GitHub triggers | `roles/run.admin`, `roles/artifactregistry.admin`, `roles/iam.serviceAccountAdmin`, `roles/iam.serviceAccountUser`, `roles/resourcemanager.projectIamAdmin`, `roles/serviceusage.serviceUsageAdmin`, `roles/cloudbuild.builds.editor`, `roles/storage.admin`, `roles/logging.logWriter` |
| `travel-agent-runtime` | [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) | `flights-search-app`, `conversational-app` | `roles/aiplatform.user` (Vertex AI Gemini), `roles/logging.logWriter`, `roles/cloudtrace.agent` |
| `travel-agent-frontend` | [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) | `frontend` (Nginx web container) | `roles/logging.logWriter` **only** (zero Vertex AI, storage, or admin access) |

- **1.1 Pillar 1 — Dedicated Service Accounts (Three Separate Identities per Project)**
  - **Backend AI Account (`travel-agent-runtime`):** Used only by the Flight Search and Conversational services instead of Google Cloud's overly broad default account.  
    — *Provisioned in [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) & [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*
  - **Frontend Web Account (`travel-agent-frontend`):** Used only by the Frontend web container so the public website never shares credentials with the backend AI services.  
    — *Provisioned in [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) & [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*
  - **Deployment Pipeline Account (`travel-agent-cicd`):** Used only for automated Cloud Build pipelines and GitHub triggers so all deployments run under one tracked machine identity.  
    — *Provisioned in [`deployment/bootstrap.sh`](deployment/bootstrap.sh), [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) & [`deployment/terraform/triggers.tf`](deployment/terraform/triggers.tf)*  
    — *Called in [`deployment/deploy.sh`](deployment/deploy.sh)*

- **1.2 Pillar 2 — Identity & Access Management (IAM)**
  - **Version-Controlled Cloud Permissions:** All service permissions—including which deployment account is allowed to attach runtime identities to Cloud Run—are defined explicitly in Terraform rather than clicked manually in the cloud console.  
    — *Provisioned in [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf)*
  - **Consistent Bucket-Wide Storage Permissions:** The Cloud Storage bucket that holds Terraform state enforces one consistent set of permissions across the entire bucket rather than allowing one-off file overrides.  
    — *Provisioned in [`deployment/bootstrap.sh`](deployment/bootstrap.sh)*

- **1.3 Pillar 3 — Principle of Least Privilege**
  - **Minimal Frontend Account (Logging Only):** Because the user's browser calls the backend services directly over HTTPS, the Frontend container makes zero AI or backend calls itself and is only allowed to write logs—with zero access to Vertex AI, Cloud Storage, or admin settings.  
    — *Provisioned in [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf)*
  - **Scoped Backend Account:** The Backend service account can only call Vertex AI models and write logs and traces, with zero access to Terraform state storage, Artifact Registry, or project administration.  
    — *Provisioned in [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf)*
  - **Automatic Cleanup of Default Google Accounts:** During project setup, [`deployment/bootstrap.sh`](deployment/bootstrap.sh) checks project permissions and actively removes extra deployment roles from Google's built-in default accounts.  
    — *Implemented in [`deployment/bootstrap.sh`](deployment/bootstrap.sh)*
  - **Non-Root Container Execution:** Both backend containers drop administrator privileges before starting up and run as a restricted user (`appuser`) for extra security.  
    — *Implemented in [`flights_search_app/Dockerfile`](flights_search_app/Dockerfile) & [`conversational_app/Dockerfile`](conversational_app/Dockerfile)*

- **1.4 Pillar 4 — Keyless Cloud Authentication & Allowed Website Origins**
  - **No Hardcoded API Keys:** Backend containers never store static Gemini API keys or downloaded JSON key files; instead, Cloud Run provides automatic short-lived credentials through each container's attached service account, while local `.env` and `.tfvars` files are excluded from Git and container builds.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Implemented in [`.gitignore`](.gitignore), [`.gcloudignore`](.gcloudignore), [`flights_search_app/.dockerignore`](flights_search_app/.dockerignore) & [`conversational_app/.dockerignore`](conversational_app/.dockerignore)*
  - **Configurable Allowed Website Origins (CORS):** Backend services control which websites are allowed to call their APIs from a browser using configurable lists in environment and Terraform settings.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf) & [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf)*  
    — *Implemented in [`flights_search_app/app/config.py`](flights_search_app/app/config.py), [`flights_search_app/app/main.py`](flights_search_app/app/main.py), [`conversational_app/app/config.py`](conversational_app/app/config.py) & [`conversational_app/app/main.py`](conversational_app/app/main.py)*

> **Note on Unimplemented Pillars:**
> - **User Sign-In & Private Backend Access (*Not Implemented — Relevant*):** Because the app is currently deployed as a public flight search demo that anyone can try in the browser without signing up, user login (such as Google Sign-In / Firebase Auth) and private-only backend access are not yet enabled and remain natural next steps if personal user accounts and saved trips are added.

---

## VI. [RELIABILITY & RESILIENCE]

### 1. Availability Design

The platform avoids single points of failure across servers, AI models, health checks, and cloud regions so the app stays online even if an individual container crashes, a Gemini model has an outage, or an entire cloud region goes down—while still letting development and staging environments shut down when idle to save money:

- **1.1 Pillar 1 — Redundancy**
  - **Always-On Backup Containers in Production:** In production, each of the three main services (Flight Search, Conversational Assistant, and Web Frontend) keeps at least two ready-to-serve containers running at all times across separate data-center zones within the Paris region (whereas development and staging shut down to zero containers when unused). If one container crashes or restarts, the second running container immediately handles user requests with zero startup wait time.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf), [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf) & [`deployment/terraform/envs/prod.tfvars`](deployment/terraform/envs/prod.tfvars)*
  - **Built-In Redundancy Across Supporting Cloud Services:** None of the surrounding cloud services depend on a single data center either: incoming web traffic is distributed automatically by Google Cloud's global load balancers, Gemini AI requests are served from Google's shared global capacity pool rather than one local facility, production container images are stored in two separate European regions (Paris and Belgium), and infrastructure state backups are automatically copied across multiple European locations.  
    — *Provisioned in [`deployment/bootstrap.sh`](deployment/bootstrap.sh), [`deployment/terraform/registry.tf`](deployment/terraform/registry.tf) & [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*

- **1.2 Pillar 2 — Failover**
  - **Automatic Backup AI Model:** Across Flight Search, the Conversational workflow, and every individual specialist agent, the default Gemini model (`gemini-3.5-flash-lite`) is paired with a separate backup Gemini model (`gemini-3.6-flash`, which can be changed globally or per agent). If the primary model is still unavailable after five automatic retry attempts—for instance, during a temporary model outage or traffic spike—the backend automatically switches to the backup model and completes the user's flight search or chat message without showing an error.  
    — *Provisioned in [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf) & [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Implemented in [`flights_search_app/app/config.py`](flights_search_app/app/config.py), [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py), [`flights_search_app/app/main.py`](flights_search_app/app/main.py), [`conversational_app/app/config.py`](conversational_app/app/config.py), [`conversational_app/app/agent.py`](conversational_app/app/agent.py), [`conversational_app/app/main.py`](conversational_app/app/main.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*  
    — *Verified in [`flights_search_app/tests/unit/test_flights_search.py`](flights_search_app/tests/unit/test_flights_search.py) & [`conversational_app/tests/unit/test_conversational.py`](conversational_app/tests/unit/test_conversational.py)*
  - **Safe Updates That Block Broken Releases:** Whenever a new version of a service is deployed, `100%` of live users stay on the currently running version until the new version proves it has started properly and passed its readiness check. If a new release crashes on startup or is missing required settings, Cloud Run automatically cancels the switch so broken updates never reach users.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*

- **1.3 Pillar 3 — Health Checks**
  - **Two-Level Health Checks ("Is It Running?" vs. "Is It Ready?"):** Every backend service, specialist agent, and web frontend provides two separate health-check URLs alongside its root info page:
    - **Liveness Check (`/healthz` — *"Is the server alive?"*):** A quick check confirming the web server is running and hasn't frozen.
    - **Readiness Check (`/readyz` — *"Is the server ready for users?"*):** A deeper check confirming the AI agents are loaded and all required cloud project and model settings are in place (or, on the web frontend, that its backend connection file has been created) before any user traffic is sent to it.  
    — *Implemented in [`flights_search_app/app/app_utils/health.py`](flights_search_app/app/app_utils/health.py), [`flights_search_app/app/main.py`](flights_search_app/app/main.py), [`conversational_app/app/app_utils/health.py`](conversational_app/app/app_utils/health.py), [`conversational_app/app/main.py`](conversational_app/app/main.py), [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/) & [`frontend/nginx.conf.template`](frontend/nginx.conf.template)*  
    — *Verified in [`flights_search_app/tests/unit/test_flights_search.py`](flights_search_app/tests/unit/test_flights_search.py), [`conversational_app/tests/unit/`](conversational_app/tests/unit/), [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) & [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml)*
  - **Automatic Self-Healing Container Checks:** Cloud Run calls both health-check URLs automatically on every primary and backup service: at startup, it checks `/readyz` every 5 seconds and waits until the container is fully ready before sending user requests; while running, it checks `/healthz` every 30 seconds and automatically restarts any container that stops responding.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*

- **1.4 Pillar 4 — Multi-Region & Stateless Design**
  - **Global AI Routing Across Regions:** All primary and backup Gemini calls connect through Google's global Vertex AI service rather than being locked to a single regional data center, so AI responses keep working even if one European region runs low on capacity.  
    — *Provisioned in [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf) & [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*
  - **Warm Backup Region with Automatic Browser Failover:** Without needing a paid custom domain or an external global load balancer, production keeps a warm backup copy of all three services running in **Belgium (`europe-west1`)** alongside the main services in **Paris (`europe-west9`)**, complete with its own Belgium image storage so it can start containers even if Paris is completely offline. The web app receives both sets of backend addresses when it loads: if a flight search or chat request to Paris fails because of a network drop or regional server outage, the browser automatically resends the request to the warm Belgium backend behind the scenes—and if the main Paris website URL itself ever goes down, the live Belgium website URL is already running and ready to open.  
    — *Provisioned in [`deployment/terraform/registry.tf`](deployment/terraform/registry.tf), [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf), [`deployment/terraform/outputs.tf`](deployment/terraform/outputs.tf), [`deployment/terraform/envs/prod.tfvars`](deployment/terraform/envs/prod.tfvars) & [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml)*  
    — *Implemented in [`frontend/Dockerfile`](frontend/Dockerfile), [`frontend/src/apiClient.js`](frontend/src/apiClient.js), [`frontend/src/App.jsx`](frontend/src/App.jsx) & [`frontend/src/ChatWidget.jsx`](frontend/src/ChatWidget.jsx)*
  - **One-Command Recovery to Any Other Cloud Region:** Because infrastructure state files are backed up across multiple European regions and region names are configurable, an operator can redeploy the entire production stack into another healthy Google Cloud region (such as the Netherlands, `europe-west4`) with a single command (`REGION="europe-west4" SECONDARY_REGION="" ./deployment/deploy.sh prod`).  
    — *Provisioned in [`deployment/bootstrap.sh`](deployment/bootstrap.sh) & [`deployment/deploy.sh`](deployment/deploy.sh)*

> **Note on Unimplemented / Non-Relevant Pillars:**
> - **Formal Uptime Targets (SLOs / SLAs) & Automated Alerts (*Not Implemented — Relevant*):** While the evaluation suite checks response speed (`<= 15.0s`) and output accuracy (`>= 0.95`), formal uptime commitments (such as a `99.9%` monthly availability target with automated alert notifications when error rates rise) are not yet set up and remain a practical future addition.
> - **External Uptime Monitoring & Single-Domain Global Load Balancing (*Not Implemented — Relevant*):** Cloud Run checks container health internally and production keeps a warm backup website URL in Belgium, but external monitoring checks from outside Google Cloud and a custom domain behind a global load balancer (which would let users keep using one single `.com` address even if the Paris website URL went down) are not yet set up.
> - **End-to-End Request Tracking IDs & Internal Service Mesh (*Not Implemented — Relevant*):** Because all five chat agents run together inside a single backend service rather than calling each other over a network, an internal service mesh is unnecessary; passing a shared tracking ID from the browser into backend logs for easier debugging remains a useful future improvement.
> - **Database Consistency & Sharding (*Not Implemented — Not Relevant*):** Database replication rules and data partitioning do not apply to this project because none of the services store user data in a database—every search or chat message sends its current flight list and conversation history directly in the request and is processed in temporary memory.

---

### 2. Graceful Degradation

The platform is built to absorb temporary Vertex AI glitches, messy AI formatting after live Google Searches, and partial service outages without breaking the app for the user:

- **2.1 Pillar 1 — Fallback Strategies**
  - **Automatic Repair of Messy JSON Replies:** When the Smart Filter agent returns broken or markdown-wrapped JSON after searching Google, the workflow catches the formatting issue automatically and hands the text to the JSON Parser agent, which cleans it into valid JSON so the user still gets their filtered flights.  
    — *Implemented in [`conversational_app/app/agent.py`](conversational_app/app/agent.py), [`conversational_app/app/sub_agents/json_parser/agent.py`](conversational_app/app/sub_agents/json_parser/agent.py) & [`conversational_app/app/sub_agents/json_parser/prompt.py`](conversational_app/app/sub_agents/json_parser/prompt.py)*
  - **Safe Handling of Unexpected Plain-Text Replies:** If an AI agent ever replies with plain text instead of expected JSON data, the backend catches the issue, logs a warning, and returns the text safely instead of crashing with a server error.  
    — *Implemented in [`flights_search_app/app/main.py`](flights_search_app/app/main.py), [`conversational_app/app/main.py`](conversational_app/app/main.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*
  - **Independent Flight Search & Chat Panels:** Because Flight Search and the Chat Assistant run as separate services—and the chat widget handles errors locally inside its own panel—a problem in the chat service never breaks flight searching, manual filters, or page navigation on the main screen.  
    — *Implemented in [`frontend/src/ChatWidget.jsx`](frontend/src/ChatWidget.jsx) & [`frontend/src/App.jsx`](frontend/src/App.jsx)*
  - **Three-Step Backend Address Fallback:** The web frontend looks up backend URLs across three fallback levels so it works seamlessly in the cloud and on a laptop: (1) live Cloud Run settings (`/env-config.js`), (2) local `.env` settings, and (3) default local ports (`8000` and `8001`).  
    — *Implemented in [`frontend/src/apiClient.js`](frontend/src/apiClient.js), [`frontend/src/App.jsx`](frontend/src/App.jsx) & [`frontend/src/ChatWidget.jsx`](frontend/src/ChatWidget.jsx)*

- **2.2 Pillar 2 — Retry Policies**
  - **Automatic Retries with Increasing Wait Times Across All Six Agents:** Every AI agent automatically retries failed Gemini calls up to 5 times (waiting longer between each attempt, from 5 seconds up to 60 seconds) whenever it hits temporary rate limits, timeouts, or server hiccups.  
    — *Implemented in [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py), [`conversational_app/app/sub_agents/engage/agent.py`](conversational_app/app/sub_agents/engage/agent.py), [`conversational_app/app/sub_agents/filter/agent.py`](conversational_app/app/sub_agents/filter/agent.py), [`conversational_app/app/sub_agents/filter_smart/agent.py`](conversational_app/app/sub_agents/filter_smart/agent.py), [`conversational_app/app/sub_agents/inspiration/agent.py`](conversational_app/app/sub_agents/inspiration/agent.py) & [`conversational_app/app/sub_agents/json_parser/agent.py`](conversational_app/app/sub_agents/json_parser/agent.py)*
  - **Deployment & Post-Release Health-Check Retries:** Setup scripts wait and retry when new cloud permissions take a moment to activate, and the final stage of every deployment pipeline retries live health checks up to 5 times to allow freshly started containers to warm up.  
    — *Implemented in [`deployment/bootstrap.sh`](deployment/bootstrap.sh), [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) & [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml)*

- **2.3 Pillar 3 — Timeout Handling**
  - **Generous 5-Minute Backend Request Timeouts:** Both backend Cloud Run services allow up to 300 seconds (5 minutes) per request so multi-step chat turns involving live Google Searches, automatic retries, backup model switching, and JSON repair are never cut off mid-answer.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*
  - **Clear Time Limits on Tests, Infrastructure Locks & Builds:** End-to-end tests stop waiting after 90 seconds, Terraform waits up to 5 minutes if another deployment is already running, and Cloud Build pipelines cap total build time at 30 minutes so stuck jobs never hang indefinitely.  
    — *Implemented in [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`flights_search_app/tests/e2e/test_flights_search.py`](flights_search_app/tests/e2e/test_flights_search.py) & [`conversational_app/tests/e2e/test_conversational.py`](conversational_app/tests/e2e/test_conversational.py)*

> **Note on Unimplemented Pillars:**
> - **Automatic Circuit Breakers (*Not Implemented — Relevant*):** While the app uses 5-attempt automatic retries, backup Gemini model switching, automatic Belgium regional failover, JSON repair, 5-minute request timeouts, and separate Flight Search and Chat services, a shared circuit breaker (which temporarily pauses calls to a failing upstream service so requests fail immediately instead of waiting through retries) is not yet set up and remains a useful future enhancement.

---

### 3. Failure & Recovery Testing

Rather than assuming backup models, regional failover, JSON repair, safety rules, and infrastructure backups will work during a real incident, the platform regularly tests how it handles failures and recovers across local test suites, container builds, Pull Request checks, and post-deployment checks:

- **3.1 Pillar 1 — Failure Injection**
  - **Testing Automatic JSON Repair on Broken & Incomplete AI Replies:** Automated tests deliberately feed cut-off, messy, markdown-wrapped, or wrongly structured replies into the Smart Filter workflow step to confirm that broken answers are automatically sent to the JSON Parser agent and cleaned into valid flight results instead of failing the user's chat turn.  
    — *Implemented in [`conversational_app/app/agent.py`](conversational_app/app/agent.py)*  
    — *Verified in [`conversational_app/tests/unit/test_failure_injection.py`](conversational_app/tests/unit/test_failure_injection.py)*
  - **Simulating AI Model Outages, Cut-Off Answers & Plain-Text Replies:** Offline tests simulate primary Gemini outages, cut-off AI responses, empty replies, and unexpected plain-text answers across Flight Search, the Conversational workflow, and all five specialist agents—verifying that the backend switches cleanly to the backup Gemini model when the primary model fails, handles plain text safely without crashing, and reports itself as unready if required startup settings are missing.  
    — *Implemented in [`flights_search_app/app/main.py`](flights_search_app/app/main.py), [`conversational_app/app/main.py`](conversational_app/app/main.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*  
    — *Verified in [`flights_search_app/tests/unit/test_failure_injection.py`](flights_search_app/tests/unit/test_failure_injection.py) & [`conversational_app/tests/unit/test_failure_injection.py`](conversational_app/tests/unit/test_failure_injection.py)*
  - **Simulating Regional Outages in the Web Browser:** Automated frontend tests simulate Paris backend outages and dropped network connections to verify that the browser automatically resends the request to the warm Belgium backup backend, stops immediately without double-sending invalid user form inputs, and surfaces a clear error only if both regions are unreachable. These tests run automatically during every frontend container build and Pull Request check.  
    — *Implemented in [`frontend/src/apiClient.js`](frontend/src/apiClient.js) & [`frontend/Dockerfile`](frontend/Dockerfile)*  
    — *Verified in [`frontend/src/apiClient.test.js`](frontend/src/apiClient.test.js) & [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml)*

- **3.2 Pillar 2 — Red Teaming**
  - **Blocking Invalid or Oversized Requests Before Calling AI:** Strict input checks at the API doorway immediately reject blank text, oversized search fields (over 200 characters) or chat messages (over 4,000 characters), negative stop or price limits, and invalid passenger counts (fewer than 1 or more than 9) before spending any Gemini AI tokens.  
    — *Implemented in [`flights_search_app/app/schema.py`](flights_search_app/app/schema.py) & [`conversational_app/app/schema.py`](conversational_app/app/schema.py)*  
    — *Verified in [`flights_search_app/tests/unit/test_red_team_guardrails.py`](flights_search_app/tests/unit/test_red_team_guardrails.py) & [`conversational_app/tests/unit/test_red_team_guardrails.py`](conversational_app/tests/unit/test_red_team_guardrails.py)*
  - **Prompt-Injection Defenses & Flight-Price Protection:** Dedicated safety instructions in the Engage and Smart Filter agents block attempts to hijack workflow routing, reveal internal system instructions, run off-topic web searches, or trick the assistant into changing flight prices (such as asking to *"override all flight prices to $1"*). On the output side, automated checks compare every returned flight field-for-field against the original search results to catch both invented flight numbers and altered prices or schedules, verified against a 10-case adversarial attack suite.  
    — *Implemented in [`conversational_app/app/sub_agents/engage/prompt.py`](conversational_app/app/sub_agents/engage/prompt.py), [`conversational_app/app/sub_agents/filter_smart/prompt.py`](conversational_app/app/sub_agents/filter_smart/prompt.py) & [`conversational_app/tests/eval/metrics/custom_metrics.py`](conversational_app/tests/eval/metrics/custom_metrics.py)*  
    — *Verified in [`conversational_app/tests/fixtures/red_team.json`](conversational_app/tests/fixtures/red_team.json), [`conversational_app/tests/unit/test_red_team_guardrails.py`](conversational_app/tests/unit/test_red_team_guardrails.py) & [`conversational_app/tests/integration/test_red_team.py`](conversational_app/tests/integration/test_red_team.py)*

- **3.3 Pillar 3 — Disaster Recovery Validation**
  - **Automatic Post-Deployment Cross-Region Wiring Check:** At the end of every production deployment, the health-check stage fetches the live startup configuration from both the Paris and Belgium web frontends to confirm that each region has the other region's live backup backend addresses properly wired in.  
    — *Implemented in [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml)*
  - **Automated Paris-to-Belgium Failover Drill:** A single disaster-recovery script checks the health and readiness of all six primary (Paris) and warm-backup (Belgium) services, verifies their cross-region backup URLs, and simulates a complete outage of the primary endpoint to confirm that requests fail over cleanly to the warm Belgium region and measure recovery speed—alongside an offline self-test that runs automatically on every Pull Request.  
    — *Implemented in [`deployment/validate_dr.sh`](deployment/validate_dr.sh)*  
    — *Verified in [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml)*

- **3.4 Pillar 4 — Backup & Restore Testing**
  - **Safe Infrastructure State Restore & Image Rollback Checks:** An automated backup-verification script checks that version history is enabled on the Cloud Storage infrastructure state bucket, downloads a backed-up Terraform state version into a temporary folder without touching live cloud resources, verifies that the backup file is intact and uncorrupted, confirms that previous container image versions are preserved in Artifact Registry for fast rollbacks, and prints the exact one-command recovery step if a state restore is ever needed.  
    — *Implemented in [`deployment/verify_backups.sh`](deployment/verify_backups.sh)*  
    — *Verified in [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml)*

- **3.5 Pillar 5 — Resilience Testing Under Degraded Conditions**
  - **Multi-User Slowdowns & Isolated User Sessions:** Automated slowdown tests send a dozen simultaneous user requests where some hit simulated rate limits or slow primary model failovers while others run normally—confirming that slow requests never block fast users, two users' flight lists or chat histories never mix together, and monitoring logs stay accurate even after errors.  
    — *Verified in [`conversational_app/tests/unit/test_degraded_conditions.py`](conversational_app/tests/unit/test_degraded_conditions.py) & [`flights_search_app/tests/unit/test_degraded_conditions.py`](flights_search_app/tests/unit/test_degraded_conditions.py)*
  - **Handling Missing Data, Noisy AI Replies & Multi-Currency Prices:** Resilience tests confirm that the assistant still works smoothly when a user chats before running a flight search (an empty flight list), when live Google Search returns partial or empty citation details, when an AI reply wraps valid JSON inside extra introductory text, or when flight cards list prices in different currency formats (`EUR`, `USD`, `$`, `€`, `£`)—while also verifying that all six primary and backup agents keep their 5-attempt automatic retry settings intact.  
    — *Implemented in [`conversational_app/app/agent.py`](conversational_app/app/agent.py), [`conversational_app/app/sub_agents/filter_smart/main.py`](conversational_app/app/sub_agents/filter_smart/main.py), [`frontend/src/apiClient.js`](frontend/src/apiClient.js) & [`frontend/src/ChatWidget.jsx`](frontend/src/ChatWidget.jsx)*  
    — *Verified in [`conversational_app/tests/unit/test_degraded_conditions.py`](conversational_app/tests/unit/test_degraded_conditions.py), [`flights_search_app/tests/unit/test_degraded_conditions.py`](flights_search_app/tests/unit/test_degraded_conditions.py) & [`frontend/src/apiClient.test.js`](frontend/src/apiClient.test.js)*

> **Note on Unimplemented / Non-Relevant Pillars:**
> - **User Database Backup & Restore (*Not Implemented — Not Relevant*):** Database backup and point-in-time user data recovery do not apply to this project because none of the services store user accounts, bookings, or chat history in a database—each request sends its current flight list and conversation history directly from the browser and is processed in temporary memory. Backup and restore testing therefore focuses on the project's stateful cloud assets: versioned Terraform infrastructure state files in Cloud Storage and previous container images in Artifact Registry.
> - **Server-Level Chaos Agents (*Not Implemented — Not Relevant*):** Because all services run on fully managed serverless Google Cloud Run containers without underlying virtual machines or disks to manage, server-level chaos tools (such as killing operating-system processes or filling up hard drives) do not apply; instead, failures are simulated directly at the AI model, workflow, and regional network boundaries.
> - **Scheduled Live Chaos Drills & Automatic Traffic Rollbacks (*Not Implemented — Relevant*):** While disaster-recovery and backup scripts run offline self-tests automatically on every Pull Request and can be run on demand against live environments, scheduled recurring failover drills in production and automatic revision rollbacks when error alerts spike are not yet set up and remain practical future additions.

---

## 📁 Repository Structure

```text
travel_agent/
├── .cloudbuild/                        # Google Cloud Build CI/CD Pipelines
│   ├── pr_checks.yaml                  # Pull Request CI (backend/frontend unit tests, DR/backup self-tests, Vite build, terraform validate)
│   ├── dev.yaml                        # 5-stage CD pipeline for Dev (travel-agent-511710)
│   ├── staging.yaml                    # 5-stage CD pipeline for Staging (travel-agent-staging-512211)
│   └── prod.yaml                       # 5-stage CD pipeline for Prod + cross-region /env-config.js smoke checks
├── docs/                               # API, Integration, SDK & Production Operational Documentation
│   ├── diagrams/                       # Architecture, workflow, sequence & triage diagrams (PNG & SVG)
│   ├── api_documentation.md            # OpenAPI 3.1 endpoint reference, integration guides & JS/Python SDK docs
│   ├── operational_documentation.md    # Operational Hub: SLOs/SLIs, telemetry/logging, IAM posture & severity matrix
│   ├── deployment_guide.md             # 5-stage Cloud Build + Terraform CD guide, promotion flow, model rollouts & rollbacks
│   ├── runbooks.md                     # Standardized production SOPs (RB-01 through RB-09) for outages, DR, quotas & state
│   ├── onboarding_guide.md             # Progressive engineer/operator onboarding (30m -> Day 1 -> Week 1) & workflow tour
│   └── troubleshooting_guide.md        # Symptom-driven diagnostic reference across Cloud Run, Vertex AI, CORS & CI/CD
├── deployment/                         # Infrastructure as Code (Terraform), Deployment & Resilience Drill Runners
│   ├── bootstrap.sh                    # Provisions multi-region (EU) GCS state bucket, travel-agent-cicd SA & cleans default SAs
│   ├── deploy.sh                       # Unified runner for PR checks, dev/staging/prod deployments & regional DR overrides
│   ├── validate_dr.sh                  # Multi-region Cloud Run DR probe, /env-config.js check & failover speed drill
│   ├── verify_backups.sh               # Safe GCS Terraform state restore drill & Artifact Registry rollback check
│   └── terraform/                      # Single declarative Terraform stack across dev, staging & prod
│       ├── apis.tf                     # Required GCP service APIs (Cloud Run, Vertex AI, Artifact Registry, IAM, etc.)
│       ├── iam.tf                      # 3-SA separation (agent_runtime, frontend_runtime, cicd_runner)
│       ├── registry.tf                 # Primary & secondary regional Artifact Registry Docker repos + 15-version cleanup
│       ├── cloud_run.tf                # Cloud Run v2 primary/secondary services, /readyz & /healthz probes & URL wiring
│       ├── triggers.tf                 # Automated Cloud Build GitHub triggers (PR, main -> staging, v* -> prod)
│       ├── variables.tf                # Parameterized primary/secondary region, primary/fallback models, scaling & CORS inputs
│       ├── outputs.tf                  # Deployed primary & secondary Cloud Run service URLs & Service Account emails
│       ├── versions.tf                 # Terraform & provider constraints + remote GCS state backend
│       └── envs/                       # Environment-specific variable files (dev.tfvars, staging.tfvars, prod.tfvars)
├── flights_search_app/                 # Standalone Flights Search ADK Service (Local :8000 / Cloud Run :8080)
│   ├── app/
│   │   ├── agent.py                    # Primary & fallback flights_search ADK Agents & App containers
│   │   ├── config.py                   # Externalized primary/fallback models, location, host/port, base URL, CORS & plugin config
│   │   ├── export_openapi.py           # Deterministic OpenAPI 3.1 contract snapshot exporter (openapi.json)
│   │   ├── main.py                     # FastAPI server (/api/v1 + legacy routes), /healthz & /readyz probes, CORS & failover
│   │   ├── prompt.py                   # Flight simulation system instructions & realism rules
│   │   ├── schema.py                   # Validated request & response envelopes, Tolerant Reader config & boundary rules
│   │   └── app_utils/
│   │       ├── health.py               # Standardized /healthz liveness & /readyz deep readiness payload builders
│   │       ├── logging.py              # Structured logging & table formatting helpers
│   │       ├── telemetry_plugin.py     # ADK ExecutionTelemetryPlugin (latency & token telemetry)
│   │       └── versioning.py           # X-API-Version & RFC 8594 Deprecation/Link header middleware
│   ├── tests/
│   │   ├── fixtures/                   # Sample search payloads (flights_search.json)
│   │   ├── unit/                       # Offline health, API contract/versioning, failover, fault-injection & boundary tests (5 modules)
│   │   ├── integration/                # In-process TestClient tests with live Vertex AI Gemini inference
│   │   └── e2e/                        # Live HTTP client tests (configurable via FLIGHTS_SEARCH_BASE_URL)
│   ├── openapi.json                    # Committed OpenAPI 3.1 contract snapshot verified automatically in CI
│   ├── Dockerfile                      # Hardened non-root (appuser) Python 3.11 container image
│   ├── .env.example                    # Template environment & model variables
│   └── requirements.txt                # Pinned Python runtime dependencies
├── conversational_app/                 # Conversational Multi-Agent Workflow Service (Local :8001–8006 / Cloud Run :8080)
│   ├── app/
│   │   ├── agent.py                    # Primary & fallback ADK v2 Workflow graphs, self-healing routing steps & App containers
│   │   ├── config.py                   # Externalized global & per-sub-agent primary/fallback models, ports, URLs & CORS
│   │   ├── export_openapi.py           # Deterministic OpenAPI 3.1 contract snapshot exporter (openapi.json)
│   │   ├── main.py                     # FastAPI gateway (/api/v1 + legacy routes, /healthz, /readyz) & ADK Runner failover
│   │   ├── schema.py                   # Canonical Flight/FlightParams, workflow state, response envelopes & boundary rules
│   │   ├── app_utils/
│   │   │   ├── health.py               # Standardized /healthz liveness & /readyz deep readiness payload builders
│   │   │   ├── logging.py              # Structured logging & table formatting helpers
│   │   │   ├── telemetry_plugin.py     # ADK ExecutionTelemetryPlugin (raw latency, in/cached/out/thoughts token & grounding telemetry)
│   │   │   └── versioning.py           # X-API-Version & RFC 8594 Deprecation/Link header middleware
│   │   └── sub_agents/                 # 5 Self-Contained Specialist Sub-Agents (each with agent.py, main.py, prompt.py, schema.py)
│   │       ├── engage/                 # Intent triage & safety-hardened routing specialist (:8002)
│   │       ├── filter/                 # Deterministic hard filter extractor (:8003)
│   │       ├── filter_smart/           # Semantic & amenity filter with Google Search grounding & safety rules (:8004)
│   │       ├── inspiration/            # Open-ended destination & date discovery specialist (:8005)
│   │       └── json_parser/            # Self-healing JSON structure repair specialist (:8006)
│   ├── tests/
│   │   ├── fixtures/                   # Functional payloads + 10-case red-team safety suite (red_team.json)
│   │   ├── unit/                       # Offline health, API contract/versioning, cost/caching math, prompt-size guardrails, failover, fault-injection & red-team tests (12 modules)
│   │   ├── integration/                # Live Gemini integration + red-team prompt-safety tests (test_red_team.py)
│   │   ├── e2e/                        # Live HTTP client tests against :8001–:8006 or Cloud Run (6 test modules)
│   │   └── eval/                       # 10-Metric GEAP AI Quality, Flight/Price Protection, Latency & Standard PayGo Cost Evaluation Suite
│   │       ├── configs/                # eval_config.json, pricing_config.json, scenario_generation_config.json, session_input.json
│   │       ├── datasets/               # 50-case synthetic travel benchmark (conversational_synthetic.evalset.json)
│   │       ├── metrics/                # custom_metrics.py & cost_estimator.py (Standard PayGo pricing & caching projections)
│   │       ├── results/                # Timestamped evaluation runs, traces, loss clusters & experiments_history.md
│   │       └── scripts/                # generate_scenarios.py, run_evaluation.py, run_loss_analysis.py
│   ├── openapi.json                    # Committed OpenAPI 3.1 contract snapshot verified automatically in CI
│   ├── Dockerfile                      # Hardened non-root (appuser) Python 3.11 container image
│   ├── .env.example                    # Template environment, per-agent model & endpoint configuration
│   └── requirements.txt                # Pinned Python runtime dependencies
└── frontend/                           # React + Vite SPA & Nginx Cloud Run Container (Local :5173 / Cloud Run :8080)
    ├── src/
    │   ├── App.jsx                     # Flight search form, manual filter controls & paginated itinerary cards
    │   ├── ChatWidget.jsx              # Conversational AI widget & multi-currency UI filter synchronization
    │   ├── apiClient.js                # /api/v1 prefix, runtime URL resolver, cross-region failover & price helper
    │   ├── apiClient.test.js           # Offline unit, /api/v1 path & regional-failover tests for apiClient.js
    │   ├── index.css                   # Application & ChatWidget styling
    │   └── main.jsx                    # React root entrypoint
    ├── index.html                      # Loads runtime /env-config.js before mounting React bundle
    ├── Dockerfile                      # Multi-stage Node 20 (npm test + build) + Nginx 1.27 runtime /env-config.js generator
    ├── nginx.conf.template             # Cloud Run Nginx config (/healthz, /readyz, Gzip, SPA fallback & no-store /env-config.js)
    ├── .env.example                    # Template local primary & optional fallback backend API URLs
    └── README.md                       # Frontend & runtime configuration documentation
```

---

## 🚀 Local Setup & Prerequisites

### 1. Authenticate with Google Cloud & Configure `.env` Files
Ensure **Python >= 3.11** and **Node.js >= 18** are installed, then authenticate your local Application Default Credentials (ADC) so the backend services can call Vertex AI:
```bash
gcloud auth application-default login
```

Copy the template `.env.example` files in each application if `.env` is not already present:
```bash
cp -n flights_search_app/.env.example flights_search_app/.env
cp -n conversational_app/.env.example conversational_app/.env
cp -n frontend/.env.example frontend/.env
```

Example [`conversational_app/.env`](conversational_app/.env.example) configuration (verify `GOOGLE_CLOUD_PROJECT` points to an active GCP project with Vertex AI enabled, e.g., `travel-agent-511710`):
```bash
# Vertex AI Authentication & Project Configuration
GOOGLE_GENAI_USE_VERTEXAI=1
GOOGLE_CLOUD_PROJECT=travel-agent-511710
GOOGLE_CLOUD_LOCATION=europe-west9

# Global & Per-Sub-Agent Primary & Backup Gemini Model Configuration
GEMINI_MODEL=gemini-3.5-flash-lite
CONVERSATIONAL_MODEL=gemini-3.5-flash-lite
FALLBACK_GEMINI_MODEL=gemini-3.6-flash
CONVERSATIONAL_FALLBACK_MODEL=gemini-3.6-flash
GEMINI_MODEL_LOCATION=global
# Optional per-sub-agent primary & fallback model overrides (fall back to CONVERSATIONAL_MODEL / CONVERSATIONAL_FALLBACK_MODEL):
# ENGAGE_MODEL=gemini-3.5-flash-lite          # ENGAGE_FALLBACK_MODEL=gemini-3.6-flash
# FILTER_MODEL=gemini-3.5-flash-lite          # FILTER_FALLBACK_MODEL=gemini-3.6-flash
# FILTER_SMART_MODEL=gemini-3.5-flash-lite    # FILTER_SMART_FALLBACK_MODEL=gemini-3.6-flash
# INSPIRATION_MODEL=gemini-3.5-flash-lite     # INSPIRATION_FALLBACK_MODEL=gemini-3.6-flash
# JSON_PARSER_MODEL=gemini-3.5-flash-lite     # JSON_PARSER_FALLBACK_MODEL=gemini-3.6-flash

# Server, CORS, Telemetry & E2E Target Endpoints
HOST=0.0.0.0
PORT=8001
ALLOWED_ORIGINS=*
ENABLE_TELEMETRY_PLUGIN=true
CONVERSATIONAL_BASE_URL=http://127.0.0.1:8001
# Optional standalone sub-agent E2E URLs (default http://127.0.0.1:8002–8006):
# ENGAGE_BASE_URL=... FILTER_BASE_URL=... FILTER_SMART_BASE_URL=... INSPIRATION_BASE_URL=... JSON_PARSER_BASE_URL=...
```

Similarly, [`flights_search_app/.env`](flights_search_app/.env.example) uses the same GCP/Vertex AI settings alongside `FLIGHTS_SEARCH_MODEL`, `FLIGHTS_SEARCH_FALLBACK_MODEL`, `PORT=8000`, `FLIGHTS_SEARCH_BASE_URL=http://127.0.0.1:8000`, `ALLOWED_ORIGINS=*`, and `ENABLE_TELEMETRY_PLUGIN=true`.

### 2. Install Python Backend Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r flights_search_app/requirements.txt -r conversational_app/requirements.txt
```

### 3. Install Frontend Dependencies
```bash
cd frontend
npm install
cd ..
```

---

## 🏃 Running Locally

Start each service in its own terminal from the repository root:

1. **Flights Search Agent Service (`flights_search_app`, Port 8000)**
   ```bash
   cd flights_search_app && python3 -m app.main
   ```
2. **Conversational Multi-Agent Workflow Service (`conversational_app`, Port 8001)**
   ```bash
   cd conversational_app && python3 -m app.main
   ```
3. **React Web Dashboard (`frontend`, Port 5173)**
   ```bash
   cd frontend && npm run dev
   ```

Open **http://localhost:5173** in your browser.

<details>
<summary><b>Optional: Run Individual Sub-Agents as Standalone Microservices (Ports <code>8002</code>–<code>8006</code>)</b></summary>

In standard operation, `conversational_app` (`:8001`) executes all 5 sub-agents in-process inside its workflow. To debug individual sub-agents over HTTP or run sub-agent-specific HTTP E2E tests (`conversational_app/tests/e2e/test_<sub_agent>.py`), launch them from `conversational_app/`:
```bash
cd conversational_app
python3 -m app.sub_agents.engage.main        # Port 8002 (POST /api/v1/run-engage | legacy /run-engage)
python3 -m app.sub_agents.filter.main        # Port 8003 (POST /api/v1/run-filter | legacy /run-filter)
python3 -m app.sub_agents.filter_smart.main  # Port 8004 (POST /api/v1/run-filter-smart | legacy /run-filter-smart)
python3 -m app.sub_agents.inspiration.main   # Port 8005 (POST /api/v1/run-inspiration | legacy /run-inspiration)
python3 -m app.sub_agents.json_parser.main   # Port 8006 (POST /api/v1/run-json-parser | legacy /run-json-parser)
```
</details>

---

## ☁ Deploying to Google Cloud (Terraform + Cloud Build)

The scripts in [`deployment/`](deployment/) automate project bootstrapping, least-privilege IAM hardening, Pull Request CI checks, and 5-stage Cloud Build + Terraform deployments across `dev`, `staging`, and `prod`:

1. **Run Pull Request CI Checks (Unit Tests + Frontend Build + Terraform Format/Validate)**
   ```bash
   ./deployment/deploy.sh pr-check dev
   ```

2. **Bootstrap Foundational APIs, Versioned State Bucket & Least-Privilege `travel-agent-cicd` SA**
   *(Note: `deploy.sh` also runs `bootstrap.sh` automatically before submitting any build.)*
   ```bash
   ./deployment/bootstrap.sh dev       # Or: staging | prod | all
   ```

3. **Deploy Full Stack to `dev`, `staging`, or `prod` via Google Cloud Build**
   ```bash
   ./deployment/deploy.sh dev          # Deploys to travel-agent-511710 (envs/dev.tfvars)
   ./deployment/deploy.sh staging      # Deploys to travel-agent-staging-512211 (envs/staging.tfvars)
   ./deployment/deploy.sh prod         # Deploys to travel-agent-prod-512211 (envs/prod.tfvars: europe-west9 + warm europe-west1)
   ```

4. **Roll Back to a Previous Immutable Git Commit SHA (Optional)**
   ```bash
   IMAGE_TAG="<previous-git-sha>" ./deployment/deploy.sh prod
   ```

5. **Redeploy Primary Stack into Any Standby GCP Region (Optional Cold-Standby Recovery)**
   ```bash
   REGION="europe-west4" SECONDARY_REGION="" ./deployment/deploy.sh prod
   ```

---

## 🧪 Testing, AI Evaluation & Verification

### 1. Offline Unit Test Suites
Run the fast offline unit, API contract/versioning, failure-simulation, safety-boundary, and slowdown suites across both backend applications and the React web frontend (no running servers or live cloud calls required):
```bash
(cd flights_search_app && python3 -m pytest tests/unit -v -s)
(cd conversational_app && python3 -m pytest tests/unit -v -s)
(cd frontend && npm test)
```

### 2. Live In-Process Integration & HTTP End-to-End (E2E) Suites
```bash
# 1. Run in-process FastAPI TestClient integration & red-team safety suites with live Vertex AI Gemini calls
(cd flights_search_app && python3 -m pytest tests/integration -v -s)
(cd conversational_app && python3 -m pytest tests/integration -v -s)
(cd conversational_app && python3 -m pytest tests/integration/test_red_team.py -v -s)

# 2. Run live HTTP E2E tests against local servers (:8000, :8001, or standalone sub-agents :8002–:8006)
(cd flights_search_app && python3 -m pytest tests/e2e -v -s)
(cd conversational_app && python3 -m pytest tests/e2e/test_conversational.py -v -s)
(cd conversational_app && python3 -m pytest tests/e2e -v -s)  # Requires standalone sub-agents on :8002–:8006

# 3. Run live HTTP E2E tests against deployed Cloud Run services
(cd flights_search_app && FLIGHTS_SEARCH_BASE_URL="https://<flights-cloud-run-url>" python3 -m pytest tests/e2e -v -s)
(cd conversational_app && CONVERSATIONAL_BASE_URL="https://<conversational-cloud-run-url>" python3 -m pytest tests/e2e/test_conversational.py -v -s)
```

### 3. GEAP 10-Metric AI Quality, Latency & Cost Evaluation Flywheel
Run the 50-scenario synthetic evaluation benchmark, Standard PayGo cost & caching attribution, and automated loss-clustering pipeline in [`conversational_app/tests/eval/`](conversational_app/tests/eval/):

| Metric | Type | Target Threshold | What It Verifies |
| :--- | :---: | :---: | :--- |
| `multi_turn_task_success_v1` | Predefined Rubric | `>= 0.80` | End-to-end user goal completion across the conversational turn. |
| `multi_turn_trajectory_quality_v1` | Predefined Rubric | `>= 0.80` | Sub-agent orchestration trajectory (`engage` → specialist → output normalization). |
| `tool_use_quality` | Custom LLM Judge | `>= 0.80` | Mandatory Google Search calls on qualitative amenities vs. zero calls on structured filters. |
| `coherence` | Predefined Rubric | `>= 0.80` | Clarity of the natural-language response and consistency with returned JSON fields. |
| `schema_and_contract_valid` | Deterministic Python | `>= 0.95` | Strict output schema validity, decision invariants, **zero hallucinated flights & exact flight/price immutability**. |
| `conversation_plan_alignment` | Custom LLM Judge | `>= 0.80` | Alignment with expected ground-truth conversation plan. |
| `latency_seconds` | Deterministic Python | `<= 15.0s` | Single-turn end-to-end latency with per-sub-agent execution breakdown. |
| `cost_per_1k_requests_usd` | Deterministic Python | `<= 15.00 USD/1k` | Total SUT Standard PayGo cost per 1,000 requests (LLM tokens + thinking + Gemini 3 `$14/1k` Google Search grounding). |
| `llm_token_cost_per_1k_usd` | Deterministic Python | `<= 5.00 USD/1k` | Pure LLM token cost per 1,000 requests (uncached input + cached input + visible output + thinking tokens). |
| `total_billable_tokens` | Deterministic Python | `<= 6000.0 tok` | Total LLM tokens consumed per request across all executed sub-agents. |

```bash
cd conversational_app

# 0. (Optional) Regenerate the 50 synthetic evaluation scenarios
python3 -m tests.eval.scripts.generate_scenarios

# 1. Run full inference + 10-metric evaluation (records quality, latency & cost in tests/eval/results/experiments_history.md)
python3 -m tests.eval.scripts.run_evaluation --run-name baseline --set-baseline

# 2. Benchmark an alternative or hybrid Gemini model setup without changing application code
FILTER_SMART_MODEL="gemini-3.1-pro-preview" \
  python3 -m tests.eval.scripts.run_evaluation \
  --run-name hybrid_smart_pro \
  --description "Upgrade only filter_smart to Gemini 3.1 Pro Preview"

# 3. Instant $0 counterfactual repricing on saved traces before spending live API quota
python3 -m tests.eval.scripts.run_evaluation \
  --reuse-run baseline \
  --reprice-only \
  --override-model filter_smart=gemini-3.1-pro-preview \
  --run-name whatif_smart_pro \
  --no-history

# 4. Cluster failure root causes with automated LLM loss analysis
python3 -m tests.eval.scripts.run_loss_analysis
```

### 4. Manual API Testing via `curl`
With `flights_search_app` running on port `8000` and `conversational_app` running on port `8001` (or substituting your deployed Cloud Run URLs; legacy unversioned `/run-*` paths also remain supported with RFC 8594 `Deprecation` headers):

```bash
# 1. Generate 15 simulated flights from Paris to New York (flights_search_app on port 8000)
curl -X POST "http://127.0.0.1:8000/api/v1/run-flights-search" \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "Paris",
    "destination": "New York",
    "departure_date": "2026-05-10",
    "return_date": "2026-05-20",
    "passengers": 1,
    "filters": {"direct": false, "max_price": 900, "max_stops": 1}
  }'

# 2. Filter flights semantically with live Google Search amenity grounding (conversational_app on port 8001)
curl -X POST "http://127.0.0.1:8001/api/v1/run-conversational" \
  -H "Content-Type: application/json" \
  -d '{
    "user_message": "I only want morning flights that have reliable Wi-Fi for remote work.",
    "conversational_history": [],
    "flights_search_input": {
      "origin": "Paris",
      "destination": "New York",
      "departure_date": "2026-05-10",
      "return_date": "2026-05-20",
      "passengers": 1
    },
    "flights_input": [
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
  }'
```

### 5. Interactive Web Dashboard Workflow
1. Open **http://localhost:5173** (or your deployed Cloud Run `frontend` URL).
2. **Search Flights**: Select an origin city, destination city, departure/return dates, and passenger count, then click **Search Flights** to generate 15 realistic itineraries.
3. **Use Manual Filters or Open the Conversational Chat Assistant (`💬`)**:
   - Ask for **direct or price filters** (e.g., *"Show me direct flights under $600"*) to watch the workflow route to the Filter specialist and update the top-level UI filter controls automatically.
   - Ask for **semantic or amenity preferences** (e.g., *"Which morning flights have the most reliable Wi-Fi for remote work?"*) to watch the workflow route to the Smart Filter specialist, ground the answer in live Google Search, and update the displayed flight cards.
   - Ask for **open-ended travel inspiration** (e.g., *"I want to go somewhere warm and sunny in December instead"*) to watch the workflow route to the Inspiration specialist, update the search form destination and dates, and automatically trigger a new flight search.

### 6. Multi-Region Failover & Infrastructure Backup Drills
Run the automated disaster-recovery failover and safe Terraform state backup/restore checks offline (`--local-self-test`, no cloud credentials required) or against live Google Cloud environments:
```bash
# 1. Offline local self-tests (also run automatically on every Pull Request in Cloud Build)
./deployment/validate_dr.sh --local-self-test
./deployment/verify_backups.sh --local-self-test

# 2. Live production Paris-to-Belgium health check, backup URL check & failover speed drill
./deployment/validate_dr.sh --env prod
./deployment/validate_dr.sh --env prod --probe-only   # Readiness-only check without live Gemini calls

# 3. Live safe Terraform state backup restore & Artifact Registry rollback check
./deployment/verify_backups.sh --env prod             # Or: --env staging | --env dev
```

