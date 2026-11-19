# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""Unit tests for eval-only AI cost estimation, caching projections, prompt-size guardrails, and raw telemetry."""

from __future__ import annotations

import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from google.adk.evaluation.conversation_scenarios import ConversationScenario
from google.adk.evaluation.eval_case import EvalCase, SessionInput
from google.adk.models.cache_metadata import CacheMetadata
from google.adk.models.llm_response import LlmResponse
from google.genai import types as genai_types
import pytest

from app.app_utils.telemetry_plugin import ExecutionTelemetryPlugin
from tests.eval.metrics.cost_estimator import (
    aggregate_invocation_cost,
    compute_analytical_cache_projections,
    compute_step_cost_from_counts,
    extract_step_usage_and_cost,
    load_pricing_catalog,
    resolve_model_pricing,
)
from tests.eval.metrics.custom_metrics import (
    evaluate_cost_per_1k_requests_usd,
    evaluate_llm_token_cost_per_1k_usd,
    evaluate_total_billable_tokens,
)
from tests.eval.scripts.run_evaluation import (
    DEFAULT_EVAL_CONFIG_PATH,
    build_agent_info,
    run_evaluation,
    run_single_case_inference,
)


def test_pricing_catalog_and_model_resolution() -> None:
    """Verify Standard PayGo catalog rates and exact/prefix/fallback model resolution."""
    catalog = load_pricing_catalog()
    assert catalog["billing_tier"] == "vertex_ai_standard_paygo"
    assert catalog["grounding_defaults"]["billing_mode"] == "per_search_query"
    assert catalog["grounding_defaults"]["price_per_unit_usd"] == pytest.approx(0.014)

    # Exact & publisher-prefixed versioned match (must match flash-lite, not flash)
    key, spec, fb = resolve_model_pricing(
        "publishers/google/models/gemini-3.5-flash-lite-001", catalog
    )
    assert key == "gemini-3.5-flash-lite"
    assert fb is False
    assert spec["input_per_1m_usd"] == pytest.approx(0.30)
    assert spec["output_per_1m_usd"] == pytest.approx(2.50)

    # Unknown future model falls back safely without crashing
    fb_key, _, fb_used = resolve_model_pricing("gemini-9.9-experimental", catalog)
    assert fb_key == catalog["default_model"]
    assert fb_used is True


def test_step_cost_accounting_tokens_thinking_caching_and_grounding() -> None:
    """Verify cached-token subtraction, thinking output billing, >200k tiering, and Google Search SKU modes."""
    # 1. Gemini 3.5 Flash-Lite with context cache + thinking + 2 Google Search queries:
    # prompt=2000 (includes 1500 cached -> 500 uncached) + 100 tool_use_prompt = 600 uncached input @ $0.30/1M = $0.00018
    # cached=1500 @ $0.03/1M = $0.000045 (savings vs $0.30/1M = $0.000405)
    # candidates=200 + thoughts=300 = 500 billable output @ $2.50/1M = $0.00125
    # llm_token_cost = 0.00018 + 0.000045 + 0.00125 = $0.001475
    # 2 search queries @ $0.014/query = $0.028
    # total = $0.029475 ($29.475 / 1k reqs)
    resp = LlmResponse(
        model_version="publishers/google/models/gemini-3.5-flash-lite",
        partial=False,
        usage_metadata=genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=2000,
            cached_content_token_count=1500,
            tool_use_prompt_token_count=100,
            candidates_token_count=200,
            thoughts_token_count=300,
        ),
        grounding_metadata=genai_types.GroundingMetadata(
            web_search_queries=[
                "Air France AF006 WiFi speed",
                "Delta DL265 WiFi reliability",
            ]
        ),
        cache_metadata=CacheMetadata(
            cache_name="projects/p/locations/global/cachedContents/c1",
            expire_time=9999999999.0,
            fingerprint="abcdef123456",
            invocations_used=3,
            contents_count=1,
            created_at=1700000000.0,
        ),
    )

    step = extract_step_usage_and_cost(
        author="filter_smart",
        llm_response=resp,
        configured_model="gemini-3.5-flash-lite",
        latency_seconds=1.85,
    )
    assert step["uncached_input_tokens"] == 500
    assert step["billable_uncached_input_tokens"] == 600
    assert step["cached_input_tokens"] == 1500
    assert step["billable_output_tokens"] == 500
    assert step["total_tokens"] == 2600
    assert step["context_cache_hit"] is True
    assert step["search_queries_count"] == 2
    assert step["llm_token_cost_usd"] == pytest.approx(0.001475)
    assert step["search_grounding_cost_usd"] == pytest.approx(0.028)
    assert step["total_cost_usd"] == pytest.approx(0.029475)
    assert step["cost_per_1k_requests_usd"] == pytest.approx(29.475)
    assert step["context_cache_savings_usd"] == pytest.approx(0.000405)

    # 2. Alternative per_grounded_request SKU mode bills 1 unit regardless of query count
    per_req_catalog = copy.deepcopy(load_pricing_catalog())
    per_req_catalog["models"]["gemini-2.5-flash"]["google_search_grounding"] = {
        "billing_mode": "per_grounded_request",
        "price_per_unit_usd": 0.035,
    }
    req_step = compute_step_cost_from_counts(
        author="filter_smart",
        resolved_model="gemini-2.5-flash",
        prompt_tokens=1000,
        candidates_output_tokens=100,
        web_search_queries=["q1", "q2", "q3"],
        catalog=per_req_catalog,
    )
    assert req_step["billable_search_units"] == 1
    assert req_step["search_grounding_cost_usd"] == pytest.approx(0.035)

    # 3. Response cache hit short-circuit -> $0 billed cost, avoided cost preserved
    cached_resp = LlmResponse(
        partial=False,
        usage_metadata=resp.usage_metadata,
        grounding_metadata=resp.grounding_metadata,
        custom_metadata={"response_cache_hit": True},
    )
    hit_step = extract_step_usage_and_cost(
        author="filter_smart",
        llm_response=cached_resp,
        configured_model="gemini-3.5-flash-lite",
    )
    assert hit_step["response_cache_hit"] is True
    assert hit_step["total_cost_usd"] == 0.0
    assert hit_step["search_grounding_cost_usd"] == 0.0
    assert hit_step["response_cache_avoided_cost_usd"] == pytest.approx(0.029475)

    # 4. Long-context tier (>200k tokens) on gemini-3.1-pro-preview ($4.00/1M in, $18.00/1M out)
    long_step = compute_step_cost_from_counts(
        author="filter_smart",
        resolved_model="gemini-3.1-pro-preview",
        prompt_tokens=250_000,
        candidates_output_tokens=1_000,
    )
    assert long_step["is_long_context_tier"] is True
    assert long_step["total_cost_usd"] == pytest.approx(
        0.25 * 4.00 + 0.001 * 18.00
    )


