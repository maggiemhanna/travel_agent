# ✈️ Flights Search & Conversational Multi-Agent Platform

**Flights Search & Conversational Multi-Agent Platform** is a modular, cloud-native travel search and conversational assistant built with **Google ADK (Agent Development Kit v2)**, **Google Cloud Vertex AI (Gemini)**, **Google Search Grounding**, **FastAPI**, **React**, **Terraform**, and **Google Cloud Build**.

Instead of relying on a single monolithic prompt or static form filters, the platform pairs a realistic flight itinerary simulator with a coordinated multi-agent conversational assistant. Through the web dashboard or REST APIs, users can:

- **Search Simulated Global Flights (`POST /run-flights-search`)**: Generate 15 realistic flight itineraries per search across budget, standard, and flagship airlines—accounting for real multi-airport city codes, route durations, timezone differences, overnight arrivals, and user filter preferences (direct flights, maximum price, and maximum stops).
- **Refine Trips Through a Conversational Assistant (`POST /run-conversational`)**: Chat in natural language with a multi-agent workflow that interprets the user's request alongside their active flight search and routes the turn to the appropriate specialist agent.
- **Apply Direct Filters via Natural Language (`POST /run-filter`)**: Convert everyday requests (such as *"show me direct flights under 600 euros"*) into structured price, stop, and direct-flight filters that immediately update the search controls and results on screen.
- **Filter by Qualitative Amenities with Live Google Search (`POST /run-filter-smart`)**: Narrow down candidate flights by specific airlines, morning or afternoon departure windows, layover cities, or on-board amenities (such as reliable Wi-Fi for remote work, extra legroom, or in-flight entertainment) verified through live Google Search, backed by an automatic JSON repair step (`POST /run-json-parser`) if the response formatting needs cleanup.
- **Explore Open-Ended Travel Ideas (`POST /run-inspiration`)**: Turn broad travel goals (such as *"somewhere warm and sunny in December"*) into concrete origin, destination, and date parameters that automatically trigger a fresh flight search in the dashboard.

![Architecture](architecture.png)

---

## 📑 Outline

