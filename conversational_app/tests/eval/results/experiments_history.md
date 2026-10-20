# GEAP Evaluation Experiments History

Cumulative leaderboard of evaluation runs across model, prompt, and architecture changes.

| Run ID                     | Run Name   | Baseline   |   Cases | Git        |   multi_turn_task_success_v1 |   multi_turn_trajectory_quality_v1 |   tool_use_quality |   grounding_v1 |   instruction_following_v1 |   coherence |   schema_and_contract_valid |   conversation_plan_alignment | latency_seconds   | Description                        |
|----------------------------|------------|------------|---------|------------|------------------------------|------------------------------------|--------------------|----------------|----------------------------|-------------|-----------------------------|-------------------------------|-------------------|------------------------------------|
| `20261019_172030_baseline` | `baseline` | Yes        |       5 | `093ba64*` |                          0.8 |                              0.821 |                              0.4 |            0.4 |                       0.76 |           1 |                           1 |                             1 | 4.617s            | Initial 5-case validation baseline |
| `20261019_181638_baseline_v2` | `baseline_v2` | Yes | 5 | `093ba64*` | 0.800 | 0.842 | 0.800 | 0.200 | 0.833 | 1.000 | 1.000 | 1.000 | 4.853s | 5-case validation with standardized sub-agent names and Option A tool_use_quality + google_search grounding bridge |
