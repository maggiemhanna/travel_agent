# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Step 3: Find failure clusters with GEAP loss analysis (generate_loss_clusters)."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from google.genai import types as genai_types
import pandas as pd
from tabulate import tabulate
import vertexai
from vertexai import types as vertex_types

from app.agent import APP_NAME
from app.app_utils.logging import format_table_for_logs, setup_logging
from tests.eval.scripts.run_evaluation import (
    DEFAULT_RESULTS_DIR,
    RESULTS_FILENAME,
    TRACES_FILENAME,
    build_agent_info,
)

logger = setup_logging(name=__name__)

LOSS_CLUSTERS_JSON_FILENAME = "loss_clusters.json"
LOSS_CLUSTERS_MD_FILENAME = "loss_clusters.md"

SUPPORTED_LOSS_METRICS = {
    "MULTI_TURN_TASK_SUCCESS": "multi_turn_task_success_v1",
    "multi_turn_task_success_v1": "multi_turn_task_success_v1",
    "MULTI_TURN_TOOL_USE_QUALITY": "multi_turn_tool_use_quality_v1",
    "multi_turn_tool_use_quality_v1": "multi_turn_tool_use_quality_v1",
}


def resolve_run_directory(
    run_arg: Optional[str],
    results_dir: str = DEFAULT_RESULTS_DIR,
) -> str:
    """Resolves a run directory by exact path, run_id, run_name suffix, or latest timestamped folder."""
    if run_arg:
        if os.path.isdir(run_arg):
            return os.path.abspath(run_arg)
        candidate = os.path.join(results_dir, run_arg)
        if os.path.isdir(candidate):
            return os.path.abspath(candidate)

        if os.path.isdir(results_dir):
            matches = sorted(
                [
                    d
                    for d in os.listdir(results_dir)
                    if os.path.isdir(os.path.join(results_dir, d))
                    and (d == run_arg or d.endswith(f"_{run_arg}"))
                ],
                reverse=True,
            )
            if matches:
                return os.path.abspath(os.path.join(results_dir, matches[0]))

        raise FileNotFoundError(
            f"Could not find evaluation run matching '{run_arg}' in {results_dir}"
        )

    if not os.path.isdir(results_dir):
        raise FileNotFoundError(f"Results directory does not exist: {results_dir}")

    subdirs = sorted(
        [
            os.path.join(results_dir, d)
            for d in os.listdir(results_dir)
            if os.path.isdir(os.path.join(results_dir, d))
            and os.path.isfile(os.path.join(results_dir, d, RESULTS_FILENAME))
        ],
        key=lambda p: os.path.basename(p),
        reverse=True,
    )
    if not subdirs:
        raise FileNotFoundError(f"No evaluation runs found in {results_dir}")

    return os.path.abspath(subdirs[0])


def reconstruct_evaluation_result(
    report: Dict[str, Any],
    traced_records: List[Dict[str, Any]],
    candidate_name: str = APP_NAME,
) -> vertex_types.EvaluationResult:
    """Reconstructs a Vertex AI EvaluationResult object from saved eval_results.json and traces."""
    for rec in traced_records:
        for turn in (rec.get("agent_data") or {}).get("turns") or []:
            for ev in turn.get("events") or []:
                if ev.get("author") != "user" and isinstance(ev.get("content"), dict):
                    ev["content"]["role"] = "model"

    eval_df = pd.DataFrame(traced_records)
    eval_dataset = vertex_types.EvaluationDataset(
        eval_dataset_df=eval_df,
        candidate_name=candidate_name,
    )

    eval_case_results: List[vertex_types.EvalCaseResult] = []
    for case_dict in report.get("eval_case_results") or []:
        idx = int(case_dict.get("eval_case_index", 0))
        raw_metrics = case_dict.get("metric_results") or {}

        sdk_metric_results: Dict[str, Any] = {}
        for m_name, m_payload in raw_metrics.items():
            if not isinstance(m_payload, dict):
                continue
            sdk_metric_results[m_name] = (
                vertex_types.common.EvalCaseMetricResult.model_validate(m_payload)
            )

        resp_cand = vertex_types.common.ResponseCandidateResult(
            response_index=0,
            metric_results=sdk_metric_results,
        )
        eval_case_results.append(
            vertex_types.common.EvalCaseResult(
                eval_case_index=idx,
                response_candidate_results=[resp_cand],
            )
        )

    summary_metrics: List[vertex_types.common.AggregatedMetricResult] = []
    for agg_dict in report.get("summary_metrics") or []:
        summary_metrics.append(
            vertex_types.common.AggregatedMetricResult(
                metric_name=agg_dict.get("metric_name"),
                mean_score=agg_dict.get("mean_score"),
                stdev_score=agg_dict.get("stdev_score"),
                pass_rate=agg_dict.get("pass_rate"),
                num_cases_total=agg_dict.get("num_cases_total"),
                num_cases_valid=agg_dict.get("num_cases_valid"),
                num_cases_error=agg_dict.get("num_cases_error"),
            )
        )

    metadata = vertex_types.common.EvaluationRunMetadata(
        candidate_names=[candidate_name],
        dataset_name=report.get("eval_set_id", "conversational_synthetic"),
    )

    return vertex_types.EvaluationResult(
        eval_case_results=eval_case_results,
        summary_metrics=summary_metrics,
        evaluation_dataset=[eval_dataset],
        metadata=metadata,
        agent_info=build_agent_info(),
    )