def test_telemetry_plugin_logs_raw_cached_and_thoughts_tokens_without_cost_state() -> None:
    """Verify ExecutionTelemetryPlugin stays lightweight (raw cached & thoughts tokens only, no retained cost buffer)."""
    plugin = ExecutionTelemetryPlugin()
    assert not hasattr(plugin, "_completed_runs")

    async def _exercise():
        inv_id = "inv-raw-tokens-001"
        inv_ctx = SimpleNamespace(invocation_id=inv_id)
        cb_ctx = SimpleNamespace(invocation_id=inv_id, agent_name="filter_smart")
        await plugin.before_run_callback(invocation_context=inv_ctx)
        await plugin.before_agent_callback(
            agent=SimpleNamespace(name="filter_smart"), callback_context=cb_ctx
        )
        await plugin.after_model_callback(
            callback_context=cb_ctx,
            llm_response=LlmResponse(
                partial=False,
                usage_metadata=genai_types.GenerateContentResponseUsageMetadata(
                    prompt_token_count=1800,
                    cached_content_token_count=1200,
                    candidates_token_count=220,
                    thoughts_token_count=140,
                ),
                grounding_metadata=genai_types.GroundingMetadata(
                    web_search_queries=["Air France WiFi speed"]
                ),
            ),
        )

        run_state = plugin._runs[inv_id]
        assert run_state["in_tokens"] == 1800
        assert run_state["out_tokens"] == 220
        assert run_state["cached_tokens"] == 1200
        assert run_state["thoughts_tokens"] == 140
        assert run_state["rows"][0][4] == "Air France WiFi speed"
        assert run_state["rows"][0][5] == 1200
        assert run_state["rows"][0][6] == 140

        await plugin.after_run_callback(invocation_context=inv_ctx)
        assert inv_id not in plugin._runs

    asyncio.run(_exercise())


