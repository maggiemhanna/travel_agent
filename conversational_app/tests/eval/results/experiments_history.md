# GEAP Evaluation Experiments History

Cumulative leaderboard of evaluation runs across model, prompt, and architecture changes.

| Run ID                     | Run Name   | Baseline   |   Cases | Git        |   multi_turn_task_success_v1 |   multi_turn_trajectory_quality_v1 |   tool_use_quality |   coherence |   schema_and_contract_valid |   conversation_plan_alignment | latency_seconds   | Description                      |
|----------------------------|------------|------------|---------|------------|------------------------------|------------------------------------|--------------------|-------------|-----------------------------|-------------------------------|-------------------|----------------------------------|
| `20261020_093127_baseline` | `baseline` | Yes        |      50 | `c4cff37*` |                         0.84 |                              0.929 |                0.9 |         0.9 |                           1 |                          0.86 | 2.593s            | Full 50-case baseline evaluation |
| `20261020_094313_gemini_3_1_pro` | `gemini_3_1_pro` | No | 50 | `b23b4f4*` | 0.853 | 0.954 | 0.960 | 1.000 | 1.000 | 0.900 | 19.792s | Upgrade all 5 sub-agents from gemini-3.5-flash-lite to gemini-3.1-pro-preview |
