# GEAP Evaluation Experiments History

Cumulative leaderboard of evaluation runs across model, prompt, caching, and architecture changes. Each column represents a single evaluation Run ID.

| Run ID                                   | `20261124_122326_baseline_all_3_5_flash_lite`                                                                                       |
|------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| **Run Name**                             | `baseline_all_3_5_flash_lite`                                                                                                       |
| **Description**                          | Baseline: all sub-agents on gemini-3.5-flash-lite (thinking budget 0 on engage/filter/inspiration/json_parser, 512 on filter_smart) |
| **Baseline**                             | Yes                                                                                                                                 |
| **Cases**                                | 50                                                                                                                                  |
| **Git**                                  | `eee59b7*`                                                                                                                          |
| **Model (`engage`)**                     | `gemini-3.5-flash-lite`                                                                                                             |
| **Model (`filter`)**                     | `gemini-3.5-flash-lite`                                                                                                             |
| **Model (`filter_smart`)**               | `gemini-3.5-flash-lite`                                                                                                             |
| **Model (`inspiration`)**                | `gemini-3.5-flash-lite`                                                                                                             |
| **Model (`json_parser`)**                | `gemini-3.5-flash-lite`                                                                                                             |
| **Task Success Rate**                    | 0.872                                                                                                                               |
| **Trajectory Quality**                   | 0.966                                                                                                                               |
| **Tool Use Quality**                     | 1.000                                                                                                                               |
| **Response Coherence**                   | 0.920                                                                                                                               |
| **Schema & Contract Validity**           | 1.000                                                                                                                               |
| **Conversation Plan Alignment**          | 0.840                                                                                                                               |
| **Latency (in seconds)**                 | 3.201s                                                                                                                              |
| **Total Cost per 1k Requests (USD)**     | 6.303 USD/1k                                                                                                                        |
| **LLM Token Cost per 1k Requests (USD)** | 2.383 USD/1k                                                                                                                        |
| **Total Billable Tokens (avg/req)**      | 3946.360 tok                                                                                                                        |
