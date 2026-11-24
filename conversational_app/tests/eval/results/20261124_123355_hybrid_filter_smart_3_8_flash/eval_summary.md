# GEAP EVALUATION SUMMARY — 20261124_123355_hybrid_filter_smart_3_8_flash (50 EvalCases)

## Run Metadata

- **Run ID**: `20261124_123355_hybrid_filter_smart_3_8_flash`
- **Run Name**: `hybrid_filter_smart_3_8_flash`
- **Description**: Hybrid: filter_smart on gemini-3.8-flash (budget 512), all other sub-agents on gemini-3.5-flash-lite (budget 0)
- **Baseline Reference**: `20261124_122326_baseline_all_3_5_flash_lite`
- **Eval Set ID**: `conversational_synthetic`
- **Timestamp (UTC)**: `2026-11-24T12:33:55.139683+00:00`
- **Cases Evaluated**: `50`
- **Git Revision**: `cea05e9` (branch: `eval/clean-model-benchmark`, dirty: `True`)

## Aggregated Metric Scores

| Metric Name                      | Mean Score   | Baseline     | Delta (Δ)     | Pass Rate   | Std Dev       | Threshold       | Valid/Total   | Status   |
|----------------------------------|--------------|--------------|---------------|-------------|---------------|-----------------|---------------|----------|
| multi_turn_task_success_v1       | 0.892        | 0.872        | +0.020        | 74.0%       | 0.199         | >= 0.80         | 50/50         | PASS     |
| multi_turn_trajectory_quality_v1 | 0.944        | 0.966        | -0.021        | 80.0%       | 0.122         | >= 0.80         | 50/50         | PASS     |
| tool_use_quality                 | 0.979        | 1.000        | -0.021        | 97.9%       | 0.144         | >= 0.80         | 48/50         | PASS     |
| coherence                        | 0.920        | 0.920        | +0.000        | 92.0%       | 0.274         | >= 0.80         | 50/50         | PASS     |
| schema_and_contract_valid        | 1.000        | 1.000        | +0.000        | 100.0%      | 0.000         | >= 0.95         | 50/50         | PASS     |
| conversation_plan_alignment      | 0.920        | 0.840        | +0.080        | 92.0%       | 0.274         | >= 0.80         | 50/50         | PASS     |
| latency_seconds                  | 6.145s       | 3.201s       | +2.944s       | 86.0%       | 6.772s        | <= 15.00s       | 50/50         | PASS     |
| cost_per_1k_requests_usd         | 8.656 USD/1k | 6.303 USD/1k | +2.352 USD/1k | 84.0%       | 13.575 USD/1k | <= 15.00 USD/1k | 50/50         | PASS     |
| llm_token_cost_per_1k_usd        | 4.456 USD/1k | 2.383 USD/1k | +2.072 USD/1k | 64.0%       | 5.105 USD/1k  | <= 5.00 USD/1k  | 50/50         | PASS     |
| total_billable_tokens            | 4127.860 tok | 3946.360 tok | +181.500 tok  | 64.0%       | 2511.422 tok  | <= 6000.00 tok  | 50/50         | PASS     |

## AI Cost & Token Breakdown (`2026-11-vertex-paygo-v1` — Standard PayGo)

| Cost / Efficiency Dimension                              | Current Run                               | Baseline   | Delta (Δ)   | Notes                                                            |
|----------------------------------------------------------|-------------------------------------------|------------|-------------|------------------------------------------------------------------|
| Total SUT Cost / 1,000 Requests                          | $8.6556                                   | $6.3032    | +2.3524     | LLM tokens + Gemini 3 Google Search grounding ($14/1k queries)   |
| LLM Token-Only Cost / 1,000 Requests                     | $4.4556 (51.5%)                           | $2.3832    | +2.0724     | Uncached input + cached input + visible output + thinking tokens |
| Google Search Grounding Cost / 1,000 Requests            | $4.2000 (48.5%)                           | $3.9200    | +0.2800     | Grounded turns: 16.0% (avg 0.30 queries/req)                     |
| Quality-Adjusted Cost / 1,000 Successful Tasks           | $9.7072                                   | $7.2313    | +2.4759     | Total Cost/1k divided by multi_turn_task_success_v1 mean score   |
| Per-Request Cost Distribution (Mean / P50 / P95 / Max)   | $0.00866 / $0.00121 / $0.03962 / $0.04666 | -          | -           | Modeled 50-case batch SUT total: $0.43278                        |
| Mean Tokens / Request (Prompt / Cached / Out / Thoughts) | 3354 / 0 / 604 / 170                      | -          | -           | Total avg: 4128 tok (thinking = 22.0% of billable output)        |
| Workflow Calls & Self-Healing JSON Repair Rate           | 1.82 calls/req                            | -          | -           | json_parser fallback rate: 0.0%                                  |