def test_custom_cost_metrics_and_analytical_cache_projections() -> None:
    """Verify deterministic GEAP custom metrics (dict & JSON string inputs) and caching sensitivity math."""
    engage_step = compute_step_cost_from_counts(
        author="engage",
        resolved_model="gemini-3.5-flash-lite",
        prompt_tokens=1200,  # Below 4096 Gemini 3 ContextCache min
        candidates_output_tokens=40,
        thoughts_tokens=60,
    )
    smart_step = compute_step_cost_from_counts(
        author="filter_smart",
        resolved_model="gemini-3.5-flash-lite",
        prompt_tokens=5000,  # Above 4096 Gemini 3 ContextCache min!
        candidates_output_tokens=400,
        thoughts_tokens=200,
        web_search_queries=["Air France WiFi"],
    )
    summary = aggregate_invocation_cost([engage_step, smart_step])

    # Test with JSON-serialized columns (matching Vertex AI EvaluationDataset DataFrame coercion)
    instance_serialized = {
        "cost_summary": json.dumps(summary),
        "sub_agent_usages": json.dumps([engage_step, smart_step]),
    }
    m_total = evaluate_cost_per_1k_requests_usd(instance_serialized)
    m_tok = evaluate_llm_token_cost_per_1k_usd(instance_serialized)
    m_cnt = evaluate_total_billable_tokens(instance_serialized)

    # Engage: 1200*0.30/1M ($0.00036) + 100*2.50/1M ($0.00025) = $0.00061
    # Smart:  5000*0.30/1M ($0.00150) + 600*2.50/1M ($0.00150) + 1*$0.014 = $0.01700
    # Total = $0.01761 -> $17.61 / 1k reqs; Token-only = $3.61 / 1k reqs; Total tokens = 6900
    assert m_total["score"] == pytest.approx(17.61)
    assert m_tok["score"] == pytest.approx(3.61)
    assert m_cnt["score"] == pytest.approx(6900.0)

    # Legacy traces without token/usage capture must return score=None (N/A), not 0.0 PASS
    legacy_instance = {"sub_agent_usages": [], "cost_summary": aggregate_invocation_cost([])}
    assert evaluate_cost_per_1k_requests_usd(legacy_instance)["score"] is None
    assert evaluate_llm_token_cost_per_1k_usd(legacy_instance)["score"] is None
    assert evaluate_total_billable_tokens(legacy_instance)["score"] is None

    traced_records = [
        {
            "eval_id": "case-1",
            "latency_seconds": 4.0,
            "sub_agent_usages": [engage_step, smart_step],
            "cost_summary": summary,
        }
    ]
    projections = compute_analytical_cache_projections(
        traced_records=traced_records,
        response_cache_hit_rates=[0.0, 0.5],
        context_cache_hit_rates=[0.0, 1.0],
    )
    resp_50 = projections["response_cache_sensitivity"][1]
    assert resp_50["effective_cost_per_1k_usd"] == pytest.approx(17.61 * 0.5)
    assert resp_50["effective_mean_latency_seconds"] == pytest.approx(2.0)

    # Context cache @ 100%:
    # Theoretical max discount saves 90% of (1200 + 5000) input tokens = 6200 * ($0.27/1M) * 1000 = $1.674 / 1k
    # Threshold-gated (>= 4096 tok) only discounts filter_smart (5000 tok): 5000 * ($0.27/1M) * 1000 = $1.35 / 1k
    ctx_100 = projections["context_cache_prefix_sensitivity"][1]
    assert ctx_100["theoretical_input_savings_per_1k_usd"] == pytest.approx(1.674)
    assert ctx_100["threshold_gated_input_savings_per_1k_usd"] == pytest.approx(1.35)
    assert (
        projections["agent_context_cache_eligibility"]["engage"][
            "eligible_call_rate_pct"
        ]
        == 0.0
    )
    assert (
        projections["agent_context_cache_eligibility"]["filter_smart"][
            "eligible_call_rate_pct"
        ]
        == 100.0
    )


