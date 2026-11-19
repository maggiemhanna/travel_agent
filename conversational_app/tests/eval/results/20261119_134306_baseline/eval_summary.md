# GEAP EVALUATION SUMMARY — 20261119_134306_baseline (50 EvalCases)

## Run Metadata

- **Run ID**: `20261119_134306_baseline`
- **Run Name**: `baseline`
- **Description**: Clean 50-case baseline with Standard PayGo token & Google Search cost tracking
- **Baseline Reference**: `Pinned as active baseline`
- **Eval Set ID**: `conversational_synthetic`
- **Timestamp (UTC)**: `2026-11-19T13:43:06.871056+00:00`
- **Cases Evaluated**: `50`
- **Git Revision**: `4e4b520` (branch: `ai-cost-eval`, dirty: `True`)

## Aggregated Metric Scores

| Metric Name                      | Mean Score   | Pass Rate   | Std Dev       | Threshold       | Valid/Total   | Status   |
|----------------------------------|--------------|-------------|---------------|-----------------|---------------|----------|
| multi_turn_task_success_v1       | 0.892        | 82.0%       | 0.255         | >= 0.80         | 50/50         | PASS     |
| multi_turn_trajectory_quality_v1 | 0.977        | 90.0%       | 0.078         | >= 0.80         | 50/50         | PASS     |
| tool_use_quality                 | 1.000        | 100.0%      | 0.000         | >= 0.80         | 50/50         | PASS     |
| coherence                        | 0.960        | 96.0%       | 0.198         | >= 0.80         | 50/50         | PASS     |
| schema_and_contract_valid        | 1.000        | 100.0%      | 0.000         | >= 0.95         | 50/50         | PASS     |
| conversation_plan_alignment      | 0.940        | 94.0%       | 0.240         | >= 0.80         | 50/50         | PASS     |
| latency_seconds                  | 2.762s       | 100.0%      | 1.887s        | <= 15.00s       | 50/50         | PASS     |
| cost_per_1k_requests_usd         | 5.447 USD/1k | 90.0%       | 11.800 USD/1k | <= 15.00 USD/1k | 50/50         | PASS     |
| llm_token_cost_per_1k_usd        | 2.087 USD/1k | 88.0%       | 2.037 USD/1k  | <= 5.00 USD/1k  | 50/50         | PASS     |
| total_billable_tokens            | 3915.660 tok | 66.0%       | 2272.916 tok  | <= 6000.00 tok  | 50/50         | PASS     |

## AI Cost & Token Breakdown (`2026-11-vertex-paygo-v1` — Standard PayGo)

| Cost / Efficiency Dimension                              | Current Run                               | Notes                                                            |
|----------------------------------------------------------|-------------------------------------------|------------------------------------------------------------------|
| Total SUT Cost / 1,000 Requests                          | $5.4466                                   | LLM tokens + Gemini 3 Google Search grounding ($14/1k queries)   |
| LLM Token-Only Cost / 1,000 Requests                     | $2.0866 (38.3%)                           | Uncached input + cached input + visible output + thinking tokens |
| Google Search Grounding Cost / 1,000 Requests            | $3.3600 (61.7%)                           | Grounded turns: 10.0% (avg 0.24 queries/req)                     |
| Quality-Adjusted Cost / 1,000 Successful Tasks           | $6.1084                                   | Total Cost/1k divided by multi_turn_task_success_v1 mean score   |
| Per-Request Cost Distribution (Mean / P50 / P95 / Max)   | $0.00545 / $0.00117 / $0.03353 / $0.05985 | Modeled 50-case batch SUT total: $0.27233                        |
| Mean Tokens / Request (Prompt / Cached / Out / Thoughts) | 3463 / 309 / 452 / 0                      | Total avg: 3916 tok (thinking = 0.0% of billable output)         |
| Workflow Calls & Self-Healing JSON Repair Rate           | 1.86 calls/req                            | json_parser fallback rate: 0.0%                                  |

- **Evaluation Run Spend Separation**: SUT live inference spend = `$0.27233` | Estimated Phase 2B Judge overhead (`gemini-2.5-flash`, ~250 judge evaluations) = `$0.44622` _(excluded from SUT production cost metrics)_.