def evaluate_missing_loss_metric(
    eval_result: vertex_types.EvaluationResult,
    traced_records: List[Dict[str, Any]],
    metric_spec_name: str,
    project_id: Optional[str],
    eval_location: str = "us-central1",
    candidate_name: str = APP_NAME,
) -> vertex_types.EvaluationResult:
    """Evaluates a predefined loss-analysis metric on existing traces if not already in eval_results.json."""
    rubric_metric = (
        vertex_types.RubricMetric.MULTI_TURN_TOOL_USE_QUALITY
        if metric_spec_name == "multi_turn_tool_use_quality_v1"
        else vertex_types.RubricMetric.MULTI_TURN_TASK_SUCCESS
    )
    logger.info(
        f"Metric '{metric_spec_name}' is not in saved eval_results.json; "
        f"evaluating {rubric_metric} on saved traces (location={eval_location})..."
    )
    eval_client = vertexai.Client(
        project=project_id,
        location=eval_location,
        http_options=genai_types.HttpOptions(timeout=180_000),
    )
    eval_df = pd.DataFrame(traced_records)
    eval_dataset = vertex_types.EvaluationDataset(
        eval_dataset_df=eval_df,
        candidate_name=candidate_name,
    )
    new_eval_res = eval_client.evals.evaluate(
        dataset=eval_dataset,
        metrics=[rubric_metric],
        agent_info=eval_result.agent_info or build_agent_info(),
        config=vertex_types.EvaluateMethodConfig(evaluation_service_qps=5.0),
    )

    # Merge new metric results into existing eval_result
    for idx, case_res in enumerate(eval_result.eval_case_results or []):
        if idx < len(new_eval_res.eval_case_results or []):
            new_cands = new_eval_res.eval_case_results[idx].response_candidate_results or []
            old_cands = case_res.response_candidate_results or []
            if new_cands and old_cands:
                if old_cands[0].metric_results is None:
                    old_cands[0].metric_results = {}
                for k, v in (new_cands[0].metric_results or {}).items():
                    old_cands[0].metric_results[k] = v

    return eval_result


def count_failing_cases_for_metric(
    eval_result: vertex_types.EvaluationResult,
    metric_spec_name: str,
) -> int:
    """Counts how many cases have score < 1.0 or failed rubric verdicts for a given metric."""
    failing = 0
    for case_res in eval_result.eval_case_results or []:
        for cand_res in case_res.response_candidate_results or []:
            m_res = (cand_res.metric_results or {}).get(metric_spec_name)
            if not m_res:
                continue
            has_failed_rubric = any(
                v.verdict is False for v in (m_res.rubric_verdicts or [])
            )
            if has_failed_rubric or (m_res.score is not None and m_res.score < 1.0):
                failing += 1
    return failing


