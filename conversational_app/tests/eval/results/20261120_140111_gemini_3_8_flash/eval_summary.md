# GEAP EVALUATION SUMMARY — 20261120_140111_gemini_3_8_flash (50 EvalCases)

## Run Metadata

- **Run ID**: `20261120_140111_gemini_3_8_flash`
- **Run Name**: `gemini_3_8_flash`
- **Description**: Upgrade default primary model from gemini-3.5-flash-lite to gemini-3.8-flash
- **Baseline Reference**: `20261119_134306_baseline`
- **Eval Set ID**: `conversational_synthetic`
- **Timestamp (UTC)**: `2026-11-20T14:01:11.416182+00:00`
- **Cases Evaluated**: `50`
- **Git Revision**: `1858ecc` (branch: `ai-cost-eval`, dirty: `True`)

## Aggregated Metric Scores

| Metric Name                      | Mean Score   | Baseline     | Delta (Δ)     | Pass Rate   | Std Dev       | Threshold       | Valid/Total   | Status   |
|----------------------------------|--------------|--------------|---------------|-------------|---------------|-----------------|---------------|----------|
| multi_turn_task_success_v1       | 0.898        | 0.892        | +0.007        | 80.0%       | 0.224         | >= 0.80         | 50/50         | PASS     |
| multi_turn_trajectory_quality_v1 | 0.980        | 0.977        | +0.003        | 90.0%       | 0.068         | >= 0.80         | 50/50         | PASS     |
| tool_use_quality                 | 1.000        | 1.000        | +0.000        | 100.0%      | 0.000         | >= 0.80         | 49/50         | PASS     |
| coherence                        | 0.940        | 0.960        | -0.020        | 94.0%       | 0.240         | >= 0.80         | 50/50         | PASS     |
| schema_and_contract_valid        | 1.000        | 1.000        | +0.000        | 100.0%      | 0.000         | >= 0.95         | 50/50         | PASS     |
| conversation_plan_alignment      | 0.920        | 0.940        | -0.020        | 92.0%       | 0.274         | >= 0.80         | 50/50         | PASS     |
| latency_seconds                  | 2.915s       | 2.762s       | +0.153s       | 100.0%      | 2.171s        | <= 15.00s       | 50/50         | PASS     |
| cost_per_1k_requests_usd         | 6.623 USD/1k | 5.447 USD/1k | +1.176 USD/1k | 90.0%       | 15.514 USD/1k | <= 15.00 USD/1k | 50/50         | PASS     |
| llm_token_cost_per_1k_usd        | 2.143 USD/1k | 2.087 USD/1k | +0.056 USD/1k | 86.0%       | 2.119 USD/1k  | <= 5.00 USD/1k  | 50/50         | PASS     |
| total_billable_tokens            | 3938.880 tok | 3915.660 tok | +23.220 tok   | 64.0%       | 2303.351 tok  | <= 6000.00 tok  | 50/50         | PASS     |

## AI Cost & Token Breakdown (`2026-11-vertex-paygo-v1` — Standard PayGo)

| Cost / Efficiency Dimension                              | Current Run                               | Baseline   | Delta (Δ)   | Notes                                                            |
|----------------------------------------------------------|-------------------------------------------|------------|-------------|------------------------------------------------------------------|
| Total SUT Cost / 1,000 Requests                          | $6.6231                                   | $5.4466    | +1.1765     | LLM tokens + Gemini 3 Google Search grounding ($14/1k queries)   |
| LLM Token-Only Cost / 1,000 Requests                     | $2.1431 (32.4%)                           | $2.0866    | +0.0565     | Uncached input + cached input + visible output + thinking tokens |
| Google Search Grounding Cost / 1,000 Requests            | $4.4800 (67.6%)                           | $3.3600    | +1.1200     | Grounded turns: 10.0% (avg 0.32 queries/req)                     |
| Quality-Adjusted Cost / 1,000 Successful Tasks           | $7.3726                                   | $6.1084    | +1.2642     | Total Cost/1k divided by multi_turn_task_success_v1 mean score   |
| Per-Request Cost Distribution (Mean / P50 / P95 / Max)   | $0.00662 / $0.00115 / $0.04840 / $0.06361 | -          | -           | Modeled 50-case batch SUT total: $0.33115                        |
| Mean Tokens / Request (Prompt / Cached / Out / Thoughts) | 3464 / 309 / 475 / 0                      | -          | -           | Total avg: 3939 tok (thinking = 0.0% of billable output)         |
| Workflow Calls & Self-Healing JSON Repair Rate           | 1.86 calls/req                            | -          | -           | json_parser fallback rate: 0.0%                                  |

