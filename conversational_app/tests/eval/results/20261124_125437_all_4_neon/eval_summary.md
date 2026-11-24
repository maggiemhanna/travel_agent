# GEAP EVALUATION SUMMARY — 20261124_125437_all_4_neon (50 EvalCases)

## Run Metadata

- **Run ID**: `20261124_125437_all_4_neon`
- **Run Name**: `all_4_neon`
- **Description**: All sub-agents on gemini-4-neon (MEDIUM thinking on filter_smart, LOW thinking on engage/filter/inspiration/json_parser)
- **Baseline Reference**: `20261124_122326_baseline_all_3_5_flash_lite`
- **Eval Set ID**: `conversational_synthetic`
- **Timestamp (UTC)**: `2026-11-24T12:54:37.948435+00:00`
- **Cases Evaluated**: `50`
- **Git Revision**: `38e070a` (branch: `eval/clean-model-benchmark`, dirty: `True`)

## Aggregated Metric Scores

| Metric Name                      | Mean Score    | Baseline     | Delta (Δ)      | Pass Rate   | Std Dev       | Threshold       | Valid/Total   | Status   |
|----------------------------------|---------------|--------------|----------------|-------------|---------------|-----------------|---------------|----------|
| multi_turn_task_success_v1       | 0.913         | 0.872        | +0.042         | 76.0%       | 0.161         | >= 0.80         | 50/50         | PASS     |
| multi_turn_trajectory_quality_v1 | 0.983         | 0.966        | +0.017         | 92.0%       | 0.063         | >= 0.80         | 50/50         | PASS     |
| tool_use_quality                 | 1.000         | 1.000        | +0.000         | 100.0%      | 0.000         | >= 0.80         | 50/50         | PASS     |
| coherence                        | 1.000         | 0.920        | +0.080         | 100.0%      | 0.000         | >= 0.80         | 50/50         | PASS     |
| schema_and_contract_valid        | 1.000         | 1.000        | +0.000         | 100.0%      | 0.000         | >= 0.95         | 50/50         | PASS     |
| conversation_plan_alignment      | 0.980         | 0.840        | +0.140         | 98.0%       | 0.141         | >= 0.80         | 50/50         | PASS     |
| latency_seconds                  | 40.613s       | 3.201s       | +37.412s       | 38.0%       | 46.330s       | <= 15.00s       | 50/50         | FAIL     |
| cost_per_1k_requests_usd         | 44.024 USD/1k | 6.303 USD/1k | +37.721 USD/1k | 40.0%       | 41.680 USD/1k | <= 15.00 USD/1k | 50/50         | FAIL     |
| llm_token_cost_per_1k_usd        | 38.144 USD/1k | 2.383 USD/1k | +35.761 USD/1k | 0.0%        | 31.553 USD/1k | <= 5.00 USD/1k  | 50/50         | FAIL     |
| total_billable_tokens            | 5508.320 tok  | 3946.360 tok | +1561.960 tok  | 60.0%       | 3386.817 tok  | <= 6000.00 tok  | 50/50         | PASS     |

## AI Cost & Token Breakdown (`2026-11-vertex-paygo-v1` — Standard PayGo)

| Cost / Efficiency Dimension                              | Current Run                               | Baseline   | Delta (Δ)   | Notes                                                            |
|----------------------------------------------------------|-------------------------------------------|------------|-------------|------------------------------------------------------------------|
| Total SUT Cost / 1,000 Requests                          | $44.0239                                  | $6.3032    | +37.7207    | LLM tokens + Gemini 3 Google Search grounding ($14/1k queries)   |
| LLM Token-Only Cost / 1,000 Requests                     | $38.1439 (86.6%)                          | $2.3832    | +35.7607    | Uncached input + cached input + visible output + thinking tokens |
| Google Search Grounding Cost / 1,000 Requests            | $5.8800 (13.4%)                           | $3.9200    | +1.9600     | Grounded turns: 18.0% (avg 0.42 queries/req)                     |
| Quality-Adjusted Cost / 1,000 Successful Tasks           | $48.2014                                  | $7.2313    | +40.9701    | Total Cost/1k divided by multi_turn_task_success_v1 mean score   |
| Per-Request Cost Distribution (Mean / P50 / P95 / Max)   | $0.04402 / $0.01950 / $0.12641 / $0.13500 | -          | -           | Modeled 50-case batch SUT total: $2.20120                        |
| Mean Tokens / Request (Prompt / Cached / Out / Thoughts) | 3707 / 0 / 723 / 1078                     | -          | -           | Total avg: 5508 tok (thinking = 59.9% of billable output)        |
| Workflow Calls & Self-Healing JSON Repair Rate           | 1.80 calls/req                            | -          | -           | json_parser fallback rate: 0.0%                                  |

