# GEAP EVALUATION SUMMARY — 20261019_181638_baseline_v2 (5 EvalCases)

## Run Metadata

- **Run ID**: `20261019_181638_baseline_v2`
- **Run Name**: `baseline_v2`
- **Description**: 5-case validation with standardized sub-agent names and Option A tool_use_quality + google_search grounding bridge
- **Baseline Reference**: `Pinned as active baseline`
- **Eval Set ID**: `conversational_synthetic`
- **Timestamp (UTC)**: `2026-10-19T18:16:38.143014+00:00`
- **Cases Evaluated**: `5`
- **Git Revision**: `093ba64` (branch: `evaluation`, dirty: `True`)

## Aggregated Metric Scores

| Metric Name                      | Mean Score   | Pass Rate   | Std Dev   | Threshold   | Valid/Total   | Status   |
|----------------------------------|--------------|-------------|-----------|-------------|---------------|----------|
| multi_turn_task_success_v1       | 0.800        | 80.0%       | 0.447     | >= 0.80     | 5/5           | PASS     |
| multi_turn_trajectory_quality_v1 | 0.842        | 60.0%       | 0.289     | >= 0.80     | 5/5           | PASS     |
| tool_use_quality                 | 0.800        | 80.0%       | 0.447     | >= 0.80     | 5/5           | PASS     |
| grounding_v1                     | 0.200        | 20.0%       | 0.447     | >= 0.80     | 5/5           | FAIL     |
| instruction_following_v1         | 0.833        | 50.0%       | 0.236     | >= 0.80     | 4/5           | PASS     |
| coherence                        | 1.000        | 100.0%      | 0.000     | >= 0.80     | 5/5           | PASS     |
| schema_and_contract_valid        | 1.000        | 100.0%      | 0.000     | >= 0.95     | 5/5           | PASS     |
| conversation_plan_alignment      | 1.000        | 100.0%      | 0.000     | >= 0.80     | 5/5           | PASS     |
| latency_seconds                  | 4.853s       | 100.0%      | 2.063s    | <= 15.00s   | 5/5           | PASS     |

## Agent Configuration Snapshot

| Sub-Agent      | Model                   | Prompt Hash (SHA-256)   | Tools         |
|----------------|-------------------------|-------------------------|---------------|
| `engage`       | `gemini-3.5-flash-lite` | `66d7c3a65f42`          | none          |
| `filter`       | `gemini-3.5-flash-lite` | `1817f7a21c23`          | none          |
| `filter_smart` | `gemini-3.5-flash-lite` | `ef1a2261eb0b`          | google_search |
| `inspiration`  | `gemini-3.5-flash-lite` | `6df18991944b`          | none          |
| `json_parser`  | `gemini-3.5-flash-lite` | `e7fc8bdbc711`          | none          |