### Per-Sub-Agent Cost & Token Attribution

| Sub-Agent      | Model(s)                | Calls (Case %)   |   Avg Prompt Tok |   Avg Out Tok |   Avg Thoughts Tok |   Search Queries | Amortized $/1k Reqs   | Share of Cost   |
|----------------|-------------------------|------------------|------------------|---------------|--------------------|------------------|-----------------------|-----------------|
| `engage`       | `gemini-3.5-flash-lite` | 50 (100.0%)      |             1377 |            28 |                  0 |                0 | $0.4831               | 8.9%            |
| `filter`       | `gemini-3.5-flash-lite` | 17 (34.0%)       |              987 |            44 |                  0 |                0 | $0.1382               | 2.5%            |
| `filter_smart` | `gemini-3.5-flash-lite` | 18 (36.0%)       |             4313 |          1076 |                  0 |               12 | $4.7104               | 86.5%           |
| `inspiration`  | `gemini-3.5-flash-lite` | 8 (16.0%)        |             1237 |           139 |                  0 |                0 | $0.1149               | 2.1%            |

### Analytical Cache-Hit Sensitivity Projections (Cold-Run Baseline Extrapolation)

#### 1. Application / Semantic Response Caching (Short-Circuits LLM + Google Search Grounding)

| Response Cache Hit Rate   | Projected Cost / 1k Reqs   | Projected Savings / 1k Reqs   | Projected Mean AI Latency   |
|---------------------------|----------------------------|-------------------------------|-----------------------------|
| 0%                        | $5.4466                    | -$0.0000 (-0.0%)              | 2.762s                      |
| 10%                       | $4.9020                    | -$0.5447 (-10.0%)             | 2.485s                      |
| 20%                       | $4.3573                    | -$1.0893 (-20.0%)             | 2.209s                      |
| 30%                       | $3.8127                    | -$1.6340 (-30.0%)             | 1.933s                      |
| 50%                       | $2.7233                    | -$2.7233 (-50.0%)             | 1.381s                      |

#### 2. Gemini Context Caching (Discounts Cached Input Prefix Tokens Only; Output & Search Unchanged)

| Prefix Cache Hit Rate   | Theoretical Cost / 1k (All Prompts)   | Threshold-Gated Cost / 1k (>= Min Tok)   | Max Input Token Savings / 1k   |
|-------------------------|---------------------------------------|------------------------------------------|--------------------------------|
| 0%                      | $5.4466 (-0.0%)                       | $5.4466 (-0.0%)                          | -$0.0000                       |
| 50%                     | $5.0209 (-7.8%)                       | $5.2788 (-3.1%)                          | -$0.4258                       |
| 80%                     | $4.7654 (-12.5%)                      | $5.1781 (-4.9%)                          | -$0.6812                       |
| 95%                     | $4.6377 (-14.8%)                      | $5.1277 (-5.9%)                          | -$0.8090                       |

- **Context Cache Prefix Threshold Eligibility**: `engage`: avg `1377` prompt tok (max `1431`, min required `4096` -> `0%` calls eligible); `filter`: avg `987` prompt tok (max `1006`, min required `4096` -> `0%` calls eligible); `filter_smart`: avg `4313` prompt tok (max `4327`, min required `4096` -> `100%` calls eligible); `inspiration`: avg `1237` prompt tok (max `1280`, min required `4096` -> `0%` calls eligible)

## Agent Configuration Snapshot

| Sub-Agent      | Model                   | Prompt Hash (SHA-256)   | Tools         |
|----------------|-------------------------|-------------------------|---------------|
| `engage`       | `gemini-3.5-flash-lite` | `5308d715db76`          | none          |
| `filter`       | `gemini-3.5-flash-lite` | `1817f7a21c23`          | none          |
| `filter_smart` | `gemini-3.5-flash-lite` | `ea9dfbe41e4a`          | google_search |
| `inspiration`  | `gemini-3.5-flash-lite` | `6df18991944b`          | none          |
| `json_parser`  | `gemini-3.5-flash-lite` | `e7fc8bdbc711`          | none          |