- **Evaluation Run Spend Separation**: SUT live inference spend = `$2.20120` | Estimated Phase 2B Judge overhead (`gemini-4-hydrogen`, ~250 judge evaluations) = `$1.92264` _(excluded from SUT production cost metrics)_.

### Per-Sub-Agent Cost & Token Attribution

| Sub-Agent      | Model(s)        | Calls (Case %)   |   Avg Prompt Tok |   Avg Out Tok |   Avg Thoughts Tok |   Search Queries | Amortized $/1k Reqs   | Share of Cost   |
|----------------|-----------------|------------------|------------------|---------------|--------------------|------------------|-----------------------|-----------------|
| `engage`       | `gemini-4-neon` | 50 (100.0%)      |             1555 |            53 |                200 |                0 | $8.4519               | 19.2%           |
| `filter`       | `gemini-4-neon` | 10 (20.0%)       |             1163 |            51 |                110 |                0 | $1.1816               | 2.7%            |
| `filter_smart` | `gemini-4-neon` | 20 (40.0%)       |             4103 |          1570 |               1964 |               21 | $32.0049              | 72.7%           |
| `inspiration`  | `gemini-4-neon` | 10 (20.0%)       |             1390 |           159 |                358 |                0 | $2.3855               | 5.4%            |

### Analytical Cache-Hit Sensitivity Projections (Cold-Run Baseline Extrapolation)

#### 1. Application / Semantic Response Caching (Short-Circuits LLM + Google Search Grounding)

| Response Cache Hit Rate   | Projected Cost / 1k Reqs   | Projected Savings / 1k Reqs   | Projected Mean AI Latency   |
|---------------------------|----------------------------|-------------------------------|-----------------------------|
| 0%                        | $44.0239                   | -$0.0000 (-0.0%)              | 40.613s                     |
| 10%                       | $39.6215                   | -$4.4024 (-10.0%)             | 36.552s                     |
| 20%                       | $35.2191                   | -$8.8048 (-20.0%)             | 32.490s                     |
| 30%                       | $30.8167                   | -$13.2072 (-30.0%)            | 28.429s                     |
| 50%                       | $22.0120                   | -$22.0120 (-50.0%)            | 20.306s                     |

#### 2. Gemini Context Caching (Discounts Cached Input Prefix Tokens Only; Output & Search Unchanged)

| Prefix Cache Hit Rate   | Theoretical Cost / 1k (All Prompts)   | Threshold-Gated Cost / 1k (>= Min Tok)   | Max Input Token Savings / 1k   |
|-------------------------|---------------------------------------|------------------------------------------|--------------------------------|
| 0%                      | $44.0239 (-0.0%)                      | $44.0239 (-0.0%)                         | -$0.0000                       |
| 50%                     | $39.0198 (-11.4%)                     | $42.4700 (-3.5%)                         | -$5.0041                       |
| 80%                     | $36.0174 (-18.2%)                     | $41.5376 (-5.7%)                         | -$8.0066                       |
| 95%                     | $34.5161 (-21.6%)                     | $41.0715 (-6.7%)                         | -$9.5078                       |

- **Context Cache Prefix Threshold Eligibility**: `engage`: avg `1555` prompt tok (max `1981`, min required `4096` -> `0%` calls eligible); `filter`: avg `1163` prompt tok (max `1185`, min required `4096` -> `0%` calls eligible); `filter_smart`: avg `4103` prompt tok (max `4128`, min required `4096` -> `70%` calls eligible); `inspiration`: avg `1390` prompt tok (max `1404`, min required `4096` -> `0%` calls eligible)

## Agent Configuration Snapshot

| Sub-Agent      | Model           | Prompt Hash (SHA-256)   | Tools         |
|----------------|-----------------|-------------------------|---------------|
| `engage`       | `gemini-4-neon` | `5308d715db76`          | none          |
| `filter`       | `gemini-4-neon` | `1817f7a21c23`          | none          |
| `filter_smart` | `gemini-4-neon` | `e5760e6d2697`          | google_search |
| `inspiration`  | `gemini-4-neon` | `6df18991944b`          | none          |
| `json_parser`  | `gemini-4-neon` | `e7fc8bdbc711`          | none          |