def serialize_loss_clusters(
    run_id: str,
    run_name: str,
    responses_by_metric: Dict[str, vertex_types.GenerateLossClustersResponse],
    failing_counts_by_metric: Dict[str, int],
    report: Dict[str, Any],
) -> Dict[str, Any]:
    """Serializes GenerateLossClustersResponse objects into a clean JSON dictionary."""
    case_by_prompt: Dict[str, Dict[str, Any]] = {}
    rubric_lookup: Dict[str, Dict[str, Any]] = {}
    for c in report.get("eval_case_results") or []:
        prompt_str = (c.get("prompt") or "").strip()
        if prompt_str:
            case_by_prompt[prompt_str] = c
        for m_name, m_res in (c.get("metric_results") or {}).items():
            for rv in m_res.get("rubric_verdicts") or []:
                rid = (rv.get("evaluated_rubric") or {}).get("rubric_id")
                desc = (
                    ((rv.get("evaluated_rubric") or {}).get("content") or {})
                    .get("property", {})
                    .get("description")
                )
                if rid:
                    rubric_lookup[rid] = {
                        "eval_id": c.get("eval_id"),
                        "eval_case_index": c.get("eval_case_index"),
                        "prompt": c.get("prompt"),
                        "agent_trajectory": c.get("agent_trajectory"),
                        "rubric_description": desc,
                        "judge_reasoning": rv.get("reasoning"),
                    }

    metrics_payload: Dict[str, Any] = {}
    for metric_name, loss_resp in responses_by_metric.items():
        clusters_list: List[Dict[str, Any]] = []
        for res_item in loss_resp.results or []:
            for cluster in res_item.clusters or []:
                tax = cluster.taxonomy_entry
                examples_list: List[Dict[str, Any]] = []
                for ex in cluster.examples or []:
                    failed_rubrics_list: List[Dict[str, Any]] = []
                    matched_case_info: Optional[Dict[str, Any]] = None
                    for fr in ex.failed_rubrics or []:
                        rid = fr.rubric_id or ""
                        r_meta = rubric_lookup.get(rid, {})
                        if r_meta and matched_case_info is None:
                            matched_case_info = {
                                "eval_case_index": r_meta.get("eval_case_index"),
                                "eval_id": r_meta.get("eval_id"),
                                "prompt": r_meta.get("prompt"),
                                "agent_trajectory": r_meta.get("agent_trajectory"),
                            }
                        failed_rubrics_list.append(
                            {
                                "rubric_id": rid,
                                "rubric_description": r_meta.get("rubric_description"),
                                "judge_reasoning": r_meta.get("judge_reasoning"),
                                "classification_rationale": fr.classification_rationale,
                            }
                        )

                    scenario_preview = (ex.evaluation_result or {}).get(
                        "scenario_preview"
                    )
                    examples_list.append(
                        {
                            "case_info": matched_case_info,
                            "scenario_preview": scenario_preview,
                            "failed_rubrics": failed_rubrics_list,
                        }
                    )

                clusters_list.append(
                    {
                        "cluster_id": cluster.cluster_id,
                        "item_count": cluster.item_count,
                        "l1_category": tax.l1_category if tax else None,
                        "l2_category": tax.l2_category if tax else None,
                        "description": tax.description if tax else None,
                        "examples": examples_list,
                    }
                )

        metrics_payload[metric_name] = {
            "failing_cases_count": failing_counts_by_metric.get(metric_name, 0),
            "num_clusters": len(clusters_list),
            "analysis_time": loss_resp.analysis_time,
            "clusters": clusters_list,
        }

    return {
        "run_id": run_id,
        "run_name": run_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics_payload,
    }


