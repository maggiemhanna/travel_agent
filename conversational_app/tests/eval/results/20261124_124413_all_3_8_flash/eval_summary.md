# GEAP EVALUATION SUMMARY — 20261124_124413_all_3_8_flash (50 EvalCases)

## Run Metadata

- **Run ID**: `20261124_124413_all_3_8_flash`
- **Run Name**: `all_3_8_flash`
- **Description**: All sub-agents on gemini-3.8-flash (thinking budget 0 on engage/filter/inspiration/json_parser, 512 on filter_smart)
- **Baseline Reference**: `Pinned as active baseline`
- **Eval Set ID**: `conversational_synthetic`
- **Timestamp (UTC)**: `2026-11-24T12:44:13.826421+00:00`
- **Cases Evaluated**: `50`
- **Git Revision**: `acd97d6` (branch: `main`, dirty: `True`)

## Aggregated Metric Scores

| Metric Name                      | Mean Score    | Pass Rate   | Std Dev       | Threshold       | Valid/Total   | Status   |
|----------------------------------|---------------|-------------|---------------|-----------------|---------------|----------|
| multi_turn_task_success_v1       | 0.923         | 78.0%       | 0.150         | >= 0.80         | 50/50         | PASS     |
| multi_turn_trajectory_quality_v1 | 0.954         | 80.0%       | 0.099         | >= 0.80         | 50/50         | PASS     |
| tool_use_quality                 | 1.000         | 100.0%      | 0.000         | >= 0.80         | 49/50         | PASS     |
| coherence                        | 0.980         | 98.0%       | 0.141         | >= 0.80         | 50/50         | PASS     |
| schema_and_contract_valid        | 1.000         | 100.0%      | 0.000         | >= 0.95         | 50/50         | PASS     |
| conversation_plan_alignment      | 0.980         | 98.0%       | 0.141         | >= 0.80         | 50/50         | PASS     |
| latency_seconds                  | 7.908s        | 84.0%       | 6.120s        | <= 15.00s       | 50/50         | PASS     |
| cost_per_1k_requests_usd         | 12.095 USD/1k | 80.0%       | 21.618 USD/1k | <= 15.00 USD/1k | 50/50         | PASS     |
| llm_token_cost_per_1k_usd        | 5.655 USD/1k  | 60.0%       | 4.627 USD/1k  | <= 5.00 USD/1k  | 50/50         | FAIL     |
| total_billable_tokens            | 4266.520 tok  | 60.0%       | 2475.670 tok  | <= 6000.00 tok  | 50/50         | PASS     |

## AI Cost & Token Breakdown (`2026-11-vertex-paygo-v1` — Standard PayGo)

| Cost / Efficiency Dimension                              | Current Run                               | Notes                                                            |
|----------------------------------------------------------|-------------------------------------------|------------------------------------------------------------------|
| Total SUT Cost / 1,000 Requests                          | $12.0945                                  | LLM tokens + Gemini 3 Google Search grounding ($14/1k queries)   |
| LLM Token-Only Cost / 1,000 Requests                     | $5.6546 (46.8%)                           | Uncached input + cached input + visible output + thinking tokens |
| Google Search Grounding Cost / 1,000 Requests            | $6.4400 (53.2%)                           | Grounded turns: 18.0% (avg 0.46 queries/req)                     |
| Quality-Adjusted Cost / 1,000 Successful Tasks           | $13.0988                                  | Total Cost/1k divided by multi_turn_task_success_v1 mean score   |
| Per-Request Cost Distribution (Mean / P50 / P95 / Max)   | $0.01209 / $0.00276 / $0.04138 / $0.13370 | Modeled 50-case batch SUT total: $0.60473                        |
| Mean Tokens / Request (Prompt / Cached / Out / Thoughts) | 3448 / 0 / 630 / 188                      | Total avg: 4266 tok (thinking = 23.0% of billable output)        |
| Workflow Calls & Self-Healing JSON Repair Rate           | 1.80 calls/req                            | json_parser fallback rate: 0.0%                                  |

