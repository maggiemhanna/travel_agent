# GEAP EVALUATION SUMMARY — 20261124_122326_baseline_all_3_5_flash_lite (50 EvalCases)

## Run Metadata

- **Run ID**: `20261124_122326_baseline_all_3_5_flash_lite`
- **Run Name**: `baseline_all_3_5_flash_lite`
- **Description**: Baseline: all sub-agents on gemini-3.5-flash-lite (thinking budget 0 on engage/filter/inspiration/json_parser, 512 on filter_smart)
- **Baseline Reference**: `Pinned as active baseline`
- **Eval Set ID**: `conversational_synthetic`
- **Timestamp (UTC)**: `2026-11-24T12:23:26.804108+00:00`
- **Cases Evaluated**: `50`
- **Git Revision**: `eee59b7` (branch: `eval/clean-model-benchmark`, dirty: `True`)

## Aggregated Metric Scores

| Metric Name                      | Mean Score   | Pass Rate   | Std Dev       | Threshold       | Valid/Total   | Status   |
|----------------------------------|--------------|-------------|---------------|-----------------|---------------|----------|
| multi_turn_task_success_v1       | 0.872        | 76.0%       | 0.260         | >= 0.80         | 50/50         | PASS     |
| multi_turn_trajectory_quality_v1 | 0.966        | 88.0%       | 0.097         | >= 0.80         | 50/50         | PASS     |
| tool_use_quality                 | 1.000        | 100.0%      | 0.000         | >= 0.80         | 48/50         | PASS     |
| coherence                        | 0.920        | 92.0%       | 0.274         | >= 0.80         | 50/50         | PASS     |
| schema_and_contract_valid        | 1.000        | 100.0%      | 0.000         | >= 0.95         | 50/50         | PASS     |
| conversation_plan_alignment      | 0.840        | 84.0%       | 0.370         | >= 0.80         | 50/50         | PASS     |
| latency_seconds                  | 3.201s       | 100.0%      | 2.266s        | <= 15.00s       | 50/50         | PASS     |
| cost_per_1k_requests_usd         | 6.303 USD/1k | 84.0%       | 11.702 USD/1k | <= 15.00 USD/1k | 50/50         | PASS     |
| llm_token_cost_per_1k_usd        | 2.383 USD/1k | 82.0%       | 2.267 USD/1k  | <= 5.00 USD/1k  | 50/50         | PASS     |
| total_billable_tokens            | 3946.360 tok | 66.0%       | 2260.523 tok  | <= 6000.00 tok  | 50/50         | PASS     |

## AI Cost & Token Breakdown (`2026-11-vertex-paygo-v1` — Standard PayGo)

| Cost / Efficiency Dimension                              | Current Run                               | Notes                                                            |
|----------------------------------------------------------|-------------------------------------------|------------------------------------------------------------------|
| Total SUT Cost / 1,000 Requests                          | $6.3032                                   | LLM tokens + Gemini 3 Google Search grounding ($14/1k queries)   |
| LLM Token-Only Cost / 1,000 Requests                     | $2.3832 (37.8%)                           | Uncached input + cached input + visible output + thinking tokens |
| Google Search Grounding Cost / 1,000 Requests            | $3.9200 (62.2%)                           | Grounded turns: 16.0% (avg 0.28 queries/req)                     |
| Quality-Adjusted Cost / 1,000 Successful Tasks           | $7.2313                                   | Total Cost/1k divided by multi_turn_task_success_v1 mean score   |
| Per-Request Cost Distribution (Mean / P50 / P95 / Max)   | $0.00630 / $0.00120 / $0.03260 / $0.06184 | Modeled 50-case batch SUT total: $0.31516                        |
| Mean Tokens / Request (Prompt / Cached / Out / Thoughts) | 3354 / 384 / 573 / 19                     | Total avg: 3946 tok (thinking = 3.2% of billable output)         |
| Workflow Calls & Self-Healing JSON Repair Rate           | 1.82 calls/req                            | json_parser fallback rate: 0.0%                                  |

- **Evaluation Run Spend Separation**: SUT live inference spend = `$0.31516` | Estimated Phase 2B Judge overhead (`gemini-4-hydrogen`, ~250 judge evaluations) = `$1.86999` _(excluded from SUT production cost metrics)_.