- [**Core Agentic Architecture (Agentic & Multi-Agent Systems)**](#-core-agentic-architecture-agentic--multi-agent-systems)
  - [1. Agent Orchestration (Stateful Multi-Agent Workflow Graph)](#1-agent-orchestration-stateful-multi-agent-workflow-graph)
  - [2. Tool & Function Calling (Conditional Google Search Grounding)](#2-tool--function-calling-conditional-google-search-grounding)
  - [3. Planning & Reasoning Loops (Intent Triage, Constraint Reasoning & Self-Healing Repair)](#3-planning--reasoning-loops-intent-triage-constraint-reasoning--self-healing-repair)
  - [4. Multi-Agent Coordination (Typed State Handoffs, In-Process Execution & Microservice Isolation)](#4-multi-agent-coordination-typed-state-handoffs-in-process-execution--microservice-isolation)
- [**Cloud Architecture & Production Engineering Layers**](#-cloud-architecture--production-engineering-layers)
  - [**I/ Cloud Architecture**](#i-cloud-architecture)
    - [1. Cloud Deployment (Cloud Architecture & Google Cloud Services Used)](#1-cloud-deployment-cloud-architecture--google-cloud-services-used)
  - [**II/ Operational Excellence**](#ii-operational-excellence)
    - [1. Infrastructure as Code (IaC)](#1-infrastructure-as-code-iac)
    - [2. CI/CD & Deployment](#2-cicd--deployment)
    - [3. Testing & Quality Engineering](#3-testing--quality-engineering)
  - [**III/ Designing for Change**](#iii-designing-for-change)
    - [1. Configuration Management](#1-configuration-management)
    - [2. Modularity & Abstraction](#2-modularity--abstraction)
    - [3. Extensibility](#3-extensibility)
  - [**IV/ Performance & Cost Optimization**](#iv-performance--cost-optimization)
    - [1. Scalability & Elasticity](#1-scalability--elasticity)
    - [2. Resource Efficiency](#2-resource-efficiency)
  - [**V/ Security, Privacy, and Compliance**](#v-security-privacy-and-compliance)
    - [1. Authentication & Authorization](#1-authentication--authorization)
  - [**VI/ Reliability & Resilience**](#vi-reliability--resilience)
    - [2. Graceful Degradation](#2-graceful-degradation)
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
  - [3. GEAP 7-Metric AI Evaluation & Loss Analysis Flywheel](#3-geap-7-metric-ai-evaluation--loss-analysis-flywheel)
  - [4. Manual API Testing via `curl`](#4-manual-api-testing-via-curl)
  - [5. Interactive Web Dashboard Workflow](#5-interactive-web-dashboard-workflow)

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
| **Flights Search Service** (`flights_search_app`) | `8000` | `gemini-3.5-flash-lite` *(configurable)* | **Flight Simulator**: Generates 15 realistic, route-appropriate flight itineraries obeying timezone, duration, and filter rules. | [README](flights_search_app/README.md) |
| **Conversational Workflow** (`conversational_app/app`) | `8001` | ADK v2 `Workflow` + FastAPI | **Orchestrator Gateway**: Executes the multi-agent workflow (`engage` → specialist → output normalization) in-process via `POST /run-conversational`. | [README](conversational_app/README.md#1-conversational-workflow-entrypoint--port-8001) |
| **Engage Sub-Agent** (`sub_agents/engage`) | `8002`* | `gemini-3.5-flash-lite` *(configurable)* | **Intent Triage**: Classifies user messages into `continue`, `filter`, `filter_smart`, or `inspiration_agent`. | [README](conversational_app/README.md#2-engage-sub-agent-port-8002) |
| **Filter Sub-Agent** (`sub_agents/filter`) | `8003`* | `gemini-3.5-flash-lite` *(configurable)* | **Hard Filter Extractor**: Translates natural language into structured filters (`direct`, `max_price`, `max_stops`). | [README](conversational_app/README.md#3-filter-sub-agent-port-8003) |
| **Smart Filter Sub-Agent** (`sub_agents/filter_smart`) | `8004`* | `gemini-3.5-flash-lite` + Google Search | **Semantic & Amenity Filter**: Filters flights by airline, time window, or amenities using live Google Search grounding. | [README](conversational_app/README.md#4-smart-filter-sub-agent-port-8004) |
| **Inspiration Sub-Agent** (`sub_agents/inspiration`) | `8005`* | `gemini-3.5-flash-lite` *(configurable)* | **Discovery Architect**: Turns open-ended trip ideas (*"somewhere warm in December"*) into concrete search parameters. | [README](conversational_app/README.md#5-inspiration-sub-agent-port-8005) |
| **JSON Parser Sub-Agent** (`sub_agents/json_parser`) | `8006`* | `gemini-3.5-flash-lite` *(configurable)* | **Self-Healing Repair**: Repairs malformed or markdown-wrapped JSON from `filter_smart` into strict schema compliance. | [README](conversational_app/README.md#6-json-parser-sub-agent-port-8006) |
| **Web Frontend** (`frontend`) | `5173` | React + Vite + Nginx | **User Interface**: Interactive flight search, filters, pagination, and conversational chat assistant. | [README](frontend/README.md) |

*\*Note: In standard operation (local & Cloud Run), `conversational_app` (`:8001`) executes all 5 sub-agents in-process inside its workflow. Ports `8002`–`8006` are optional standalone FastAPI servers for isolated sub-agent debugging and component E2E tests.*

- **Validated State Handoffs Between Agents:** All five conversational sub-agents coordinate through shared, schema-validated state objects so triage decisions, extracted filter values, filtered flight lists, and suggested search parameters pass cleanly from one specialist to the next and are combined into a single unified JSON response.  
  — *Implemented in [`conversational_app/app/schema.py`](conversational_app/app/schema.py), [`conversational_app/app/agent.py`](conversational_app/app/agent.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*
- **In-Process Workflow Execution with Optional Standalone Microservices:** In production on Cloud Run and during standard local runs, all five conversational sub-agents execute in-process inside the main Conversational service (port `8001`), eliminating internal network hops between agents. For isolated debugging and component-level testing, each sub-agent can also be launched as its own standalone HTTP microservice on ports `8002`–`8006`.  
  — *Implemented in [`conversational_app/app/agent.py`](conversational_app/app/agent.py), [`conversational_app/app/main.py`](conversational_app/app/main.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*
- **Cross-Service Synchronization in the Web Interface:** The React chat assistant coordinates between the Conversational service and the Flights Search service based on the workflow's decision—updating the page's filter controls and visible cards when hard filters are returned, displaying Google Search-verified flights when smart filtering runs, or updating the search form and automatically triggering a new flight search when a new destination or date is suggested.  
  — *Implemented in [`frontend/src/ChatWidget.jsx`](frontend/src/ChatWidget.jsx) & [`frontend/src/App.jsx`](frontend/src/App.jsx)*

---

## 🏗 Cloud Architecture & Production Engineering Layers

The platform is engineered for reproducible multi-environment deployment (`dev`, `staging`, `prod`) on **Google Cloud Platform (GCP)** across **6 architectural domains (`I`–`VI`) and 10 production engineering layers**, verified by the automated test, evaluation, and CI/CD suites in [`flights_search_app/tests/`](flights_search_app/tests/), [`conversational_app/tests/`](conversational_app/tests/), [`deployment/`](deployment/), and [`.cloudbuild/`](.cloudbuild/):

| Domain | Layer | Pillars & Focus Areas |
| :--- | :--- | :--- |
| [**I. Cloud Architecture**](#i-cloud-architecture) | [**1. Cloud Deployment**](#1-cloud-deployment-cloud-architecture--google-cloud-services-used) | Three-service serverless Cloud Run topology across isolated `dev`, `staging`, and `prod` GCP projects, runtime backend URL wiring, and inventory of managed Google Cloud compute, AI, search grounding, registry, CI/CD, state, IAM & logging services |
| [**II. Operational Excellence**](#ii-operational-excellence) | [**1. Infrastructure as Code (IaC)**](#1-infrastructure-as-code-iac) | Declarative Terraform stack, versioned Cloud Storage remote state, remote Cloud Build Terraform execution, reproducible two-phase project bootstrap, and strict `dev`/`staging`/`prod` environment parity |
| [**II. Operational Excellence**](#ii-operational-excellence) | [**2. CI/CD & Deployment**](#2-cicd--deployment) | Pull Request CI checks, 5-stage CD pipelines across `dev`, `staging`, and `prod` (with a manual approval gate on `prod`), zero-downtime Cloud Run revision rollouts with automated smoke checks, and Git-commit image rollback support |
| [**II. Operational Excellence**](#ii-operational-excellence) | [**3. Testing & Quality Engineering**](#3-testing--quality-engineering) | Four-tier verification pyramid (offline unit tests, live Gemini in-process integration tests, live HTTP E2E tests against localhost or Cloud Run, and a 50-scenario 7-metric AI Evaluation & Loss Analysis suite), automated CI test gates, and 1-to-1 service and sub-agent test coverage |
| [**III. Designing for Change**](#iii-designing-for-change) | [**1. Configuration Management**](#1-configuration-management) | Externalized backend and Terraform configuration, startup frontend runtime config generation, multi-project `dev`/`staging`/`prod` vs. local environment separation, and infrastructure/runtime feature flags |
| [**III. Designing for Change**](#iii-designing-for-change) | [**2. Modularity & Abstraction**](#2-modularity--abstraction) | Loose coupling across 3 independent services and 5 self-contained sub-agent packages, strict request/response/state interface schemas, global and per-sub-agent Gemini model swappability, and composable runner & session injection |
| [**III. Designing for Change**](#iii-designing-for-change) | [**3. Extensibility**](#3-extensibility) | Event-driven in-process workflow routing, cross-cutting ADK `BasePlugin` runtime telemetry, plug-and-play sub-agent and custom evaluation metric registries, and GitHub webhook-driven Cloud Build triggers |
| [**IV. Performance & Cost Optimization**](#iv-performance--cost-optimization) | [**1. Scalability & Elasticity**](#1-scalability--elasticity) | Workload-isolated microservice scaling with zero-hop in-process sub-agent execution, environment-tiered horizontal autoscaling (`0–5` dev, `0–10` staging, `1–20` prod) and vertical CPU/memory sizing, managed Cloud Run HTTPS load balancing with non-blocking async I/O, and global Vertex AI inference |
| [**IV. Performance & Cost Optimization**](#iv-performance--cost-optimization) | [**2. Resource Efficiency**](#2-resource-efficiency) | Per-service CPU & memory right-sizing and LLM token/tool budget optimization, scale-to-zero non-prod billing with request-scoped CPU throttling, and automated container registry cleanup with Docker layer caching and Nginx Gzip compression |
| [**V. Security, Privacy, and Compliance**](#v-security-privacy-and-compliance) | [**1. Authentication & Authorization**](#1-authentication--authorization) | Three dedicated custom Service Accounts per project, declarative IAM bindings, active removal of extra permissions from default Google service accounts, non-root backend containers, and keyless Vertex AI authentication with configurable CORS scoping |
| [**VI. Reliability & Resilience**](#vi-reliability--resilience) | [**2. Graceful Degradation**](#2-graceful-degradation) | Self-healing JSON repair fallback, non-JSON runner fallback, independent UI feature isolation between Flight Search and Chat, 3-tier frontend endpoint fallback, 5-attempt exponential backoff retries across all 6 agents + CI/CD smoke retries, and 300-second Cloud Run request timeouts |

---

## I/ Cloud Architecture

### 1. Cloud Deployment (Cloud Architecture & Google Cloud Services Used)

The platform is deployed as three containerized serverless microservices on **Google Cloud Run** in `europe-west9`, promoted across three isolated Google Cloud projects (**Dev**: `travel-agent-511710`, **Staging**: `travel-agent-staging-512211`, **Prod**: `travel-agent-prod-512211`).

- **1.1 End-to-End Cloud Architecture & Request Routing**
  - **Three Independently Deployed Serverless Microservices:**
    - **Web Frontend (`frontend`):** Serves the React single-page application via Nginx and generates a runtime configuration script at container startup containing the environment's live backend service URLs.
    - **Flights Search Service (`flights-search-app`):** Exposes `POST /run-flights-search` (and `GET /` for health checks) to generate 15 realistic flight itineraries per search request.
    - **Conversational Multi-Agent Service (`conversational-app`):** Exposes `POST /run-conversational` (and `GET /` for health checks) to execute the five-agent conversational workflow in-process.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf), [`deployment/terraform/outputs.tf`](deployment/terraform/outputs.tf) & [`deployment/terraform/envs/`](deployment/terraform/envs/)*  
    — *Implemented in [`frontend/Dockerfile`](frontend/Dockerfile), [`flights_search_app/app/main.py`](flights_search_app/app/main.py) & [`conversational_app/app/main.py`](conversational_app/app/main.py)*

- **1.2 Managed Google Cloud Services Used**
  - **Google Cloud Run (Gen2 Serverless Compute):** Hosts `flights-search-app`, `conversational-app`, and `frontend` with managed HTTPS certificates, revision-based traffic switching, environment-specific autoscaling, and production deletion protection.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*
  - **Google Cloud Vertex AI (Gemini Models & GenAI Evaluation Service):** Provides managed Gemini inference (`gemini-3.5-flash-lite` by default) for all six agents and powers the LLM-as-a-Judge evaluation rubrics in the AI evaluation suite.  
    — *Provisioned in [`deployment/terraform/apis.tf`](deployment/terraform/apis.tf), [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) & [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Implemented in [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py), [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/) & [`conversational_app/tests/eval/scripts/run_evaluation.py`](conversational_app/tests/eval/scripts/run_evaluation.py)*
  - **Google Search Grounding:** Grounds the Smart Filter sub-agent in live web search results whenever evaluating qualitative airline or cabin amenities.  
    — *Implemented in [`conversational_app/app/sub_agents/filter_smart/agent.py`](conversational_app/app/sub_agents/filter_smart/agent.py)*
  - **Google Artifact Registry:** Hosts the private regional (`europe-west9`) Docker repository storing versioned container images for all three services with an automated retention policy that keeps the 15 most recent versions.  
    — *Provisioned in [`deployment/terraform/registry.tf`](deployment/terraform/registry.tf) & [`deployment/terraform/apis.tf`](deployment/terraform/apis.tf)*
  - **Google Cloud Build:** Executes Pull Request CI checks, 5-stage CD pipelines across `dev`, `staging`, and `prod`, and automated GitHub triggers with a production manual approval gate.  
    — *Provisioned in [`deployment/terraform/triggers.tf`](deployment/terraform/triggers.tf) & [`deployment/terraform/apis.tf`](deployment/terraform/apis.tf)*  
    — *Implemented in [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml), [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) & [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml)*
  - **Google Cloud Storage (Remote Terraform State Bucket):** Stores versioned Terraform infrastructure state files (`gs://<PROJECT_ID>-tfstate`) isolated per project and environment with uniform bucket-level access.  
    — *Provisioned in [`deployment/bootstrap.sh`](deployment/bootstrap.sh) & [`deployment/terraform/versions.tf`](deployment/terraform/versions.tf)*
  - **Google Cloud IAM & Resource Manager:** Governs least-privilege machine-to-machine permissions across three dedicated Service Accounts per project (`travel-agent-cicd`, `travel-agent-runtime`, `travel-agent-frontend`).  
    — *Provisioned in [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) & [`deployment/bootstrap.sh`](deployment/bootstrap.sh)*
  - **Google Cloud Logging & Google Cloud Trace:** Collects container operational logs, Cloud Build pipeline logs, and distributed request trace data.  
    — *Provisioned in [`deployment/terraform/apis.tf`](deployment/terraform/apis.tf) & [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf)*  
    — *Implemented in [`flights_search_app/app/app_utils/logging.py`](flights_search_app/app/app_utils/logging.py) & [`conversational_app/app/app_utils/logging.py`](conversational_app/app/app_utils/logging.py)*

---

## II/ [OPERATIONAL EXCELLENCE]

### 1. Infrastructure as Code (IaC)

All cloud APIs, service accounts, IAM policies, container registries, Cloud Run microservices, and CI/CD triggers are managed declaratively as version-controlled Terraform code rather than manual console changes:

- **1.1 Pillar 1 — Declarative Terraform Stack & Remote State**
  - **Full-Stack Declarative Terraform Modules:** Modular Terraform configuration files provision all 10 required Google Cloud APIs, the regional Artifact Registry repository and cleanup policy, dedicated runtime Service Accounts and IAM bindings, all three Cloud Run microservices, and Cloud Build GitHub triggers.  
    — *Provisioned in [`deployment/terraform/apis.tf`](deployment/terraform/apis.tf), [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf), [`deployment/terraform/registry.tf`](deployment/terraform/registry.tf), [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf), [`deployment/terraform/triggers.tf`](deployment/terraform/triggers.tf), [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf), [`deployment/terraform/outputs.tf`](deployment/terraform/outputs.tf) & [`deployment/terraform/versions.tf`](deployment/terraform/versions.tf)*
  - **Remote Versioned Cloud Storage State Backend:** Terraform stores its infrastructure state in a dedicated, versioned Google Cloud Storage bucket per project. Bucket and environment prefix parameters are passed dynamically at initialization time so the Terraform files remain portable across projects without hardcoded bucket names.  
    — *Provisioned in [`deployment/bootstrap.sh`](deployment/bootstrap.sh) & [`deployment/terraform/versions.tf`](deployment/terraform/versions.tf)*  
    — *Called in [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) & [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml)*

- **1.2 Pillar 2 — Cloud-Native Terraform Execution (`Cloud Build`)**
  - **Remote Cloud Build Terraform Runner:** All Terraform initialization, formatting checks, schema validation, targeted bootstrap steps, and full Cloud Run rollouts execute inside Google Cloud Build using a pinned Terraform container image (`1.9.8`) under the dedicated CI/CD Service Account—requiring no local Terraform installation on developer machines.  
    — *Implemented in [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml), [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml), [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml) & [`deployment/deploy.sh`](deployment/deploy.sh)*

- **1.3 Pillar 3 — Reproducible Environments**
  - **Two-Phase Bootstrap & Automatic Backend URL Wiring:** To ensure brand-new Google Cloud projects deploy cleanly on the first run, the pipeline first provisions foundational APIs, Artifact Registry, and Service Accounts before building and pushing container images. Once the images exist, the full Terraform pass deploys the backend Cloud Run services and automatically injects their live URLs into the frontend service.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Implemented in [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) & [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml)*
  - **Pinned Container Images, Lockfiles & Input Validation:** All Dockerfiles and pipelines pin exact runtime and tool versions (`python:3.11-slim`, `node:20-alpine`, `nginx:1.27-alpine`, `hashicorp/terraform:1.9.8`), install frontend packages reproducibly via `npm ci`, and validate environment names during the Terraform planning phase.  
    — *Provisioned in [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf)*  
    — *Implemented in [`flights_search_app/Dockerfile`](flights_search_app/Dockerfile), [`conversational_app/Dockerfile`](conversational_app/Dockerfile), [`frontend/Dockerfile`](frontend/Dockerfile) & [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml)*

- **1.4 Pillar 4 — Environment Parity**
  - **Single Parameterized Terraform Codebase Across `dev`, `staging` & `prod`:** Development, staging, and production share the exact same Terraform files, using environment-specific `.tfvars` files to configure project IDs and scaling bounds while automatically enabling production-only safeguards such as Cloud Run deletion protection in `prod`.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf) & [`deployment/terraform/envs/`](deployment/terraform/envs/)*
  - **Build-Once, Run-Anywhere Frontend Image:** The compiled frontend container image contains no hardcoded environment URLs and can be promoted unchanged across development, staging, and production environments.  
    — *Implemented in [`frontend/Dockerfile`](frontend/Dockerfile) & [`frontend/nginx.conf.template`](frontend/nginx.conf.template)*

> **Note on Unimplemented / Non-Relevant Pillars:**
> - **Pulumi (*Not Implemented — Not Relevant*):** Pulumi is not used because 100% of our Google Cloud infrastructure across `dev`, `staging`, and `prod` is declaratively defined and managed with **Terraform** ([`deployment/terraform/*.tf`](deployment/terraform/)), which integrates directly with our versioned Cloud Storage state backend and Cloud Build pipelines.

---

### 2. CI/CD & Deployment

Code verification, container builds, infrastructure rollouts, and post-deploy health checks are orchestrated through automated Google Cloud Build pipelines across three isolated GCP projects:

| Environment | GCP Project ID | Terraform Vars | Pipeline & Trigger | Scaling (`min` / `max`) |
| :--- | :--- | :--- | :--- | :---: |
| **Pull Requests** | `travel-agent-511710` | — | [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml) — PRs targeting `main` | — |
| **Dev** | `travel-agent-511710` | [`envs/dev.tfvars`](deployment/terraform/envs/dev.tfvars) | [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml) — Active feature iteration | `0` / `5` |
| **Staging** | `travel-agent-staging-512211` | [`envs/staging.tfvars`](deployment/terraform/envs/staging.tfvars) | [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) — Automated on merge to `main` | `0` / `10` |
| **Prod** | `travel-agent-prod-512211` | [`envs/prod.tfvars`](deployment/terraform/envs/prod.tfvars) | [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml) — `v*` Git tag + **Manual Approval Gate** | `1` / `20` |

- **2.1 Pillar 1 — Pipeline Design**
  - **Pull Request Continuous Integration Gate:** Runs automatically on pull requests targeting `main` (or via `./deployment/deploy.sh pr-check dev`) to execute offline unit tests for both backend applications, verify that the React production bundle compiles cleanly, and check Terraform formatting and schema validity before code can be merged.  
    — *Provisioned in [`deployment/terraform/triggers.tf`](deployment/terraform/triggers.tf)*  
    — *Implemented in [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml) & [`deployment/deploy.sh`](deployment/deploy.sh)*
  - **Five-Stage Continuous Delivery Pipeline (`dev`, `staging`, `prod`):**
    1. **Stage 1 — CI Unit Test Gate:** Runs the offline unit test suites across both backend services and halts the pipeline immediately if any test fails.
    2. **Stage 2 — Targeted Infrastructure Bootstrap:** Enables required Google Cloud APIs, provisions Artifact Registry, and configures the dedicated runtime Service Accounts.
    3. **Stage 3 — Parallel Container Build & Push:** Builds all three service images in parallel using Docker layer caching and pushes both the Git commit hash tag and `latest` to Artifact Registry.
    4. **Stage 4 — Cloud Run Infrastructure Rollout:** Applies the full Terraform stack to deploy the new Cloud Run revisions, inject model settings, and wire the live backend URLs into the frontend service.
    5. **Stage 5 — Post-Deploy Smoke Verification:** Pings the live health endpoints on both backend services and verifies the generated runtime configuration on the live frontend with automatic retries.  
    — *Implemented in [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml), [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml) & [`deployment/deploy.sh`](deployment/deploy.sh)*
  - **Manual Approval Gate for Production Releases:** Production releases are triggered only when a semantic version tag (`v*`) is pushed and require explicit human approval in Cloud Build before deployment begins.  
    — *Provisioned in [`deployment/terraform/triggers.tf`](deployment/terraform/triggers.tf)*

- **2.2 Pillar 2 — Deployment Strategies**
  - **Immutable Cloud Run Revision Rollouts & Zero-Downtime Traffic Switching:** Deploying a new container image tag creates a brand-new, immutable Cloud Run revision for each service without modifying running containers in place. Cloud Run starts the new revision before atomically shifting live traffic over from the previous revision with zero downtime, followed immediately by Stage 5 smoke checks.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Called in [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) & [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml)*

- **2.3 Pillar 3 — Rollback Support**
  - **Git-Commit Image Tag Rollbacks:** Because every deployment tags images in Artifact Registry with the exact Git commit hash alongside `latest` (and retains the 15 most recent versions), operators can roll back all three services to any previously tested release in a single command (`IMAGE_TAG=<previous-git-sha> ./deployment/deploy.sh prod`).  
    — *Provisioned in [`deployment/terraform/registry.tf`](deployment/terraform/registry.tf) & [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Called in [`deployment/deploy.sh`](deployment/deploy.sh)*
  - **Versioned Infrastructure State Recovery:** Object versioning on the Terraform state bucket retains previous state versions so operators can recover from unintended infrastructure changes.  
    — *Provisioned in [`deployment/bootstrap.sh`](deployment/bootstrap.sh)*

> **Note on Unimplemented Pillars:**
> - **Progressive Traffic Splitting (Blue/Green & Canary) & Automated Rollback Triggers (*Not Implemented — Relevant*):** While Cloud Run performs zero-downtime revision swaps, runs post-deploy smoke checks, and supports one-command Git-commit rollbacks, percentage-based blue/green or canary traffic splitting across revisions and automated rollback triggers tied to post-deploy smoke failures or error alerts are not yet implemented and remain relevant future production enhancements.

---

### 3. Testing & Quality Engineering

Quality, schema compliance, sub-agent routing, non-hallucination, and response latency are verified across a four-tier testing and AI evaluation pyramid:

- **3.1 Pillar 1 — Unit, Integration, End-to-End (E2E) & AI Evaluation Testing**
  - **Tier 1 — Offline Unit Tests (`tests/unit/`):** Verifies service health endpoints, validates request schemas against sample JSON fixtures, and confirms that invalid or empty requests are rejected with `HTTP 422` across both backend applications and all five sub-agents without requiring live cloud calls.  
    — *Implemented in [`flights_search_app/tests/unit/test_flights_search.py`](flights_search_app/tests/unit/test_flights_search.py), [`conversational_app/tests/unit/test_conversational.py`](conversational_app/tests/unit/test_conversational.py), [`conversational_app/tests/unit/test_engage.py`](conversational_app/tests/unit/test_engage.py), [`conversational_app/tests/unit/test_filter.py`](conversational_app/tests/unit/test_filter.py), [`conversational_app/tests/unit/test_filter_smart.py`](conversational_app/tests/unit/test_filter_smart.py), [`conversational_app/tests/unit/test_inspiration.py`](conversational_app/tests/unit/test_inspiration.py) & [`conversational_app/tests/unit/test_json_parser.py`](conversational_app/tests/unit/test_json_parser.py)*
  - **Tier 2 — Live In-Process Integration Tests (`tests/integration/`):** Exercises the full FastAPI and ADK runner stack in-process using `TestClient` with live Vertex AI Gemini calls across the Flight Search service, the Conversational workflow, and all five individual sub-agents, verifying that every returned response satisfies its output schema.  
    — *Implemented in [`flights_search_app/tests/integration/test_flights_search.py`](flights_search_app/tests/integration/test_flights_search.py), [`conversational_app/tests/integration/test_conversational.py`](conversational_app/tests/integration/test_conversational.py), [`conversational_app/tests/integration/test_engage.py`](conversational_app/tests/integration/test_engage.py), [`conversational_app/tests/integration/test_filter.py`](conversational_app/tests/integration/test_filter.py), [`conversational_app/tests/integration/test_filter_smart.py`](conversational_app/tests/integration/test_filter_smart.py), [`conversational_app/tests/integration/test_inspiration.py`](conversational_app/tests/integration/test_inspiration.py) & [`conversational_app/tests/integration/test_json_parser.py`](conversational_app/tests/integration/test_json_parser.py)*
  - **Tier 3 — Live HTTP End-to-End (E2E) Tests (`tests/e2e/`):** Sends real HTTP requests over the network to locally running servers (`127.0.0.1:8000`–`8006`) or live deployed Cloud Run URLs to verify end-to-end service reachability and response contracts.  
    — *Implemented in [`flights_search_app/tests/e2e/test_flights_search.py`](flights_search_app/tests/e2e/test_flights_search.py), [`conversational_app/tests/e2e/test_conversational.py`](conversational_app/tests/e2e/test_conversational.py), [`conversational_app/tests/e2e/test_engage.py`](conversational_app/tests/e2e/test_engage.py), [`conversational_app/tests/e2e/test_filter.py`](conversational_app/tests/e2e/test_filter.py), [`conversational_app/tests/e2e/test_filter_smart.py`](conversational_app/tests/e2e/test_filter_smart.py), [`conversational_app/tests/e2e/test_inspiration.py`](conversational_app/tests/e2e/test_inspiration.py) & [`conversational_app/tests/e2e/test_json_parser.py`](conversational_app/tests/e2e/test_json_parser.py)*
  - **Tier 4 — 7-Metric AI Quality, Non-Hallucination & Latency Evaluation Suite (`conversational_app/tests/eval/`):** Benchmarks the conversational workflow against 50 synthetic travel scenarios across 7 automated metrics—measuring task completion, sub-agent routing trajectory, appropriate Google Search tool usage, response coherence, deterministic schema compliance with zero hallucinated flight numbers (`>= 0.95`), ground-truth plan alignment, and single-turn response latency (`<= 15.0s`)—paired with automated failure root-cause clustering and experiment history tracking.  
    — *Implemented in [`conversational_app/tests/eval/configs/eval_config.json`](conversational_app/tests/eval/configs/eval_config.json), [`conversational_app/tests/eval/metrics/custom_metrics.py`](conversational_app/tests/eval/metrics/custom_metrics.py), [`conversational_app/tests/eval/scripts/generate_scenarios.py`](conversational_app/tests/eval/scripts/generate_scenarios.py), [`conversational_app/tests/eval/scripts/run_evaluation.py`](conversational_app/tests/eval/scripts/run_evaluation.py) & [`conversational_app/tests/eval/scripts/run_loss_analysis.py`](conversational_app/tests/eval/scripts/run_loss_analysis.py)*

- **3.2 Pillar 2 — Test Automation**
  - **Automated Pre-Build & Post-Deploy Quality Gates:** Every Cloud Build pipeline (`pr_checks.yaml`, `dev.yaml`, `staging.yaml`, `prod.yaml`) automatically runs the offline unit test suites before building containers or applying Terraform changes, while PR checks additionally automate frontend build verification and Terraform schema validation, and CD pipelines automate post-deploy HTTP smoke checks.  
    — *Implemented in [`.cloudbuild/pr_checks.yaml`](.cloudbuild/pr_checks.yaml), [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) & [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml)*

- **3.3 Pillar 3 — Test Coverage Across Services & Sub-Agents**
  - **1-to-1 Service & Sub-Agent Test Coverage:** Every backend service and sub-agent (`flights_search`, `conversational`, `engage`, `filter`, `filter_smart`, `inspiration`, `json_parser`) is paired with its own dedicated JSON test fixtures, unit test suite, integration test suite, and E2E test suite.  
    — *Implemented in [`flights_search_app/tests/`](flights_search_app/tests/) & [`conversational_app/tests/`](conversational_app/tests/)*

> **Note on Unimplemented Pillars:**
> - **Automated Load & Stress Benchmarking, Browser UI E2E Tests & Code-Coverage Threshold Gates (*Not Implemented — Relevant*):** While the AI evaluation suite measures single-turn and per-sub-agent latency (`<= 15.0s`) across 50 scenarios with parallel worker threads, a dedicated HTTP load-testing tool (such as Locust or k6 stress-testing Cloud Run autoscaling under high concurrent traffic), automated browser UI tests (such as Playwright or Cypress for the React dashboard), and automated code-coverage percentage gates in CI are not yet implemented and remain relevant future enhancements.

---

## III/ [DESIGNING FOR CHANGE]

### 1. Configuration Management

All AI model selections, Vertex AI locations, server ports, CORS origins, scaling bounds, and frontend backend URLs are externalized from application code:

- **1.1 Pillar 1 — Externalized Configuration**
  - **Centralized Backend Configuration Modules:** All backend settings—including global and per-sub-agent Gemini model names, Vertex AI model locations, server hosts and ports, allowed CORS origins, and standalone sub-agent URLs—are loaded from environment variables through dedicated configuration modules rather than hardcoded across files.  
    — *Implemented in [`flights_search_app/app/config.py`](flights_search_app/app/config.py) & [`conversational_app/app/config.py`](conversational_app/app/config.py)*
  - **Parameterized Terraform Infrastructure Configuration:** Terraform input variables and per-environment `.tfvars` files control project IDs, region, model versions, minimum and maximum container counts, per-service CPU and memory limits, CORS origins, and Git trigger toggles without editing infrastructure code.  
    — *Provisioned in [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf), [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf) & [`deployment/terraform/envs/`](deployment/terraform/envs/)*
  - **Startup Runtime Configuration for the Web Frontend:** Single-page web apps normally bake backend URLs into static JavaScript files at build time—before cloud resources exist. Instead, when the frontend container starts on Cloud Run, an Nginx startup script reads the backend service URLs injected by Terraform and writes a runtime configuration file (`/env-config.js` with browser caching disabled) that the browser loads before starting React.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Implemented in [`frontend/Dockerfile`](frontend/Dockerfile), [`frontend/nginx.conf.template`](frontend/nginx.conf.template), [`frontend/index.html`](frontend/index.html), [`frontend/src/App.jsx`](frontend/src/App.jsx) & [`frontend/src/ChatWidget.jsx`](frontend/src/ChatWidget.jsx)*

- **1.2 Pillar 2 — Environment Separation**
  - **Isolated Multi-Project Cloud Environments (`dev`, `staging`, `prod`) vs. Local Development:** Local development loads `.env` files (templated by `.env.example` in each app) and binds to localhost ports (`8000`–`8006` and `5173`). Cloud deployments isolate `dev` (`travel-agent-511710`), `staging` (`travel-agent-staging-512211`), and `prod` (`travel-agent-prod-512211`) into separate Google Cloud projects, separate remote Terraform state prefixes, and environment-specific `.tfvars` scaling and protection profiles.  
    — *Provisioned in [`deployment/bootstrap.sh`](deployment/bootstrap.sh), [`deployment/deploy.sh`](deployment/deploy.sh) & [`deployment/terraform/envs/`](deployment/terraform/envs/)*  
    — *Implemented in [`flights_search_app/.env.example`](flights_search_app/.env.example), [`conversational_app/.env.example`](conversational_app/.env.example) & [`frontend/.env.example`](frontend/.env.example)*

- **1.3 Pillar 3 — Feature & Infrastructure Flags**
  - **Infrastructure & Runtime Capability Toggles:** Boolean and environment-driven toggles allow operators to control phased Cloud Run service provisioning during initial project bootstrap, enable or disable automated GitHub Cloud Build triggers, control public HTTP access, enforce production-only deletion protection, and toggle Vertex AI credential mode.  
    — *Provisioned in [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf), [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf) & [`deployment/terraform/triggers.tf`](deployment/terraform/triggers.tf)*

> **Note on Unimplemented Pillars:**
> - **Dynamic Remote Feature-Flag Evaluation Service (*Not Implemented — Relevant*):** Configuration flags are currently evaluated from environment variables injected into Cloud Run revisions (requiring a revision update to toggle in production). Integrating a dynamic remote feature-flag service (such as Firebase Remote Config or OpenFeature for live percentage-based or per-user rollouts without redeploying containers) is not yet implemented and is a relevant future enhancement.

---

### 2. Modularity & Abstraction

The platform is organized around decoupled service boundaries, typed data contracts, swappable AI models, and composable runner abstractions so domain logic and infrastructure evolve independently:

- **2.1 Pillar 1 — Loose Coupling**
  - **Three Decoupled Application Services:** The Flights Search service, Conversational Multi-Agent service, and React Web Frontend live in independent directories with their own Dockerfiles, dependency manifests, configuration modules, and test suites—sharing zero cross-service Python imports or coupled databases.  
    — *Implemented in [`flights_search_app/`](flights_search_app/), [`conversational_app/`](conversational_app/) & [`frontend/`](frontend/)*
  - **Self-Contained Sub-Agent Packages:** Each of the five conversational sub-agents (`engage`, `filter`, `filter_smart`, `inspiration`, `json_parser`) encapsulates its own agent definition, system prompt, data schemas, and standalone FastAPI server inside a dedicated folder so updating one specialist's prompt or schema never affects the others.  
    — *Implemented in [`conversational_app/app/sub_agents/engage/`](conversational_app/app/sub_agents/engage/), [`conversational_app/app/sub_agents/filter/`](conversational_app/app/sub_agents/filter/), [`conversational_app/app/sub_agents/filter_smart/`](conversational_app/app/sub_agents/filter_smart/), [`conversational_app/app/sub_agents/inspiration/`](conversational_app/app/sub_agents/inspiration/) & [`conversational_app/app/sub_agents/json_parser/`](conversational_app/app/sub_agents/json_parser/)*

- **2.2 Pillar 2 — Interface Contracts**
  - **Strict Request, Response & Workflow State Schemas:** Every REST endpoint, individual agent, and multi-agent workflow is governed by explicit Pydantic data schemas—validating search parameters, flight lists, routing decisions, and filter types upfront and rejecting malformed requests (`HTTP 422`) before agent execution begins.  
    — *Implemented in [`flights_search_app/app/schema.py`](flights_search_app/app/schema.py), [`conversational_app/app/schema.py`](conversational_app/app/schema.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*

- **2.3 Pillar 3 — Model Swappability**
  - **Global & Per-Sub-Agent Gemini Model Switching:** Every agent initializes its language model through externalized configuration variables rather than hardcoded model strings. Operators can switch the default Gemini model across an entire service or override individual sub-agents (for example, upgrading only the Smart Filter specialist to a larger model while keeping intent triage on `gemini-3.5-flash-lite`) via `.env` or Terraform `.tfvars` with zero code changes—as demonstrated in our multi-model evaluation benchmarks.  
    — *Provisioned in [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf) & [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Implemented in [`flights_search_app/app/config.py`](flights_search_app/app/config.py), [`conversational_app/app/config.py`](conversational_app/app/config.py), [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*  
    — *Verified in [`conversational_app/tests/eval/results/experiments_history.md`](conversational_app/tests/eval/results/experiments_history.md)*

- **2.4 Pillar 4 — Dependency Injection**
  - **Composable Runner & Session Service Wiring:** FastAPI route handlers and the evaluation harness construct ADK runners by injecting a fresh in-memory session service per request, while the root workflow composes imported sub-agent objects declaratively—allowing the exact same agent definitions to run inside the production API server, in-process integration tests, or the batch evaluation runner.  
    — *Implemented in [`flights_search_app/app/main.py`](flights_search_app/app/main.py), [`conversational_app/app/main.py`](conversational_app/app/main.py), [`conversational_app/app/agent.py`](conversational_app/app/agent.py) & [`conversational_app/tests/eval/scripts/run_evaluation.py`](conversational_app/tests/eval/scripts/run_evaluation.py)*

> **Note on Unimplemented Pillars:**
> - **Route-Level FastAPI `Depends()` Providers for Offline Fake LLM Injection (*Not Implemented — Relevant*):** While session and runner setup is modularized in helper functions, refactoring FastAPI route handlers to accept runner factories via `Depends(...)` so offline unit tests can inject deterministic mock LLM responses without live Vertex AI calls is a relevant future enhancement.

---

### 3. Extensibility

New specialist sub-agents, tools, evaluation metrics, and CI/CD pipelines can be added through standardized plugin contracts and event-driven routing:

- **3.1 Pillar 1 — Event-Driven In-Process Workflow Routing**
  - **Event-Driven State Transitions Inside the ADK Workflow:** Within the conversational orchestrator, routing steps emit structured workflow events carrying the next branch key and updated session state to trigger downstream specialist agents. During execution, the runner streams these internal events asynchronously so the evaluation harness can record sub-agent trajectories, tool calls, and per-agent latency breakdowns.  
    — *Implemented in [`conversational_app/app/agent.py`](conversational_app/app/agent.py), [`conversational_app/app/main.py`](conversational_app/app/main.py) & [`conversational_app/tests/eval/scripts/run_evaluation.py`](conversational_app/tests/eval/scripts/run_evaluation.py)*

- **3.2 Pillar 2 — Plugin Patterns (ADK Runtime Plugins, Sub-Agent, Tool & Evaluation Metric Registries)**
  - **Cross-Cutting ADK Runtime Plugin (`ExecutionTelemetryPlugin`):** Both backend applications register a concurrency-safe `BasePlugin` (`ExecutionTelemetryPlugin`, toggleable via `ENABLE_TELEMETRY_PLUGIN`) on their ADK `App` containers (`before_run_callback`, `before_agent_callback`, `after_model_callback`, `on_model_error_callback`, `after_run_callback`, `on_run_error_callback`). Isolating state by `invocation_id`, it automatically captures and logs per-agent execution latency, prompt/output token usage (`usage_metadata`), and live Google Search grounding queries (`grounding_metadata`) across the entire workflow and standalone sub-agents without coupling observability code into individual specialist packages.  
    — *Implemented in [`conversational_app/app/app_utils/telemetry_plugin.py`](conversational_app/app/app_utils/telemetry_plugin.py), [`flights_search_app/app/app_utils/telemetry_plugin.py`](flights_search_app/app/app_utils/telemetry_plugin.py), [`conversational_app/app/agent.py`](conversational_app/app/agent.py), [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*  
    — *Verified in [`conversational_app/tests/unit/test_conversational.py`](conversational_app/tests/unit/test_conversational.py) & [`flights_search_app/tests/unit/test_flights_search.py`](flights_search_app/tests/unit/test_flights_search.py)*
  - **Plug-and-Play Sub-Agent & Tool Pattern:** Every sub-agent under `conversational_app/app/sub_agents/` follows an identical four-file structure (`agent.py`, `prompt.py`, `schema.py`, `main.py`). Adding a new specialist capability (such as a hotel or baggage assistant) requires only dropping in a new sub-agent folder, adding its route key to the workflow graph, and optionally attaching tools to its agent definition.  
    — *Implemented in [`conversational_app/app/agent.py`](conversational_app/app/agent.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*
  - **Pluggable Evaluation Metric Registries:** The evaluation suite uses dictionary-based plugin registries for both deterministic Python metrics and custom LLM-as-a-Judge rubric templates, resolving active metrics dynamically from [`eval_config.json`](conversational_app/tests/eval/configs/eval_config.json) at runtime without modifying the evaluation runner script.  
    — *Implemented in [`conversational_app/tests/eval/metrics/custom_metrics.py`](conversational_app/tests/eval/metrics/custom_metrics.py) & [`conversational_app/tests/eval/configs/eval_config.json`](conversational_app/tests/eval/configs/eval_config.json)*

- **3.3 Pillar 3 — Webhook-Driven CI/CD Automation**
  - **GitHub Webhook Triggers in Cloud Build:** Terraform provisions automated Cloud Build triggers that listen for GitHub pull request and push webhook events to launch CI validation and CD deployment pipelines automatically.  
    — *Provisioned in [`deployment/terraform/triggers.tf`](deployment/terraform/triggers.tf)*

> **Note on Unimplemented Pillars:**
> - **Distributed Cloud Event Brokers (Pub/Sub / Eventarc) & Outbound Application Webhooks (*Not Implemented — Relevant*):** While the conversational workflow uses ADK's in-process event graph, `ExecutionTelemetryPlugin` hooks global ADK lifecycle callbacks, and CI/CD uses GitHub webhook triggers, a distributed cloud message bus (such as Google Cloud Pub/Sub or Eventarc) and outbound application webhooks (such as asynchronous price-alert callbacks) are not yet implemented and remain relevant future extensibility enhancements.

---

## IV/ [PERFORMANCE & COST OPTIMIZATION]

### 1. Scalability & Elasticity

The platform separates flight simulation from multi-step conversational reasoning, eliminates internal network hops between sub-agents, and scales horizontally across environment-tiered Cloud Run pools and global Vertex AI endpoints:

- **1.1 Pillar 1 — Horizontal & Vertical Scaling Strategies**
  - **Workload-Isolated Horizontal Microservice Scaling:** Deploying Flight Search (`flights-search-app`), Conversational Orchestration (`conversational-app`), and the Web Frontend (`frontend`) as three separate Cloud Run services allows each tier to scale out horizontally according to its own traffic demand without competing for CPU or memory.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*
  - **Parameterized Vertical Compute Sizing:** Per-container CPU and memory limits are parameterized in Terraform (`2 vCPU / 2 GiB` for backend AI services and `1 vCPU / 512 MiB` for the Nginx frontend) so operators can scale vertical container capacity per environment via `.tfvars` files.  
    — *Provisioned in [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf), [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf) & [`deployment/terraform/envs/`](deployment/terraform/envs/)*

- **1.2 Pillar 2 — Environment-Tiered Autoscaling Policies**
  - **Environment-Specific Minimum & Maximum Instance Bounds:** Cloud Run automatically adds or removes container instances based on incoming traffic using bounds matched to each environment:
    - **Dev ([`envs/dev.tfvars`](deployment/terraform/envs/dev.tfvars)):** `0` to `5` instances per service.
    - **Staging ([`envs/staging.tfvars`](deployment/terraform/envs/staging.tfvars)):** `0` to `10` instances per service.
    - **Prod ([`envs/prod.tfvars`](deployment/terraform/envs/prod.tfvars)):** `1` minimum warm instance (eliminating cold-start delays for production users) scaling up to `20` instances per service during traffic spikes.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf), [`deployment/terraform/envs/dev.tfvars`](deployment/terraform/envs/dev.tfvars), [`deployment/terraform/envs/staging.tfvars`](deployment/terraform/envs/staging.tfvars) & [`deployment/terraform/envs/prod.tfvars`](deployment/terraform/envs/prod.tfvars)*

- **1.3 Pillar 3 — Load Balancing & High-Throughput API Design**
  - **Built-In Cloud Run HTTPS Load Balancing:** Each Cloud Run service is fronted by Google Cloud's managed global HTTPS load balancer, which terminates TLS at the edge and distributes concurrent requests across healthy container instances.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*
  - **Zero-Network-Hop In-Process Sub-Agent Execution:** Running all five conversational sub-agents in-process inside `conversational-app` avoids 2–3 internal HTTP round-trips and serialization steps on every chat turn.  
    — *Implemented in [`conversational_app/app/agent.py`](conversational_app/app/agent.py) & [`conversational_app/app/main.py`](conversational_app/app/main.py)*
  - **Non-Blocking Asynchronous API Execution:** All backend endpoints run asynchronously on FastAPI and Uvicorn with isolated per-request in-memory sessions, allowing each container to handle multiple concurrent requests while waiting on Vertex AI network I/O.  
    — *Implemented in [`flights_search_app/app/main.py`](flights_search_app/app/main.py) & [`conversational_app/app/main.py`](conversational_app/app/main.py)*

- **1.4 Pillar 4 — Scalable Managed Vertex AI Inference**
  - **Global Vertex AI Endpoint Routing:** All six agents route inference calls through Vertex AI's `global` endpoint location by default, drawing from Google Cloud's globally pooled inference capacity for higher quota availability and lower tail latency.  
    — *Provisioned in [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf) & [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Implemented in [`flights_search_app/app/config.py`](flights_search_app/app/config.py), [`conversational_app/app/config.py`](conversational_app/app/config.py), [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*

> **Note on Unimplemented / Non-Relevant Pillars:**
> - **HPC / GPU Cluster Scaling (*Not Implemented — Not Relevant*):** Managing self-hosted HPC or GPU Kubernetes clusters is not relevant to this serverless architecture because all LLM inference and search grounding are offloaded to fully managed, auto-scaling **Google Cloud Vertex AI** APIs while application services run on serverless **Google Cloud Run**.
> - **Unified Global External Application Load Balancer (*Not Implemented — Relevant*):** Each microservice currently uses Cloud Run's built-in `.run.app` HTTPS load balancer; fronting all three services behind a single Global External Application Load Balancer with path-based routing and Cloud Armor WAF is a relevant future enhancement.

---

### 2. Resource Efficiency

Compute allocations, model token/tool budgets, idle instance billing, and container registry storage are tuned so non-production environments cost `$0` when idle while active workloads avoid wasted compute and tokens:

- **2.1 Pillar 1 — Compute & Inference Right-Sizing**
  - **Right-Sized CPU & Memory per Tier:** Compute resources are matched to each service's footprint—allocating `2 vCPU` and `2 GiB` of RAM to the Python AI backend services (`flights-search-app` and `conversational-app`) and a lightweight `1 vCPU` and `512 MiB` of RAM to the static Nginx `frontend`.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf) & [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf)*
  - **Model Selection, Thinking-Budget & Tool-Call Optimization:**
    - All six agents default to fast, cost-efficient `gemini-3.5-flash-lite` (which achieved a `0.946` quality score at `4.64s` average turn latency in [`experiments_history.md`](conversational_app/tests/eval/results/experiments_history.md)) while allowing selective per-agent model overrides.
    - The Flight Search agent disables extended thinking tokens (`thinking_budget=0`) during structured itinerary generation, all agents scope context strictly to required input fields, and the Smart Filter agent skips Google Search whenever structured flight fields are sufficient.  
    — *Implemented in [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py), [`conversational_app/app/config.py`](conversational_app/app/config.py) & [`conversational_app/app/sub_agents/filter_smart/prompt.py`](conversational_app/app/sub_agents/filter_smart/prompt.py)*

- **2.2 Pillar 2 — Cost-Aware Autoscaling & Request-Scoped CPU Billing**
  - **Scale-to-Zero Idle Instance Elimination in `dev` & `staging`:** Development and staging environments set their minimum instance count to zero across all services so containers spin down completely when no requests are running.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf), [`deployment/terraform/envs/dev.tfvars`](deployment/terraform/envs/dev.tfvars) & [`deployment/terraform/envs/staging.tfvars`](deployment/terraform/envs/staging.tfvars)*
  - **Request-Scoped CPU Billing:** Cloud Run CPU throttling is enabled whenever scale-to-zero is active (and on the frontend across all environments) so CPU is allocated and billed only while a container is actively processing an HTTP request.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*

- **2.3 Pillar 3 — Storage, Build & Bandwidth Efficiency**
  - **Automated 15-Version Artifact Registry Cleanup:** Artifact Registry automatically deletes older container images beyond the 15 most recent versions per service to prevent unbounded image storage growth.  
    — *Provisioned in [`deployment/terraform/registry.tf`](deployment/terraform/registry.tf)*
  - **Docker Layer Caching, Multi-Stage Builds & Nginx Gzip Compression:** Cloud Build pipelines pull the previous `latest` image to reuse cached Docker layers, the frontend Dockerfile uses a multi-stage build that discards Node build tools from the final Nginx image, and Nginx compresses JavaScript, CSS, and JSON payloads with Gzip.  
    — *Implemented in [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`frontend/Dockerfile`](frontend/Dockerfile), [`frontend/nginx.conf.template`](frontend/nginx.conf.template), [`flights_search_app/Dockerfile`](flights_search_app/Dockerfile) & [`conversational_app/Dockerfile`](conversational_app/Dockerfile)*

> **Note on Unimplemented / Non-Relevant Pillars:**
> - **GPU Right-Sizing & Spot / Preemptible VM Usage (*Not Implemented — Not Relevant*):** GPU right-sizing and Spot/Preemptible virtual machines are not relevant to this architecture because the platform uses zero self-managed VMs or GPU nodes—all deep-learning inference runs on pay-per-token managed **Google Cloud Vertex AI** APIs and all application containers run on serverless **Google Cloud Run**.

---

## V/ [SECURITY, PRIVACY, AND COMPLIANCE]

### 1. Authentication & Authorization

Cloud infrastructure and runtime services follow a least-privilege model across three dedicated service accounts per project, declarative IAM role bindings, non-root containers, and keyless Vertex AI authentication:

| Service Account | Provisioned By | Attached To | Granted IAM Roles |
| :--- | :--- | :--- | :--- |
| `travel-agent-cicd` | [`deployment/bootstrap.sh`](deployment/bootstrap.sh) | Cloud Build pipelines & GitHub triggers | `roles/run.admin`, `roles/artifactregistry.admin`, `roles/iam.serviceAccountAdmin`, `roles/iam.serviceAccountUser`, `roles/resourcemanager.projectIamAdmin`, `roles/serviceusage.serviceUsageAdmin`, `roles/cloudbuild.builds.editor`, `roles/storage.admin`, `roles/logging.logWriter` |
| `travel-agent-runtime` | [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) | `flights-search-app`, `conversational-app` | `roles/aiplatform.user` (Vertex AI Gemini), `roles/logging.logWriter`, `roles/cloudtrace.agent` |
| `travel-agent-frontend` | [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) | `frontend` (Nginx web container) | `roles/logging.logWriter` **only** (zero Vertex AI, storage, or admin access) |

- **1.1 Pillar 1 — Dedicated Service Accounts (3-Way Identity Separation per Project)**
  - **Backend Agent Runtime Service Account (`travel-agent-runtime`):** Attached exclusively to the Flight Search and Conversational Cloud Run services instead of Google Cloud's overly broad default compute account.  
    — *Provisioned in [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) & [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*
  - **Frontend Runtime Service Account (`travel-agent-frontend`):** Attached exclusively to the Frontend web container so the public web tier never shares credentials with the backend AI services.  
    — *Provisioned in [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) & [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*
  - **CI/CD Cloud Build Service Account (`travel-agent-cicd`):** Used exclusively for automated Cloud Build pipelines and GitHub triggers so deployments run under an audited machine identity.  
    — *Provisioned in [`deployment/bootstrap.sh`](deployment/bootstrap.sh), [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf) & [`deployment/terraform/triggers.tf`](deployment/terraform/triggers.tf)*  
    — *Called in [`deployment/deploy.sh`](deployment/deploy.sh)*

- **1.2 Pillar 2 — Identity & Access Management (IAM)**
  - **Declarative Role Bindings & Scoped Impersonation Permissions:** All runtime permissions and service-account attachment bindings (allowing the CI/CD service account to attach the runtime service accounts to Cloud Run) are defined explicitly in version-controlled Terraform code.  
    — *Provisioned in [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf)*
  - **Uniform Bucket-Level Access on State Storage:** The Terraform state bucket disables legacy per-object ACLs and enforces uniform bucket-level IAM access.  
    — *Provisioned in [`deployment/bootstrap.sh`](deployment/bootstrap.sh)*

- **1.3 Pillar 3 — Principle of Least Privilege**
  - **Minimal Frontend Service Account (`roles/logging.logWriter` Only):** Because the browser calls the backend services directly over HTTPS, the Frontend container makes zero backend or AI calls and is granted only log-writing permissions—with zero access to Vertex AI, Cloud Storage, or IAM.  
    — *Provisioned in [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf)*
  - **Scoped Backend Service Account:** The Backend service account is restricted strictly to invoking Vertex AI models and writing logs and traces, with zero access to the Terraform state bucket, Artifact Registry, or project administration.  
    — *Provisioned in [`deployment/terraform/iam.tf`](deployment/terraform/iam.tf)*
  - **Active Removal of Extra Permissions from Default Google Service Accounts:** During project bootstrap, [`deployment/bootstrap.sh`](deployment/bootstrap.sh) inspects the project IAM policy and actively strips all CI/CD administrative roles from Google's built-in Cloud Build and Compute Engine default service accounts.  
    — *Implemented in [`deployment/bootstrap.sh`](deployment/bootstrap.sh)*
  - **Non-Root Container Execution:** Inside both backend Docker images, root privileges are dropped before startup so the web server runs as an unprivileged operating-system user (`appuser`).  
    — *Implemented in [`flights_search_app/Dockerfile`](flights_search_app/Dockerfile) & [`conversational_app/Dockerfile`](conversational_app/Dockerfile)*

- **1.4 Pillar 4 — Keyless Workload Identity & API Origin Scoping**
  - **Keyless Backend Service-to-Service Authentication:** Backend containers never use static Gemini API keys or downloadable JSON key files to call Vertex AI; instead, they authenticate automatically using short-lived credentials attached to their Cloud Run service account, while local `.env` and `.tfvars` files are excluded from Git and Docker builds.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*  
    — *Implemented in [`.gitignore`](.gitignore), [`.gcloudignore`](.gcloudignore), [`flights_search_app/.dockerignore`](flights_search_app/.dockerignore) & [`conversational_app/.dockerignore`](conversational_app/.dockerignore)*
  - **Configurable Cross-Origin Request Scoping (CORS):** Backend services enforce configurable CORS origin lists injected via environment variables and Terraform settings.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf) & [`deployment/terraform/variables.tf`](deployment/terraform/variables.tf)*  
    — *Implemented in [`flights_search_app/app/config.py`](flights_search_app/app/config.py), [`flights_search_app/app/main.py`](flights_search_app/app/main.py), [`conversational_app/app/config.py`](conversational_app/app/config.py) & [`conversational_app/app/main.py`](conversational_app/app/main.py)*

> **Note on Unimplemented Pillars:**
> - **End-User OAuth 2.0 / OIDC Sign-In & Authenticated Cloud Run Invoker IAM (*Not Implemented — Relevant*):** Because the platform is deployed as an open interactive flight search application (`allow_public_access = true`), end-user OAuth 2.0 / OIDC login (such as Google Identity Platform / Firebase Authentication) and IAM-restricted backend invocation are not yet enabled and remain relevant future security enhancements for user accounts and saved trips.

---

## VI/ [RELIABILITY & RESILIENCE]

### 2. Graceful Degradation

The platform is engineered to handle transient Vertex AI errors, malformed model responses after live Google Search calls, and partial service outages without breaking the user experience:

- **2.1 Pillar 1 — Fallback Strategies**
  - **Self-Healing JSON Repair Fallback:** When the Smart Filter specialist returns markdown-wrapped or malformed JSON after running a live Google Search, the workflow catches the parsing error and automatically routes the raw text to the JSON Parser specialist, which repairs the output into valid schema-compliant JSON so the user's request succeeds.  
    — *Implemented in [`conversational_app/app/agent.py`](conversational_app/app/agent.py), [`conversational_app/app/sub_agents/json_parser/agent.py`](conversational_app/app/sub_agents/json_parser/agent.py) & [`conversational_app/app/sub_agents/json_parser/prompt.py`](conversational_app/app/sub_agents/json_parser/prompt.py)*
  - **Non-JSON Runner Output Fallback:** If an agent runner ever returns unexpected plain text instead of JSON, the backend catches the error, logs a warning, and wraps the raw text safely rather than crashing with an unhandled exception.  
    — *Implemented in [`flights_search_app/app/main.py`](flights_search_app/app/main.py), [`conversational_app/app/main.py`](conversational_app/app/main.py) & [`conversational_app/app/sub_agents/`](conversational_app/app/sub_agents/)*
  - **Independent UI Feature Isolation (Flight Search vs. Chat Assistant):** Because Flight Search and the Conversational Assistant are separate microservices—and the React chat widget catches network or server errors locally inside the chat panel—an outage in the conversational service never interrupts core flight search, manual filtering, or pagination on the main page.  
    — *Implemented in [`frontend/src/ChatWidget.jsx`](frontend/src/ChatWidget.jsx) & [`frontend/src/App.jsx`](frontend/src/App.jsx)*
  - **Three-Tier Frontend Endpoint Fallback:** The web frontend resolves backend URLs across three fallback levels: (1) runtime Cloud Run configuration (`/env-config.js`), (2) local `.env` build variables, and (3) default localhost ports (`8000` and `8001`).  
    — *Implemented in [`frontend/src/App.jsx`](frontend/src/App.jsx) & [`frontend/src/ChatWidget.jsx`](frontend/src/ChatWidget.jsx)*

- **2.2 Pillar 2 — Retry Policies**
  - **Exponential Backoff Retries Across All Six AI Agents:** Every agent configures automatic HTTP retries (up to 5 attempts with exponential backoff from 5 seconds to 60 seconds) on transient Vertex AI rate limits (`429`), request timeouts (`408`), and upstream server errors (`500`, `502`, `503`, `504`).  
    — *Implemented in [`flights_search_app/app/agent.py`](flights_search_app/app/agent.py), [`conversational_app/app/sub_agents/engage/agent.py`](conversational_app/app/sub_agents/engage/agent.py), [`conversational_app/app/sub_agents/filter/agent.py`](conversational_app/app/sub_agents/filter/agent.py), [`conversational_app/app/sub_agents/filter_smart/agent.py`](conversational_app/app/sub_agents/filter_smart/agent.py), [`conversational_app/app/sub_agents/inspiration/agent.py`](conversational_app/app/sub_agents/inspiration/agent.py) & [`conversational_app/app/sub_agents/json_parser/agent.py`](conversational_app/app/sub_agents/json_parser/agent.py)*
  - **CI/CD IAM Binding & Post-Deploy Smoke Test Retries:** Project bootstrap scripts retry IAM policy bindings with propagation wait delays, and Stage 5 of every deployment pipeline retries live service health checks (`--retry 5 --retry-delay 3`) to absorb container startup transients.  
    — *Implemented in [`deployment/bootstrap.sh`](deployment/bootstrap.sh), [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`.cloudbuild/staging.yaml`](.cloudbuild/staging.yaml) & [`.cloudbuild/prod.yaml`](.cloudbuild/prod.yaml)*

- **2.3 Pillar 3 — Timeout Handling**
  - **Workload-Tailored Cloud Run Request Timeouts (300 Seconds):** Terraform configures a 300-second request timeout on both backend Cloud Run services so multi-step conversational turns involving Google Search grounding, exponential backoff retries, and JSON repair are never cut off prematurely.  
    — *Provisioned in [`deployment/terraform/cloud_run.tf`](deployment/terraform/cloud_run.tf)*
  - **Bounded E2E Client Timeouts, Terraform Lock Timeouts & Build Deadlines:** End-to-end HTTP tests enforce a 90-second request timeout, Terraform commands enforce a 5-minute state-lock timeout, and Cloud Build pipelines enforce a 30-minute overall build timeout.  
    — *Implemented in [`.cloudbuild/dev.yaml`](.cloudbuild/dev.yaml), [`flights_search_app/tests/e2e/test_flights_search.py`](flights_search_app/tests/e2e/test_flights_search.py) & [`conversational_app/tests/e2e/test_conversational.py`](conversational_app/tests/e2e/test_conversational.py)*

> **Note on Unimplemented Pillars:**
> - **Stateful Upstream Circuit Breakers & Automatic Cross-Model Failover (*Not Implemented — Relevant*):** While the platform enforces 5-attempt exponential backoff retries, self-healing JSON repair via `json_parser`, 300-second Cloud Run request timeouts, and UI feature isolation between Flight Search and Chat, a stateful circuit-breaker state machine (tracking consecutive upstream failure rates across requests to fail fast) and automatic cross-model failover (such as automatically retrying a timed-out primary model call on a backup Gemini model) are not yet implemented and remain relevant future resilience enhancements.

---

## 📁 Repository Structure

```text
travel_agent/
├── .cloudbuild/                        # Google Cloud Build CI/CD Pipelines
│   ├── pr_checks.yaml                  # Pull Request CI (unit tests, frontend build, terraform fmt/validate)
│   ├── dev.yaml                        # 5-stage CD pipeline for Dev (travel-agent-511710)
│   ├── staging.yaml                    # 5-stage CD pipeline for Staging (travel-agent-staging-512211)
│   └── prod.yaml                       # 5-stage CD pipeline for Prod (travel-agent-prod-512211)
├── deployment/                         # Infrastructure as Code (Terraform) & Deployment Runners
│   ├── bootstrap.sh                    # Provisions versioned GCS state bucket, travel-agent-cicd SA & cleans default SAs
│   ├── deploy.sh                       # Unified runner for PR checks and dev/staging/prod Cloud Build deployments
│   └── terraform/                      # Single declarative Terraform stack across dev, staging & prod
│       ├── apis.tf                     # Required GCP service APIs (Cloud Run, Vertex AI, Artifact Registry, IAM, etc.)
│       ├── iam.tf                      # 3-SA separation (agent_runtime, frontend_runtime, cicd_runner)
│       ├── registry.tf                 # Artifact Registry Docker repository + 15-version cleanup policy
│       ├── cloud_run.tf                # Cloud Run v2 services, scaling, model & runtime URL env injection
│       ├── triggers.tf                 # Automated Cloud Build GitHub triggers (PR, main -> staging, v* -> prod)
│       ├── variables.tf                # Parameterized infrastructure, model, scaling, CPU/memory & CORS inputs
│       ├── outputs.tf                  # Deployed Cloud Run service URLs & Service Account emails
│       ├── versions.tf                 # Terraform & provider constraints + remote GCS state backend
│       └── envs/                       # Environment-specific variable files (dev.tfvars, staging.tfvars, prod.tfvars)
├── flights_search_app/                 # Standalone Flights Search ADK Service (Local :8000 / Cloud Run :8080)
│   ├── app/
│   │   ├── agent.py                    # flights_search ADK Agent & App container (with telemetry plugin)
│   │   ├── config.py                   # Externalized model, location, host/port, base URL, CORS & plugin config
│   │   ├── main.py                     # FastAPI server, CORSMiddleware & per-request ADK Runner
│   │   ├── prompt.py                   # Flight simulation system instructions & realism rules
│   │   ├── schema.py                   # Validated request & response schemas
│   │   └── app_utils/
│   │       ├── logging.py              # Structured logging & table formatting helpers
│   │       └── telemetry_plugin.py     # ADK ExecutionTelemetryPlugin (latency & token telemetry)
│   ├── tests/
│   │   ├── fixtures/                   # Sample search payloads (flights_search.json)
│   │   ├── unit/                       # Offline health check, schema / 422 & telemetry plugin tests
│   │   ├── integration/                # In-process TestClient tests with live Vertex AI Gemini inference
│   │   └── e2e/                        # Live HTTP client tests (configurable via FLIGHTS_SEARCH_BASE_URL)
│   ├── Dockerfile                      # Hardened non-root (appuser) Python 3.11 container image
│   ├── .env.example                    # Template environment & model variables
│   ├── requirements.txt                # Pinned Python runtime dependencies
│   └── README.md                       # Flights Search service documentation
├── conversational_app/                 # Conversational Multi-Agent Workflow Service (Local :8001–8006 / Cloud Run :8080)
│   ├── app/
│   │   ├── agent.py                    # Root ADK v2 Workflow graph, routing steps & App container
│   │   ├── config.py                   # Externalized global & per-sub-agent models, ports, base URLs, CORS & plugin config
│   │   ├── main.py                     # FastAPI gateway (POST /run-conversational) & ADK Runner execution
│   │   ├── schema.py                   # Validated workflow input, output & shared state schemas
│   │   ├── app_utils/
│   │   │   ├── logging.py              # Structured logging & table formatting helpers
│   │   │   └── telemetry_plugin.py     # ADK ExecutionTelemetryPlugin (latency, token & search grounding telemetry)
│   │   └── sub_agents/                 # 5 Self-Contained Specialist Sub-Agents (each with agent.py, main.py, prompt.py, schema.py)
│   │       ├── engage/                 # Intent triage specialist (:8002)
│   │       ├── filter/                 # Deterministic hard filter extractor (:8003)
│   │       ├── filter_smart/           # Semantic & amenity filter with Google Search grounding (:8004)
│   │       ├── inspiration/            # Open-ended destination & date discovery specialist (:8005)
│   │       └── json_parser/            # Self-healing JSON structure repair specialist (:8006)
│   ├── tests/
│   │   ├── fixtures/                   # Sample JSON test payloads for orchestrator & all 5 sub-agents
│   │   ├── unit/                       # Offline health & schema / 422 validation tests (6 test modules)
│   │   ├── integration/                # In-process TestClient tests with live Gemini calls (6 test modules)
│   │   ├── e2e/                        # Live HTTP client tests against :8001–:8006 or Cloud Run (6 test modules)
│   │   └── eval/                       # 7-Metric GEAP AI Quality, Non-Hallucination & Latency Evaluation Suite
│   │       ├── configs/                # eval_config.json, scenario_generation_config.json, session_input.json
│   │       ├── datasets/               # 50-case synthetic travel benchmark (conversational_synthetic.evalset.json)
│   │       ├── metrics/                # Custom deterministic Python & LLM-as-a-Judge metrics (custom_metrics.py)
│   │       ├── results/                # Timestamped evaluation runs, traces, loss clusters & experiments_history.md
│   │       └── scripts/                # generate_scenarios.py, run_evaluation.py, run_loss_analysis.py
│   ├── Dockerfile                      # Hardened non-root (appuser) Python 3.11 container image
│   ├── .env.example                    # Template environment, per-agent model & endpoint configuration
│   ├── requirements.txt                # Pinned Python runtime dependencies
│   └── README.md                       # Conversational Workflow, Sub-Agents & GEAP Evaluation documentation
└── frontend/                           # React + Vite SPA & Nginx Cloud Run Container (Local :5173 / Cloud Run :8080)
    ├── src/
    │   ├── App.jsx                     # Flight search form, manual filter controls & paginated itinerary cards
    │   ├── ChatWidget.jsx              # Conversational AI widget & dynamic UI state synchronization
    │   ├── index.css                   # Application & ChatWidget styling
    │   └── main.jsx                    # React root entrypoint
    ├── index.html                      # Loads runtime /env-config.js before mounting React bundle
    ├── Dockerfile                      # Multi-stage Node 20 build + Nginx 1.27 runtime /env-config.js generator
    ├── nginx.conf.template             # Cloud Run Nginx config (Gzip, SPA fallback & no-store /env-config.js)
    ├── .env.example                    # Template local backend API URLs
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

# Global & Per-Sub-Agent Gemini Model Configuration
GEMINI_MODEL=gemini-3.5-flash-lite
CONVERSATIONAL_MODEL=gemini-3.5-flash-lite
GEMINI_MODEL_LOCATION=global
# Optional per-sub-agent model overrides (fall back to CONVERSATIONAL_MODEL):
# ENGAGE_MODEL=gemini-3.5-flash-lite
# FILTER_MODEL=gemini-3.5-flash-lite
# FILTER_SMART_MODEL=gemini-3.5-flash-lite
# INSPIRATION_MODEL=gemini-3.5-flash-lite
# JSON_PARSER_MODEL=gemini-3.5-flash-lite

# Server, CORS & E2E Target Endpoints
HOST=0.0.0.0
PORT=8001
ALLOWED_ORIGINS=*
CONVERSATIONAL_BASE_URL=http://127.0.0.1:8001
```

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
python3 -m app.sub_agents.engage.main        # Port 8002 (POST /run-engage)
python3 -m app.sub_agents.filter.main        # Port 8003 (POST /run-filter)
python3 -m app.sub_agents.filter_smart.main  # Port 8004 (POST /run-filter-smart)
python3 -m app.sub_agents.inspiration.main   # Port 8005 (POST /run-inspiration)
python3 -m app.sub_agents.json_parser.main   # Port 8006 (POST /run-json-parser)
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
   ./deployment/deploy.sh prod         # Deploys to travel-agent-prod-512211 (envs/prod.tfvars)
   ```

4. **Roll Back to a Previous Immutable Git Commit SHA (Optional)**
   ```bash
   IMAGE_TAG="<previous-git-sha>" ./deployment/deploy.sh prod
   ```

---

## 🧪 Testing, AI Evaluation & Verification

### 1. Offline Unit Test Suites
Run the fast offline unit and schema validation suites across both backend applications (no live servers or Vertex AI calls required):
```bash
(cd flights_search_app && python3 -m pytest tests/unit -v -s)
(cd conversational_app && python3 -m pytest tests/unit -v -s)
```

### 2. Live In-Process Integration & HTTP End-to-End (E2E) Suites
```bash
# 1. Run in-process FastAPI TestClient integration tests with live Vertex AI Gemini calls
(cd flights_search_app && python3 -m pytest tests/integration -v -s)
(cd conversational_app && python3 -m pytest tests/integration -v -s)

# 2. Run live HTTP E2E tests against local servers (:8000 and :8001)
(cd flights_search_app && python3 -m pytest tests/e2e -v -s)
(cd conversational_app && python3 -m pytest tests/e2e/test_conversational.py -v -s)

# 3. Run live HTTP E2E tests against deployed Cloud Run services
(cd flights_search_app && FLIGHTS_SEARCH_BASE_URL="https://<flights-cloud-run-url>" python3 -m pytest tests/e2e -v -s)
(cd conversational_app && CONVERSATIONAL_BASE_URL="https://<conversational-cloud-run-url>" python3 -m pytest tests/e2e/test_conversational.py -v -s)
```

### 3. GEAP 7-Metric AI Evaluation & Loss Analysis Flywheel
Run the 50-scenario synthetic evaluation benchmark and automated loss-clustering pipeline in [`conversational_app/tests/eval/`](conversational_app/tests/eval/):

| Metric | Type | Target Threshold | What It Verifies |
| :--- | :---: | :---: | :--- |
| `multi_turn_task_success_v1` | Predefined Rubric | `>= 0.80` | End-to-end user goal completion across the conversational turn. |
| `multi_turn_trajectory_quality_v1` | Predefined Rubric | `>= 0.80` | Sub-agent orchestration trajectory (`engage` → specialist → output normalization). |
| `tool_use_quality` | Custom LLM Judge | `>= 0.80` | Mandatory Google Search calls on qualitative amenities vs. zero calls on structured filters. |
| `coherence` | Custom LLM Judge | `>= 0.80` | Clarity of the natural-language response and consistency with returned JSON fields. |
| `schema_and_contract_valid` | Deterministic Python | `>= 0.95` | Strict output schema validity, decision invariants & **zero hallucinated flights**. |
| `conversation_plan_alignment` | Custom LLM Judge | `>= 0.80` | Alignment with expected ground-truth conversation plan. |
| `latency_seconds` | Deterministic Python | `<= 15.0s` | Single-turn end-to-end latency with per-sub-agent execution breakdown. |

```bash
cd conversational_app

# 1. Run full inference + 7-metric evaluation (records results in tests/eval/results/experiments_history.md)
python3 -m tests.eval.scripts.run_evaluation --run-name baseline

# 2. Benchmark an alternative Gemini model without changing application code
CONVERSATIONAL_MODEL="gemini-2.5-pro" \
  python3 -m tests.eval.scripts.run_evaluation \
  --run-name gemini_2_5_pro \
  --description "Benchmark Gemini 2.5 Pro across all conversational sub-agents"

# 3. Cluster failure root causes with automated LLM loss analysis
python3 -m tests.eval.scripts.run_loss_analysis
```

### 4. Manual API Testing via `curl`
With `flights_search_app` running on port `8000` and `conversational_app` running on port `8001` (or substituting your deployed Cloud Run URLs):

```bash
# 1. Generate 15 simulated flights from Paris to New York (flights_search_app on port 8000)
curl -X POST "http://127.0.0.1:8000/run-flights-search" \
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
curl -X POST "http://127.0.0.1:8001/run-conversational" \
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