- **Evaluation Run Spend Separation**: SUT live inference spend = `$0.60473` | Estimated Phase 2B Judge overhead (`gemini-4-hydrogen`, ~250 judge evaluations) = `$1.89267` _(excluded from SUT production cost metrics)_.

### Per-Sub-Agent Cost & Token Attribution

| Sub-Agent      | Model(s)           | Calls (Case %)   |   Avg Prompt Tok |   Avg Out Tok |   Avg Thoughts Tok |   Search Queries | Amortized $/1k Reqs   | Share of Cost   |
|----------------|--------------------|------------------|------------------|---------------|--------------------|------------------|-----------------------|-----------------|
| `engage`       | `gemini-3.8-flash` | 50 (100.0%)      |             1422 |            32 |                 77 |                0 | $1.4742               | 12.2%           |
| `filter`       | `gemini-3.8-flash` | 10 (20.0%)       |             1014 |            39 |                 11 |                0 | $0.1895               | 1.6%            |
| `filter_smart` | `gemini-3.8-flash` | 20 (40.0%)       |             3932 |          1416 |                273 |               23 | $10.1534              | 84.0%           |
| `inspiration`  | `gemini-3.8-flash` | 10 (20.0%)       |             1256 |           119 |                  0 |                0 | $0.2775               | 2.3%            |

### Analytical Cache-Hit Sensitivity Projections (Cold-Run Baseline Extrapolation)

#### 1. Application / Semantic Response Caching (Short-Circuits LLM + Google Search Grounding)

| Response Cache Hit Rate   | Projected Cost / 1k Reqs   | Projected Savings / 1k Reqs   | Projected Mean AI Latency   |
|---------------------------|----------------------------|-------------------------------|-----------------------------|
| 0%                        | $12.0945                   | -$0.0000 (-0.0%)              | 7.908s                      |
| 10%                       | $10.8851                   | -$1.2095 (-10.0%)             | 7.118s                      |
| 20%                       | $9.6756                    | -$2.4189 (-20.0%)             | 6.327s                      |
| 30%                       | $8.4662                    | -$3.6284 (-30.0%)             | 5.536s                      |
| 50%                       | $6.0473                    | -$6.0473 (-50.0%)             | 3.954s                      |

#### 2. Gemini Context Caching (Discounts Cached Input Prefix Tokens Only; Output & Search Unchanged)

| Prefix Cache Hit Rate   | Theoretical Cost / 1k (All Prompts)   | Threshold-Gated Cost / 1k (>= Min Tok)   | Max Input Token Savings / 1k   |
|-------------------------|---------------------------------------|------------------------------------------|--------------------------------|
| 0%                      | $12.0945 (-0.0%)                      | $12.0945 (-0.0%)                         | -$0.0000                       |
| 50%                     | $10.9307 (-9.6%)                      | $12.0945 (-0.0%)                         | -$1.1638                       |
| 80%                     | $10.2325 (-15.4%)                     | $12.0945 (-0.0%)                         | -$1.8621                       |
| 95%                     | $9.8833 (-18.3%)                      | $12.0945 (-0.0%)                         | -$2.2112                       |

- **Context Cache Prefix Threshold Eligibility**: `engage`: avg `1422` prompt tok (max `1453`, min required `4096` -> `0%` calls eligible); `filter`: avg `1014` prompt tok (max `1035`, min required `4096` -> `0%` calls eligible); `filter_smart`: avg `3932` prompt tok (max `3953`, min required `4096` -> `0%` calls eligible); `inspiration`: avg `1256` prompt tok (max `1266`, min required `4096` -> `0%` calls eligible)

## Agent Configuration Snapshot

| Sub-Agent      | Model              | Prompt Hash (SHA-256)   | Tools         |
|----------------|--------------------|-------------------------|---------------|
| `engage`       | `gemini-3.8-flash` | `5308d715db76`          | none          |
| `filter`       | `gemini-3.8-flash` | `1817f7a21c23`          | none          |
| `filter_smart` | `gemini-3.8-flash` | `e5760e6d2697`          | google_search |
| `inspiration`  | `gemini-3.8-flash` | `6df18991944b`          | none          |
| `json_parser`  | `gemini-3.8-flash` | `e7fc8bdbc711`          | none          |
