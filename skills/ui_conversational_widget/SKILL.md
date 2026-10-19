---
name: UI Development - Conversational Search & Orchestration Widget
description: |
  Instructions and guidelines to build a chat interface that communicates with the `orchestrator`.
  This widget allows users to apply natural language filters alongside search history.
---

# 💬 Skill: Developing the Conversational Orchestration Widget

This skill enables the agent to design and implement a smart, sticky **Chatbot Widget** that talks to the **Orchestrator Agent**. It allows travelers to refine search results using prompts like *"Only direct flights under $500"* instead of standard toggles.

---

## 🏗️ Architecture & Stack Choice

-   **Framework:** **Vite + React (JavaScript)** — Continuing the existing stack.
-   **State Management:** Extends the search state.
    -   The `Search Results` and `Chat Widget` share contextual state (e.g., Active Flights).
-   **API Integration:** Standard `fetch` API to `http://127.0.0.1:8004/run-conversational`.

---

## 📐 UI/UX Design Specifications

### 🌿 Aesthetic Guidelines
-   **Vibe:** Sleek glassmorphism overlay resting in the bottom-right corner.
-   **Animations:** Smooth slide-in/slide-out on toggle click.
-   **State Triggers:** Visual indicators for "Typing..." when agent processes.

### 🖥️ Widget Breakdown
1.  **Chat FAB (Floating Action Button):** Minimal circular icon.
2.  **Conversational Thread View:**
    -   Bubble chat (User vs Agent).
    -   Timestamps.
3.  **Refinement Text Box:** Prompt field with enter key bindings.

---

## 🛠️ Step-by-Step Implementation Workflow

### Step 1: Manage Shared State
The widget needs access to the active `flights` list (fetched by the primary search) to send it to the orchestrator.
```js
// Shared state context or lifted state
const [flights, setFlights] = useState([]);
const [conversationalHistory, setConversationalHistory] = useState([]);
```

### Step 2: Handle Orchestrator Webhook
Bind submit events to trigger the `/run-conversational` endpoint.

For the second round, third round, nth round etc of chat conversation, ensure the conversation is appended to the `conversation_history` variable (or `conversational_history` payload field) sent to the backend.

**Payload Format required:**
```json
{
  "user_message": "String",
  "conversational_history": ["String history"],
  "flights_input": [ { /* Current State of Flights */ } ]
}
```

### Step 3: Parse Hybrid Decisions (Deterministic vs Semantic)
Update state based on orchestrator output:

-   **Scenario 1: `agent_decision` == `"filter"` (Deterministic)**
    -   Read `filter_type` and `filter_value` to automatically apply the filters on the flights search simulator UI.
    -   Display `agent_response` to the user as chatbot AI answer.
-   **Scenario 2: `agent_decision` == `"filter_smart"` (Semantic)**
    -   Take into consideration the variable `flights_output` to have the new list of flights available and displayed to the user instead of the existing list.
    -   Display `agent_response` to the user as chatbot AI answer.
-   **Scenario 3: `agent_decision` == `"continue"` (Classic Chat)**
    -   Just append the `agent_response` to the chat bubbles feed!

---

## 🧪 Verification Checklists

### ✅ Manual Checklist
-   [ ] Typing "only direct flights" extracts the filter, and standard UI updates.
-   [ ] Typing "flights with great Wi-Fi" replaces the cards with smart-filtered lists.
-   [ ] Typing "hello" doesn't corrupt state, just replies.
-   [ ] Conversational history grows correctly without infinite loops.
