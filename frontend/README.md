# 🌐 Travel Agent Web Frontend (`frontend`)

The **Web Frontend** is a single-page React + Vite application (`:5173` locally, Nginx `:8080` on Google Cloud Run) providing interactive flight search, manual parameter filtering, paginated results, and an embedded conversational **ChatWidget**.

---

## 🌟 Key Components & Features

- **Flight Search & Exploration ([`src/App.jsx`](src/App.jsx))**:
  - Autocomplete city selector, departure/return dates, passenger count, and manual filter controls (`direct`, `max_price`, `max_stops`).
  - Client-side pagination (5 itineraries per page) and responsive itinerary cards displaying carrier, flight number, airport codes, overnight `+1`/`+2` offsets, stopovers, and pricing.
- **Conversational AI Assistant ([`src/ChatWidget.jsx`](src/ChatWidget.jsx))**:
  - Floating chat widget connected to `POST /api/v1/run-conversational`.
  - Dynamically updates UI state based on `agent_decision`:
    - `filter`: Updates top-level filter controls and filters displayed flights instantaneously.
    - `filter_smart`: Updates displayed flights with semantically filtered / Google Search-verified itineraries.
    - `inspiration_agent`: Updates search parameters (`origin`, `destination`, dates) and automatically triggers a fresh flight search.
    - `continue`: Displays conversational guidance or clarifying questions.
  - **Independent Feature Isolation**: Network or backend errors from `conversational-app` are caught and shown gracefully inside the chat widget without interrupting flight search or manual filtering in `App.jsx`.
- **Versioned API Client, Cross-Region Backend Failover & Price Helper ([`src/apiClient.js`](src/apiClient.js))**:
  - Centralizes the canonical `/api/v1` API prefix (`API_V1_PREFIX`), runtime URL resolution (`resolveBackendUrl`), multi-currency price parsing (`parseFlightPrice` across `EUR`, `USD`, `$`, `€`, `£` for local filter sync), and wraps backend `POST /api/v1/run-*` calls from [`src/App.jsx`](src/App.jsx) and [`src/ChatWidget.jsx`](src/ChatWidget.jsx) with `postWithRegionalFailover()`.
  - When a secondary regional backend URL is configured (`VITE_FLIGHTS_SEARCH_FALLBACK_API_URL` / `VITE_CONVERSATIONAL_FALLBACK_API_URL`, pointing to `europe-west1` in `prod`), network errors (`TypeError` / connection drop) or transient upstream gateway failures (`HTTP 502`, `503`, `504`) on the primary `europe-west9` backend automatically fail over to the warm `europe-west1` backend transparently—while never double-sending client validation errors (`HTTP 4xx`).

---

## ⚙️ 12-Factor Runtime Configuration & Multi-Region Routing

Backend URLs are never hardcoded into compiled JavaScript bundles. [`src/apiClient.js`](src/apiClient.js) resolves primary and optional regional fallback endpoints in priority order:

1. **`window.__ENV__` (`/env-config.js`)** — Generated dynamically at container startup on Cloud Run by [`Dockerfile`](Dockerfile) (`40-generate-env-config.sh`) from Cloud Run environment variables injected by Terraform (`VITE_FLIGHTS_SEARCH_API_URL`, `VITE_CONVERSATIONAL_API_URL`, `VITE_FLIGHTS_SEARCH_FALLBACK_API_URL`, `VITE_CONVERSATIONAL_FALLBACK_API_URL`). [`nginx.conf.template`](nginx.conf.template) serves `/env-config.js` with `Cache-Control: no-store, no-cache, must-revalidate` and exposes `GET /healthz` (Nginx liveness) and `GET /readyz` (verifies `/usr/share/nginx/html/env-config.js` exists before Cloud Run admits traffic).
2. **`import.meta.env.VITE_*` (`.env` — see [`.env.example`](.env.example))** — Used during local Vite development (`npm run dev`).
3. **Localhost Fallback** — Primary URLs default to `http://127.0.0.1:8000` (Flights Search) and `http://127.0.0.1:8001` (Conversational Workflow), while fallback URLs default to `""` (single-region mode).

### Primary `frontend_url` vs. Warm Standby `frontend_secondary_url` in Production
In `prod` (without a paid custom DNS domain or external Global Application Load Balancer):
- **`frontend` (`europe-west9` — Terraform output `frontend_url`)** is the primary entry URL shared with end users (`min_instances = 2`). If a backend service in `europe-west9` degrades, `postWithRegionalFailover()` automatically fails over API calls to `europe-west1` in the background.
- **`frontend-secondary` (`europe-west1` — Terraform output `frontend_secondary_url`)** runs as a warm standby (`secondary_min_instances = 1`) pre-wired to call `europe-west1` backends first (with `europe-west9` as its fallback), providing an immediate zero-rebuild recovery URL if the `europe-west9` frontend Cloud Run endpoint itself becomes unreachable.

### Security Footprint on Cloud Run
Because the user's browser invokes the public CORS-protected backend URLs directly over HTTPS, the `frontend` Nginx container makes zero server-to-server or Vertex AI calls—and runs under its own dedicated `travel-agent-frontend` Service Account with **`roles/logging.logWriter` only**.

---

## 📁 Directory Structure

```text
frontend/
├── src/
│   ├── App.jsx              # Flight search form, manual filters & paginated itinerary cards
│   ├── ChatWidget.jsx       # Conversational AI assistant & dynamic UI state sync
│   ├── apiClient.js         # Runtime URL resolution, cross-region POST failover & price helper
│   ├── apiClient.test.js    # Unit & fault-injection tests for URL resolution, regional failover & price parsing
│   ├── index.css            # Application & ChatWidget styling
│   └── main.jsx             # React root entrypoint
├── index.html               # Loads /env-config.js before mounting React bundle
├── Dockerfile               # Multi-stage Node test/build + Nginx runtime /env-config.js generator
├── nginx.conf.template      # Cloud Run Nginx config ($PORT, /healthz, /readyz, SPA fallback & no-store env-config)
├── .env.example             # Template local primary & optional fallback backend API URLs
├── package.json             # Dependencies, test & Vite scripts
└── vite.config.js           # Vite dev/build configuration
```

---

## 🚀 Running & Testing Locally

```bash
cd frontend
cp -n .env.example .env
npm install

# Run offline failover & price-parsing unit tests
npm test

# Start Vite dev server on http://localhost:5173
npm run dev

# Verify production bundle compilation
npm run build
```
