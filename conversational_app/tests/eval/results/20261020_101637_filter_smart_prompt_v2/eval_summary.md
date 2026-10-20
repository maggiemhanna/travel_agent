# GEAP EVALUATION SUMMARY — 20261020_101637_filter_smart_prompt_v2 (50 EvalCases)

## Run Metadata

- **Run ID**: `20261020_101637_filter_smart_prompt_v2`
- **Run Name**: `filter_smart_prompt_v2`
- **Description**: Clarify mandatory Google Search triggers and output consistency in filter_smart prompt
- **Baseline Reference**: `20261020_093127_baseline`
- **Eval Set ID**: `conversational_synthetic`
- **Timestamp (UTC)**: `2026-10-20T10:16:37.210474+00:00`
- **Cases Evaluated**: `50`
- **Git Revision**: `e86a965` (branch: `evaluation`, dirty: `True`)

## Aggregated Metric Scores

| Metric Name                      | Mean Score   | Baseline   | Delta (Δ)   | Pass Rate   | Std Dev   | Threshold   | Valid/Total   | Status   |
|----------------------------------|--------------|------------|-------------|-------------|-----------|-------------|---------------|----------|
| multi_turn_task_success_v1       | 0.888        | 0.840      | +0.048      | 82.0%       | 0.261     | >= 0.80     | 50/50         | PASS     |
| multi_turn_trajectory_quality_v1 | 0.966        | 0.929      | +0.038      | 88.0%       | 0.104     | >= 0.80     | 50/50         | PASS     |
| tool_use_quality                 | 0.980        | 0.900      | +0.080      | 98.0%       | 0.143     | >= 0.80     | 49/50         | PASS     |
| coherence                        | 0.940        | 0.900      | +0.040      | 94.0%       | 0.240     | >= 0.80     | 50/50         | PASS     |
| schema_and_contract_valid        | 1.000        | 1.000      | +0.000      | 100.0%      | 0.000     | >= 0.95     | 50/50         | PASS     |
| conversation_plan_alignment      | 0.900        | 0.860      | +0.040      | 90.0%       | 0.303     | >= 0.80     | 50/50         | PASS     |
| latency_seconds                  | 2.487s       | 2.593s     | -0.107s     | 100.0%      | 1.791s    | <= 15.00s   | 50/50         | PASS     |

## Agent Configuration Snapshot

| Sub-Agent      | Model                   | Prompt Hash (SHA-256)   | Tools         |
|----------------|-------------------------|-------------------------|---------------|
| `engage`       | `gemini-3.5-flash-lite` | `66d7c3a65f42`          | none          |
| `filter`       | `gemini-3.5-flash-lite` | `1817f7a21c23`          | none          |
| `filter_smart` | `gemini-3.5-flash-lite` | `56f7737bfd9f`          | google_search |
| `inspiration`  | `gemini-3.5-flash-lite` | `6df18991944b`          | none          |
| `json_parser`  | `gemini-3.5-flash-lite` | `e7fc8bdbc711`          | none          |