- **Evaluation Run Spend Separation**: SUT live inference spend = `$0.43278` | Estimated Phase 2B Judge overhead (`gemini-4-hydrogen`, ~250 judge evaluations) = `$1.87810` _(excluded from SUT production cost metrics)_.

### Per-Sub-Agent Cost & Token Attribution

| Sub-Agent      | Model(s)                | Calls (Case %)   |   Avg Prompt Tok |   Avg Out Tok |   Avg Thoughts Tok |   Search Queries | Amortized $/1k Reqs   | Share of Cost   |
|----------------|-------------------------|------------------|------------------|---------------|--------------------|------------------|-----------------------|-----------------|
| `engage`       | `gemini-3.5-flash-lite` | 50 (100.0%)      |             1422 |            29 |                  0 |                0 | $0.4982               | 5.8%            |
| `filter`       | `gemini-3.5-flash-lite` | 12 (24.0%)       |             1012 |            45 |                  0 |                0 | $0.0999               | 1.2%            |
| `filter_smart` | `gemini-3.8-flash`      | 18 (36.0%)       |             3926 |          1478 |                474 |               15 | $7.8949               | 91.2%           |
| `inspiration`  | `gemini-3.5-flash-lite` | 11 (22.0%)       |             1254 |           145 |                  0 |                0 | $0.1625               | 1.9%            |

### Analytical Cache-Hit Sensitivity Projections (Cold-Run Baseline Extrapolation)

#### 1. Application / Semantic Response Caching (Short-Circuits LLM + Google Search Grounding)

| Response Cache Hit Rate   | Projected Cost / 1k Reqs   | Projected Savings / 1k Reqs   | Projected Mean AI Latency   |
|---------------------------|----------------------------|-------------------------------|-----------------------------|
| 0%                        | $8.6556                    | -$0.0000 (-0.0%)              | 6.145s                      |
| 10%                       | $7.7900                    | -$0.8656 (-10.0%)             | 5.530s                      |
| 20%                       | $6.9245                    | -$1.7311 (-20.0%)             | 4.916s                      |
| 30%                       | $6.0589                    | -$2.5967 (-30.0%)             | 4.301s                      |
| 50%                       | $4.3278                    | -$4.3278 (-50.0%)             | 3.072s                      |

#### 2. Gemini Context Caching (Discounts Cached Input Prefix Tokens Only; Output & Search Unchanged)

| Prefix Cache Hit Rate   | Theoretical Cost / 1k (All Prompts)   | Threshold-Gated Cost / 1k (>= Min Tok)   | Max Input Token Savings / 1k   |
|-------------------------|---------------------------------------|------------------------------------------|--------------------------------|
| 0%                      | $8.6556 (-0.0%)                       | $8.6556 (-0.0%)                          | -$0.0000                       |
| 50%                     | $7.9166 (-8.5%)                       | $8.6556 (-0.0%)                          | -$0.7390                       |
| 80%                     | $7.4732 (-13.7%)                      | $8.6556 (-0.0%)                          | -$1.1824                       |
| 95%                     | $7.2515 (-16.2%)                      | $8.6556 (-0.0%)                          | -$1.4041                       |

- **Context Cache Prefix Threshold Eligibility**: `engage`: avg `1422` prompt tok (max `1453`, min required `4096` -> `0%` calls eligible); `filter`: avg `1012` prompt tok (max `1039`, min required `4096` -> `0%` calls eligible); `filter_smart`: avg `3926` prompt tok (max `3940`, min required `4096` -> `0%` calls eligible); `inspiration`: avg `1254` prompt tok (max `1318`, min required `4096` -> `0%` calls eligible)

## Agent Configuration Snapshot

| Sub-Agent      | Model                   | Prompt Hash (SHA-256)   | Tools         |
|----------------|-------------------------|-------------------------|---------------|
| `engage`       | `gemini-3.5-flash-lite` | `5308d715db76`          | none          |
| `filter`       | `gemini-3.5-flash-lite` | `1817f7a21c23`          | none          |
| `filter_smart` | `gemini-3.8-flash`      | `e5760e6d2697`          | google_search |
| `inspiration`  | `gemini-3.5-flash-lite` | `6df18991944b`          | none          |
| `json_parser`  | `gemini-3.5-flash-lite` | `e7fc8bdbc711`          | none          |
