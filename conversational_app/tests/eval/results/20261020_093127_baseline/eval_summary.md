# GEAP EVALUATION SUMMARY — 20261020_093127_baseline (50 EvalCases)

## Run Metadata

- **Run ID**: `20261020_093127_baseline`
- **Run Name**: `baseline`
- **Description**: Full 50-case baseline evaluation
- **Baseline Reference**: `Pinned as active baseline`
- **Eval Set ID**: `conversational_synthetic`
- **Timestamp (UTC)**: `2026-10-20T09:31:27.212987+00:00`
- **Cases Evaluated**: `50`
- **Git Revision**: `c4cff37` (branch: `evaluation`, dirty: `True`)

## Aggregated Metric Scores

| Metric Name                      | Mean Score   | Pass Rate   | Std Dev   | Threshold   | Valid/Total   | Status   |
|----------------------------------|--------------|-------------|-----------|-------------|---------------|----------|
| multi_turn_task_success_v1       | 0.840        | 76.0%       | 0.312     | >= 0.80     | 50/50         | PASS     |
| multi_turn_trajectory_quality_v1 | 0.929        | 82.0%       | 0.175     | >= 0.80     | 50/50         | PASS     |
| tool_use_quality                 | 0.900        | 90.0%       | 0.303     | >= 0.80     | 50/50         | PASS     |
| coherence                        | 0.900        | 90.0%       | 0.303     | >= 0.80     | 50/50         | PASS     |
| schema_and_contract_valid        | 1.000        | 100.0%      | 0.000     | >= 0.95     | 50/50         | PASS     |
| conversation_plan_alignment      | 0.860        | 86.0%       | 0.351     | >= 0.80     | 50/50         | PASS     |
| latency_seconds                  | 2.593s       | 100.0%      | 1.455s    | <= 15.00s   | 50/50         | PASS     |

## Agent Configuration Snapshot

| Sub-Agent      | Model                   | Prompt Hash (SHA-256)   | Tools         |
|----------------|-------------------------|-------------------------|---------------|
| `engage`       | `gemini-3.5-flash-lite` | `66d7c3a65f42`          | none          |
| `filter`       | `gemini-3.5-flash-lite` | `1817f7a21c23`          | none          |
| `filter_smart` | `gemini-3.5-flash-lite` | `ef1a2261eb0b`          | google_search |
| `inspiration`  | `gemini-3.5-flash-lite` | `6df18991944b`          | none          |
| `json_parser`  | `gemini-3.5-flash-lite` | `e7fc8bdbc711`          | none          |
