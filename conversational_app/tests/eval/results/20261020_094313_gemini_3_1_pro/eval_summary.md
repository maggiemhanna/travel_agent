# GEAP EVALUATION SUMMARY — 20261020_094313_gemini_3_1_pro (50 EvalCases)

## Run Metadata

- **Run ID**: `20261020_094313_gemini_3_1_pro`
- **Run Name**: `gemini_3_1_pro`
- **Description**: Upgrade all 5 sub-agents from gemini-3.5-flash-lite to gemini-3.1-pro-preview
- **Baseline Reference**: `20261020_093127_baseline`
- **Eval Set ID**: `conversational_synthetic`
- **Timestamp (UTC)**: `2026-10-20T09:43:13.394902+00:00`
- **Cases Evaluated**: `50`
- **Git Revision**: `b23b4f4` (branch: `evaluation`, dirty: `True`)

## Aggregated Metric Scores

| Metric Name                      | Mean Score   | Baseline   | Delta (Δ)   | Pass Rate   | Std Dev   | Threshold   | Valid/Total   | Status   |
|----------------------------------|--------------|------------|-------------|-------------|-----------|-------------|---------------|----------|
| multi_turn_task_success_v1       | 0.853        | 0.840      | +0.013      | 82.0%       | 0.340     | >= 0.80     | 50/50         | PASS     |
| multi_turn_trajectory_quality_v1 | 0.954        | 0.929      | +0.026      | 88.0%       | 0.147     | >= 0.80     | 50/50         | PASS     |
| tool_use_quality                 | 0.960        | 0.900      | +0.060      | 96.0%       | 0.198     | >= 0.80     | 50/50         | PASS     |
| coherence                        | 1.000        | 0.900      | +0.100      | 100.0%      | 0.000     | >= 0.80     | 50/50         | PASS     |
| schema_and_contract_valid        | 1.000        | 1.000      | +0.000      | 100.0%      | 0.000     | >= 0.95     | 50/50         | PASS     |
| conversation_plan_alignment      | 0.900        | 0.860      | +0.040      | 90.0%       | 0.303     | >= 0.80     | 50/50         | PASS     |
| latency_seconds                  | 19.792s      | 2.593s     | +17.199s    | 54.0%       | 16.862s   | <= 15.00s   | 50/50         | FAIL     |

## Agent Configuration Snapshot

| Sub-Agent      | Model                    | Prompt Hash (SHA-256)   | Tools         |
|----------------|--------------------------|-------------------------|---------------|
| `engage`       | `gemini-3.1-pro-preview` | `66d7c3a65f42`          | none          |
| `filter`       | `gemini-3.1-pro-preview` | `1817f7a21c23`          | none          |
| `filter_smart` | `gemini-3.1-pro-preview` | `ef1a2261eb0b`          | google_search |
| `inspiration`  | `gemini-3.1-pro-preview` | `6df18991944b`          | none          |
| `json_parser`  | `gemini-3.1-pro-preview` | `e7fc8bdbc711`          | none          |