def log_and_save_loss_report(
    payload: Dict[str, Any],
    md_output_path: str,
) -> None:
    """Logs a summary table of loss clusters and writes a detailed Markdown report."""
    run_id = payload.get("run_id", "unknown")
    md_lines: List[str] = [
        f"# GEAP Loss Cluster Analysis — `{run_id}`\n",
        f"- **Run Name**: `{payload.get('run_name')}`",
        f"- **Generated At (UTC)**: `{payload.get('timestamp')}`\n",
    ]

    for metric_name, m_data in (payload.get("metrics") or {}).items():
        failing_cnt = m_data.get("failing_cases_count", 0)
        clusters = m_data.get("clusters") or []
        md_lines.append(f"## Metric: `{metric_name}`")
        md_lines.append(
            f"- **Failing Cases Analyzed**: `{failing_cnt}`\n"
            f"- **Loss Clusters Identified**: `{len(clusters)}`\n"
        )

        if not clusters:
            msg = f"No loss clusters generated for '{metric_name}' (failing cases={failing_cnt})."
            logger.info(msg)
            md_lines.append(f"_{msg}_\n")
            continue

        rows = []
        for c in clusters:
            rows.append(
                [
                    c.get("cluster_id") or "-",
                    c.get("l1_category") or "-",
                    c.get("l2_category") or "-",
                    c.get("item_count") or 0,
                    (c.get("description") or "")[:90],
                ]
            )

        headers = [
            "Cluster ID",
            "L1 Category",
            "L2 Category",
            "Items",
            "Description",
        ]
        logger.info(
            format_table_for_logs(
                title=f"LOSS CLUSTERS — {metric_name} ({run_id})",
                rows=rows,
                headers=headers,
                width=115,
            )
        )

        md_lines.append("### Cluster Summary Table\n")
        md_lines.append(tabulate(rows, headers=headers, tablefmt="github"))
        md_lines.append("\n### Detailed Cluster Breakdown\n")

        for idx, c in enumerate(clusters, start=1):
            l1 = c.get("l1_category") or "Uncategorized"
            l2 = c.get("l2_category") or "Uncategorized"
            cnt = c.get("item_count") or 0
            desc = c.get("description") or ""
            md_lines.append(
                f"#### {idx}. `{l1}` → `{l2}` ({cnt} item(s), ID: `{c.get('cluster_id')}`)\n"
            )
            md_lines.append(f"> {desc}\n")

            for ex_idx, ex in enumerate(c.get("examples") or [], start=1):
                c_info = ex.get("case_info") or {}
                if c_info.get("eval_id"):
                    traj_str = " -> ".join(c_info.get("agent_trajectory") or [])
                    md_lines.append(
                        f"- **Example {ex_idx}** — Case `{c_info.get('eval_case_index')}` "
                        f"(`{c_info.get('eval_id')}`, trajectory: `{traj_str}`):"
                    )
                    md_lines.append(f"  - **User Prompt**: _{c_info.get('prompt')}_")
                elif ex.get("scenario_preview"):
                    md_lines.append(
                        f"- **Example {ex_idx}**: _{ex.get('scenario_preview')}_"
                    )

                for fr in ex.get("failed_rubrics") or []:
                    r_desc = fr.get("rubric_description") or fr.get("rubric_id")
                    rationale = fr.get("classification_rationale") or ""
                    reasoning = fr.get("judge_reasoning") or ""
                    md_lines.append(f"  - **Failed Rubric**: {r_desc}")
                    if reasoning:
                        md_lines.append(f"    - **Judge Reasoning**: {reasoning}")
                    if rationale:
                        md_lines.append(f"    - **Cluster Rationale**: {rationale}")
            md_lines.append("")

    with open(md_output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    logger.info(f"Saved Markdown loss analysis report to {md_output_path}")


def run_loss_analysis(
    run_arg: Optional[str] = "filter_smart_prompt_v2",
    results_dir: str = DEFAULT_RESULTS_DIR,
    metrics: Optional[List[str]] = None,
    evaluate_missing: bool = False,
    max_top_cluster_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Runs GEAP generate_loss_clusters on an existing evaluation run directory."""
    load_dotenv()
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")

    run_dir = resolve_run_directory(run_arg=run_arg, results_dir=results_dir)
    results_path = os.path.join(run_dir, RESULTS_FILENAME)
    traces_path = os.path.join(run_dir, TRACES_FILENAME)

    if not os.path.isfile(results_path):
        raise FileNotFoundError(f"Missing {RESULTS_FILENAME} in {run_dir}")
    if not os.path.isfile(traces_path):
        raise FileNotFoundError(f"Missing {TRACES_FILENAME} in {run_dir}")

    with open(results_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    with open(traces_path, "r", encoding="utf-8") as f:
        traced_records = json.load(f)

    run_id = report.get("run_id") or os.path.basename(run_dir)
    run_name = report.get("run_name") or run_id
    logger.info(f"Loaded evaluation run '{run_id}' ({len(traced_records)} cases) from {run_dir}")

    eval_result = reconstruct_evaluation_result(
        report=report,
        traced_records=traced_records,
        candidate_name=APP_NAME,
    )

    requested_metrics = metrics or ["MULTI_TURN_TASK_SUCCESS"]
    resolved_metrics: List[str] = []
    for m in requested_metrics:
        spec = SUPPORTED_LOSS_METRICS.get(m, m)
        if spec not in resolved_metrics:
            resolved_metrics.append(spec)

    # Check which metrics are already in eval_result
    existing_metrics = set()
    for c in eval_result.eval_case_results or []:
        for rc in c.response_candidate_results or []:
            existing_metrics.update((rc.metric_results or {}).keys())

    # Note: generate_loss_clusters API is only available in the 'global' region
    loss_client = vertexai.Client(
        project=project_id,
        location="global",
        http_options=genai_types.HttpOptions(timeout=180_000),
    )

    responses_by_metric: Dict[str, vertex_types.GenerateLossClustersResponse] = {}
    failing_counts_by_metric: Dict[str, int] = {}

    for metric_spec in resolved_metrics:
        if metric_spec not in existing_metrics:
            if evaluate_missing:
                eval_result = evaluate_missing_loss_metric(
                    eval_result=eval_result,
                    traced_records=traced_records,
                    metric_spec_name=metric_spec,
                    project_id=project_id,
                    candidate_name=APP_NAME,
                )
            else:
                logger.warning(
                    f"Skipping '{metric_spec}' because it is not present in {results_path}. "
                    f"Pass --evaluate-missing to score it on the saved traces first."
                )
                continue

        failing_count = count_failing_cases_for_metric(eval_result, metric_spec)
        failing_counts_by_metric[metric_spec] = failing_count
        logger.info(
            f"Running generate_loss_clusters for metric='{metric_spec}' "
            f"(candidate='{APP_NAME}', failing_cases={failing_count}, location='global')..."
        )

        loss_cfg = vertex_types.LossAnalysisConfig(
            metric=metric_spec,
            candidate=APP_NAME,
            max_top_cluster_count=max_top_cluster_count,
        )
        loss_response = loss_client.evals.generate_loss_clusters(
            eval_result=eval_result,
            metric=metric_spec,
            candidate=APP_NAME,
            config=loss_cfg,
        )
        responses_by_metric[metric_spec] = loss_response

    payload = serialize_loss_clusters(
        run_id=run_id,
        run_name=run_name,
        responses_by_metric=responses_by_metric,
        failing_counts_by_metric=failing_counts_by_metric,
        report=report,
    )

    json_output_path = os.path.join(run_dir, LOSS_CLUSTERS_JSON_FILENAME)
    md_output_path = os.path.join(run_dir, LOSS_CLUSTERS_MD_FILENAME)

    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved loss cluster JSON results to {json_output_path}")

    log_and_save_loss_report(payload=payload, md_output_path=md_output_path)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Step 3: Find failure clusters with GEAP loss analysis (generate_loss_clusters)."
    )
    parser.add_argument(
        "--run",
        default="filter_smart_prompt_v2",
        help="Run name, run ID, or path to analyze (default: 'filter_smart_prompt_v2')",
    )
    parser.add_argument(
        "--results-dir",
        default=DEFAULT_RESULTS_DIR,
        help="Base results directory containing evaluation run folders",
    )
    parser.add_argument(
        "--metrics",
        nargs="+",
        default=["MULTI_TURN_TASK_SUCCESS"],
        help=(
            "Predefined metric(s) to cluster failures for: "
            "MULTI_TURN_TASK_SUCCESS and/or MULTI_TURN_TOOL_USE_QUALITY"
        ),
    )
    parser.add_argument(
        "--evaluate-missing",
        action="store_true",
        help="If a requested metric (e.g. MULTI_TURN_TOOL_USE_QUALITY) was not in eval_results.json, evaluate it on saved traces first",
    )
    parser.add_argument(
        "--max-clusters",
        type=int,
        default=None,
        help="Optional maximum number of top loss clusters to return",
    )
    args = parser.parse_args()

    run_loss_analysis(
        run_arg=args.run,
        results_dir=args.results_dir,
        metrics=args.metrics,
        evaluate_missing=args.evaluate_missing,
        max_top_cluster_count=args.max_clusters,
    )


if __name__ == "__main__":
    main()