### Per-Sub-Agent Cost & Token Attribution

| Sub-Agent      | Model(s)                | Calls (Case %)   |   Avg Prompt Tok |   Avg Out Tok |   Avg Thoughts Tok |   Search Queries | Amortized $/1k Reqs   | Share of Cost   |
|----------------|-------------------------|------------------|------------------|---------------|--------------------|------------------|-----------------------|-----------------|
| `engage`       | `gemini-3.5-flash-lite` | 50 (100.0%)      |             1422 |            29 |                  0 |                0 | $0.4985               | 7.9%            |
| `filter`       | `gemini-3.5-flash-lite` | 12 (24.0%)       |             1013 |            45 |                  0 |                0 | $0.0997               | 1.6%            |
| `filter_smart` | `gemini-3.5-flash-lite` | 18 (36.0%)       |             3926 |          1396 |                 52 |               14 | $5.5435               | 87.9%           |
| `inspiration`  | `gemini-3.5-flash-lite` | 11 (22.0%)       |             1255 |           143 |                  0 |                0 | $0.1615               | 2.6%            |

### Analytical Cache-Hit Sensitivity Projections (Cold-Run Baseline Extrapolation)

#### 1. Application / Semantic Response Caching (Short-Circuits LLM + Google Search Grounding)

| Response Cache Hit Rate   | Projected Cost / 1k Reqs   | Projected Savings / 1k Reqs   | Projected Mean AI Latency   |
|---------------------------|----------------------------|-------------------------------|-----------------------------|
| 0%                        | $6.3032                    | -$0.0000 (-0.0%)              | 3.201s                      |
| 10%                       | $5.6729                    | -$0.6303 (-10.0%)             | 2.881s                      |
| 20%                       | $5.0426                    | -$1.2606 (-20.0%)             | 2.561s                      |
| 30%                       | $4.4123                    | -$1.8910 (-30.0%)             | 2.241s                      |
| 50%                       | $3.1516                    | -$3.1516 (-50.0%)             | 1.600s                      |

#### 2. Gemini Context Caching (Discounts Cached Input Prefix Tokens Only; Output & Search Unchanged)

| Prefix Cache Hit Rate   | Theoretical Cost / 1k (All Prompts)   | Threshold-Gated Cost / 1k (>= Min Tok)   | Max Input Token Savings / 1k   |
|-------------------------|---------------------------------------|------------------------------------------|--------------------------------|
| 0%                      | $6.3032 (-0.0%)                       | $6.3032 (-0.0%)                          | -$0.0000                       |
| 50%                     | $5.9024 (-6.4%)                       | $6.3032 (-0.0%)                          | -$0.4009                       |
| 80%                     | $5.6618 (-10.2%)                      | $6.3032 (-0.0%)                          | -$0.6414                       |
| 95%                     | $5.5416 (-12.1%)                      | $6.3032 (-0.0%)                          | -$0.7617                       |

- **Context Cache Prefix Threshold Eligibility**: `engage`: avg `1422` prompt tok (max `1453`, min required `4096` -> `0%` calls eligible); `filter`: avg `1013` prompt tok (max `1045`, min required `4096` -> `0%` calls eligible); `filter_smart`: avg `3926` prompt tok (max `3953`, min required `4096` -> `0%` calls eligible); `inspiration`: avg `1255` prompt tok (max `1309`, min required `4096` -> `0%` calls eligible)

## Agent Configuration Snapshot

| Sub-Agent      | Model                   | Prompt Hash (SHA-256)   | Tools         |
|----------------|-------------------------|-------------------------|---------------|
| `engage`       | `gemini-3.5-flash-lite` | `5308d715db76`          | none          |
| `filter`       | `gemini-3.5-flash-lite` | `1817f7a21c23`          | none          |
| `filter_smart` | `gemini-3.5-flash-lite` | `e5760e6d2697`          | google_search |
| `inspiration`  | `gemini-3.5-flash-lite` | `6df18991944b`          | none          |
| `json_parser`  | `gemini-3.5-flash-lite` | `e7fc8bdbc711`          | none          |