def test_offline_reprice_and_experiments_history_column_expansion(
    tmp_path: Path,
) -> None:
    """Verify --reprice-only + --override-model counterfactual estimation and safe Markdown table expansion."""
    from google.adk.models.google_llm import Gemini

    call_idx = 0

    async def _fake_workflow_llm(self, llm_request, stream=False):
        nonlocal call_idx
        call_idx += 1
        if call_idx == 1:
            body = {
                "agent_response": "Filtering under $785.",
                "agent_decision": "filter",
            }
            in_t, out_t, th_t = 1100, 35, 45
        else:
            body = {
                "agent_response": "Showing flights under $785.",
                "filter_type": "max_price",
                "filter_value": 785,
            }
            in_t, out_t, th_t = 850, 40, 20
        yield LlmResponse(
            model_version="gemini-3.5-flash-lite",
            content=genai_types.Content(
                role="model",
                parts=[genai_types.Part.from_text(text=json.dumps(body))],
            ),
            usage_metadata=genai_types.GenerateContentResponseUsageMetadata(
                prompt_token_count=in_t,
                candidates_token_count=out_t,
                thoughts_token_count=th_t,
            ),
            partial=False,
        )

    eval_case = EvalCase(
        eval_id="unit0001",
        conversation_scenario=ConversationScenario(
            starting_prompt="Flights under $785 please",
            conversation_plan="agent_decision: filter, max_price: 785",
        ),
        session_input=SessionInput(
            app_name="conversational_app",
            user_id="u1",
            state={
                "conversational_history": [],
                "flights_search_input": {
                    "origin": "Paris",
                    "destination": "New York",
                    "departure_date": "2026-05-10",
                    "return_date": "2026-05-20",
                    "passengers": 1,
                },
                "flights_input": [],
            },
        ),
    )

    with patch.object(
        Gemini, "generate_content_async", new=_fake_workflow_llm
    ):
        agent_info = build_agent_info()
        record = asyncio.run(
            run_single_case_inference(
                eval_case=eval_case,
                agents_map=agent_info.agents or {},
                semaphore=asyncio.Semaphore(1),
            )
        )

    assert len(record["sub_agent_usages"]) == 2
    flash_lite_cost_1k = record["cost_summary"]["cost_per_1k_requests_usd"]
    assert flash_lite_cost_1k > 0.0

    # Seed a legacy experiments_history.md (matching existing repo state before cost columns)
    results_dir = tmp_path / "results"
    base_dir = results_dir / "20261118_000001_seed"
    base_dir.mkdir(parents=True)
    (base_dir / "eval_dataset_with_traces.json").write_text(
        json.dumps([record], indent=2), encoding="utf-8"
    )

    history_file = results_dir / "experiments_history.md"
    history_file.write_text(
        "# GEAP Evaluation Experiments History\n\n"
        "Cumulative leaderboard.\n\n"
        "| Run ID | Run Name | Baseline | Cases | Git | schema_and_contract_valid | latency_seconds | Description |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| `20261020_093127_baseline` | `baseline` | Yes | 50 | `c4cff37*` | 1.000 | 2.593s | Legacy baseline |\n",
        encoding="utf-8",
    )

    # 1. Run offline --reprice-only baseline on saved traces ($0 Vertex API calls)
    base_report = run_evaluation(
        eval_config_path=DEFAULT_EVAL_CONFIG_PATH,
        results_dir=str(results_dir),
        run_name="cost_baseline",
        description="Baseline with Standard PayGo cost tracking",
        set_baseline=True,
        reuse_run=str(base_dir),
        reprice_only=True,
    )
    assert base_report["cost_overview"]["cost_per_1k_requests_usd"] == pytest.approx(
        flash_lite_cost_1k
    )
    assert (
        base_report["cost_overview"]["eval_judge_overhead_estimate"][
            "estimated_judge_cost_usd"
        ]
        == 0.0
    )

    # 2. Counterfactual model upgrade: override `filter` -> `gemini-3.1-pro-preview` ($2/$12 vs $0.30/$2.50)
    pro_report = run_evaluation(
        eval_config_path=DEFAULT_EVAL_CONFIG_PATH,
        results_dir=str(results_dir),
        run_name="hybrid_filter_pro",
        description="Counterfactual: upgrade filter to gemini-3.1-pro-preview",
        reuse_run=str(base_dir),
        reprice_only=True,
        model_overrides=["filter=gemini-3.1-pro-preview"],
    )
    pro_cost_1k = pro_report["cost_overview"]["cost_per_1k_requests_usd"]
    assert pro_cost_1k > flash_lite_cost_1k
    cost_metric_item = next(
        m
        for m in pro_report["summary_metrics"]
        if m["metric_name"] == "cost_per_1k_requests_usd"
    )
    assert cost_metric_item["baseline_mean_score"] == pytest.approx(
        flash_lite_cost_1k
    )
    assert cost_metric_item["delta_mean_score"] == pytest.approx(
        pro_cost_1k - flash_lite_cost_1k
    )

    # Verify experiments_history.md has uniform column count across legacy + new rows and Description stays last
    updated_md = history_file.read_text(encoding="utf-8")
    table_lines = [
        ln.strip()
        for ln in updated_md.splitlines()
        if ln.strip().startswith("|")
    ]
    assert len(table_lines) == 5  # header + separator + 1 legacy + 2 new runs
    col_counts = {len(ln.strip("|").split("|")) for ln in table_lines}
    assert len(col_counts) == 1, f"Mismatched Markdown table columns: {updated_md}"
    header_cols = [c.strip() for c in table_lines[0].strip("|").split("|")]
    assert header_cols[-1] == "Description"
    assert "cost_per_1k_requests_usd" in header_cols
    legacy_cells = [c.strip() for c in table_lines[2].strip("|").split("|")]
    cost_col_idx = header_cols.index("cost_per_1k_requests_usd")
    assert legacy_cells[cost_col_idx] == "N/A"
    assert legacy_cells[-1] == "Legacy baseline"