- **Evaluation Run Spend Separation**: SUT live inference spend = `$0.33115` | Estimated Phase 2B Judge overhead (`gemini-2.5-flash`, ~250 judge evaluations) = `$0.44786` _(excluded from SUT production cost metrics)_.

### Per-Sub-Agent Cost & Token Attribution

| Sub-Agent      | Model(s)                | Calls (Case %)   |   Avg Prompt Tok |   Avg Out Tok |   Avg Thoughts Tok |   Search Queries | Amortized $/1k Reqs   | Share of Cost   |
|----------------|-------------------------|------------------|------------------|---------------|--------------------|------------------|-----------------------|-----------------|
| `engage`       | `gemini-3.5-flash-lite` | 50 (100.0%)      |             1377 |            28 |                  0 |                0 | $0.4841               | 7.3%            |
| `filter`       | `gemini-3.5-flash-lite` | 17 (34.0%)       |              989 |            44 |                  0 |                0 | $0.1382               | 2.1%            |
| `filter_smart` | `gemini-3.5-flash-lite` | 18 (36.0%)       |             4313 |          1138 |                  0 |               16 | $5.8869               | 88.9%           |
| `inspiration`  | `gemini-3.5-flash-lite` | 8 (16.0%)        |             1239 |           136 |                  0 |                0 | $0.1139               | 1.7%            |

### Analytical Cache-Hit Sensitivity Projections (Cold-Run Baseline Extrapolation)

#### 1. Application / Semantic Response Caching (Short-Circuits LLM + Google Search Grounding)

| Response Cache Hit Rate   | Projected Cost / 1k Reqs   | Projected Savings / 1k Reqs   | Projected Mean AI Latency   |
|---------------------------|----------------------------|-------------------------------|-----------------------------|
| 0%                        | $6.6231                    | -$0.0000 (-0.0%)              | 2.915s                      |
| 10%                       | $5.9608                    | -$0.6623 (-10.0%)             | 2.623s                      |
| 20%                       | $5.2985                    | -$1.3246 (-20.0%)             | 2.332s                      |
| 30%                       | $4.6361                    | -$1.9869 (-30.0%)             | 2.040s                      |
| 50%                       | $3.3115                    | -$3.3115 (-50.0%)             | 1.457s                      |

#### 2. Gemini Context Caching (Discounts Cached Input Prefix Tokens Only; Output & Search Unchanged)

| Prefix Cache Hit Rate   | Theoretical Cost / 1k (All Prompts)   | Threshold-Gated Cost / 1k (>= Min Tok)   | Max Input Token Savings / 1k   |
|-------------------------|---------------------------------------|------------------------------------------|--------------------------------|
| 0%                      | $6.6231 (-0.0%)                       | $6.6231 (-0.0%)                          | -$0.0000                       |
| 50%                     | $6.1972 (-6.4%)                       | $6.4552 (-2.5%)                          | -$0.4259                       |
| 80%                     | $5.9417 (-10.3%)                      | $6.3545 (-4.0%)                          | -$0.6814                       |
| 95%                     | $5.8139 (-12.2%)                      | $6.3041 (-4.8%)                          | -$0.8092                       |

- **Context Cache Prefix Threshold Eligibility**: `engage`: avg `1377` prompt tok (max `1431`, min required `4096` -> `0%` calls eligible); `filter`: avg `989` prompt tok (max `1019`, min required `4096` -> `0%` calls eligible); `filter_smart`: avg `4313` prompt tok (max `4327`, min required `4096` -> `100%` calls eligible); `inspiration`: avg `1239` prompt tok (max `1270`, min required `4096` -> `0%` calls eligible)

## Agent Configuration Snapshot

| Sub-Agent      | Model                   | Prompt Hash (SHA-256)   | Tools         |
|----------------|-------------------------|-------------------------|---------------|
| `engage`       | `gemini-3.5-flash-lite` | `5308d715db76`          | none          |
| `filter`       | `gemini-3.5-flash-lite` | `1817f7a21c23`          | none          |
| `filter_smart` | `gemini-3.5-flash-lite` | `ea9dfbe41e4a`          | google_search |
| `inspiration`  | `gemini-3.5-flash-lite` | `6df18991944b`          | none          |
| `json_parser`  | `gemini-3.5-flash-lite` | `e7fc8bdbc711`          | none          |
