# 🌐 Travel Agent Web Frontend (`frontend`)

The **Web Frontend** is a single-page React + Vite application (`:5173` locally, Nginx `:8080` on Google Cloud Run) providing interactive flight search, manual parameter filtering, paginated results, and an embedded conversational **ChatWidget**.

---

## 🌟 Key Components & Features

- **Flight Search & Exploration ([`src/App.jsx`](src/App.jsx))**:
  - Autocomplete city selector, departure/return dates, passenger count, and manual filter controls (`direct`, `max_price`, `max_stops`).
  - Client-side pagination (5 itineraries per page) and responsive itinerary cards displaying carrier, flight number, airport codes, overnight `+1`/`+2` offsets, stopovers, and pricing.
- **Conversational AI Assistant ([`src/ChatWidget.jsx`](src/ChatWidget.jsx))**:
  - Floating chat widget connected to `POST /run-conversational`.
  - Dynamically updates UI state based on `agent_decision`:
    - `filter`: Updates top-level filter controls and filters displayed flights instantaneously.
    - `filter_smart`: Updates displayed flights with semantically filtered / Google Search-verified itineraries.
    - `inspiration_agent`: Updates search parameters (`origin`, `destination`, dates) and automatically triggers a fresh flight search.
    - `continue`: Displays conversational guidance or clarifying questions.
  - **Independent Feature Isolation**: Network or backend errors from `conversational-app` are caught and shown gracefully inside the chat widget without interrupting flight search or manual filtering in `App.jsx`.

---

## ⚙️ 12-Factor Runtime Configuration ("Build Once, Deploy Anywhere")

Backend URLs are never hardcoded into compiled JavaScript bundles. Both [`src/App.jsx`](src/App.jsx) and [`src/ChatWidget.jsx`](src/ChatWidget.jsx) resolve endpoints in priority order:

1. **`window.__ENV__` (`/env-config.js`)** — Generated dynamically at container startup on Cloud Run by [`Dockerfile`](Dockerfile) (`40-generate-env-config.sh`) from Cloud Run environment variables injected by Terraform (`VITE_FLIGHTS_SEARCH_API_URL`, `VITE_CONVERSATIONAL_API_URL`). [`nginx.conf.template`](nginx.conf.template) serves `/env-config.js` with `Cache-Control: no-store, no-cache, must-revalidate`.
2. **`import.meta.env.VITE_*` (`.env` — see [`.env.example`](.env.example))** — Used during local Vite development (`npm run dev`).
3. **Localhost Fallback** — Defaults to `http://127.0.0.1:8000` (Flights Search) and `http://127.0.0.1:8001` (Conversational Workflow).

### Security Footprint on Cloud Run
Because the user's browser invokes the public CORS-protected backend URLs directly over HTTPS, the `frontend` Nginx container makes zero server-to-server or Vertex AI calls—and runs under its own dedicated `travel-agent-frontend` Service Account with **`roles/logging.logWriter` only**.

---

## 📁 Directory Structure

```text
frontend/
├── src/
│   ├── App.jsx              # Flight search form, manual filters & paginated itinerary cards
│   ├── ChatWidget.jsx       # Conversational AI assistant & dynamic UI state sync
│   ├── index.css            # Application & ChatWidget styling
│   └── main.jsx             # React root entrypoint
├── index.html               # Loads /env-config.js before mounting React bundle
├── Dockerfile               # Multi-stage Node build + Nginx runtime /env-config.js generator
├── nginx.conf.template      # Cloud Run Nginx config ($PORT, SPA fallback & no-store env-config)
├── .env.example             # Template local backend API URLs
├── package.json             # Dependencies & Vite scripts
└── vite.config.js           # Vite dev/build configuration
```

---

## 🚀 Running Locally

```bash
cd frontend
cp -n .env.example .env
npm install

# Start Vite dev server on http://localhost:5173
npm run dev

# Verify production bundle compilation
npm run build
```
