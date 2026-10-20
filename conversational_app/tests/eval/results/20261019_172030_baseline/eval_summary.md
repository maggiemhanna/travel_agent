# GEAP EVALUATION SUMMARY — 20261019_172030_baseline (5 EvalCases)

## Run Metadata

- **Run ID**: `20261019_172030_baseline`
- **Run Name**: `baseline`
- **Description**: Initial 5-case validation baseline
- **Baseline Reference**: `Pinned as active baseline`
- **Eval Set ID**: `conversational_synthetic`
- **Timestamp (UTC)**: `2026-10-19T17:20:30.561890+00:00`
- **Cases Evaluated**: `5`
- **Git Revision**: `093ba64` (branch: `evaluation`, dirty: `True`)

## Aggregated Metric Scores

| Metric Name                      | Mean Score   | Pass Rate   | Std Dev   | Threshold   | Valid/Total   | Status   |
|----------------------------------|--------------|-------------|-----------|-------------|---------------|----------|
| multi_turn_task_success_v1       | 0.800        | 80.0%       | 0.447     | >= 0.80     | 5/5           | PASS     |
| multi_turn_trajectory_quality_v1 | 0.821        | 60.0%       | 0.325     | >= 0.80     | 5/5           | PASS     |
| multi_turn_tool_use_quality_v1   | 0.400        | 40.0%       | 0.548     | >= 0.80     | 5/5           | FAIL     |
| grounding_v1                     | 0.400        | 40.0%       | 0.548     | >= 0.80     | 5/5           | FAIL     |
| instruction_following_v1         | 0.760        | 60.0%       | 0.434     | >= 0.80     | 5/5           | FAIL     |
| coherence                        | 1.000        | 100.0%      | 0.000     | >= 0.80     | 5/5           | PASS     |
| schema_and_contract_valid        | 1.000        | 100.0%      | 0.000     | >= 0.95     | 5/5           | PASS     |
| conversation_plan_alignment      | 1.000        | 100.0%      | 0.000     | >= 0.80     | 5/5           | PASS     |
| latency_seconds                  | 4.617s       | 100.0%      | 2.029s    | <= 15.00s   | 5/5           | PASS     |

## Agent Configuration Snapshot

| Sub-Agent            | Model                   | Prompt Hash (SHA-256)   | Tools         |
|----------------------|-------------------------|-------------------------|---------------|
| `engage`             | `gemini-3.5-flash-lite` | `66d7c3a65f42`          | none          |
| `filter_agent`       | `gemini-3.5-flash-lite` | `1817f7a21c23`          | none          |
| `filter_smart_agent` | `gemini-3.5-flash-lite` | `ef1a2261eb0b`          | google_search |
| `inspiration`        | `gemini-3.5-flash-lite` | `6df18991944b`          | none          |
| `json_parser_agent`  | `gemini-3.5-flash-lite` | `e7fc8bdbc711`          | none          |
