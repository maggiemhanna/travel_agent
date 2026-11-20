# Copyright (c) 2024 Maggie Mhanna
# All rights reserved.

"""AI token, Google Search grounding, and caching cost calculator for conversational_app."""

from __future__ import annotations

import copy
from functools import lru_cache
import json
import math
import os
from typing import Any, Dict, Iterable, List, Mapping, Optional

DEFAULT_PRICING_CONFIG_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "configs",
        "pricing_config.json",
    )
)


@lru_cache(maxsize=8)
def _load_pricing_catalog_cached(resolved_path: str) -> Dict[str, Any]:
    with open(resolved_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_pricing_catalog(
    pricing_config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Loads the Vertex AI model & grounding pricing catalog JSON."""
    target_path = (
        pricing_config_path
        or os.getenv("PRICING_CONFIG_PATH")
        or DEFAULT_PRICING_CONFIG_PATH
    )
    resolved = os.path.abspath(target_path)
    return copy.deepcopy(_load_pricing_catalog_cached(resolved))


def normalize_model_name(raw_model: Optional[str]) -> str:
    """Strips Vertex AI publisher/project resource prefixes from a model identifier."""
    if not raw_model:
        return ""
    cleaned = str(raw_model).strip()
    if "/models/" in cleaned:
        cleaned = cleaned.split("/models/")[-1]
    elif cleaned.startswith("models/"):
        cleaned = cleaned[len("models/") :]
    return cleaned.strip()


def resolve_model_pricing(
    model_name: Optional[str],
    catalog: Optional[Mapping[str, Any]] = None,
) -> tuple[str, Dict[str, Any], bool]:
    """Resolves a model string to ``(matched_key, pricing_spec, fallback_used)``.

    Uses exact match first, then longest-prefix match (so ``gemini-3.5-flash-lite-001``
    matches ``gemini-3.5-flash-lite`` before any shorter prefix), and falls back to
    ``catalog['default_model']`` if unknown.
    """
    cat = catalog or load_pricing_catalog()
    models_map: Mapping[str, Any] = cat.get("models") or {}
    default_key = str(cat.get("default_model") or "gemini-3.8-flash")

    normalized = normalize_model_name(model_name)
    if normalized and normalized in models_map:
        return normalized, dict(models_map[normalized]), False

    if normalized:
        prefix_candidates = [
            key
            for key in models_map.keys()
            if normalized.startswith(key) or key.startswith(normalized)
        ]
        if prefix_candidates:
            # Prefer keys that are prefixes of `normalized`, ordered by longest key
            strict_prefixes = [
                k for k in prefix_candidates if normalized.startswith(k)
            ]
            best_key = max(
                strict_prefixes or prefix_candidates,
                key=len,
            )
            return best_key, dict(models_map[best_key]), False

    fallback_spec = dict(models_map.get(default_key) or {})
    return default_key, fallback_spec, True


def parse_model_overrides(
    raw_overrides: Optional[Iterable[str]],
) -> Dict[str, str]:
    """Parses CLI model override specs (`model_id` or `agent_name=model_id`).

    Examples:
        - ``["gemini-3.6-flash"]`` -> ``{"*": "gemini-3.6-flash"}``
        - ``["filter_smart=gemini-3.1-pro-preview"]`` -> ``{"filter_smart": "gemini-3.1-pro-preview"}``
    """
    overrides: Dict[str, str] = {}
    for item in raw_overrides or []:
        text = str(item or "").strip()
        if not text:
            continue
        if "=" in text:
            agent_key, model_val = text.split("=", 1)
            agent_key = agent_key.strip()
            model_val = model_val.strip()
            if agent_key and model_val:
                overrides[agent_key] = model_val
        else:
            overrides["*"] = text
    return overrides


def compute_step_cost_from_counts(
    *,
    author: str,
    configured_model: Optional[str] = None,
    resolved_model: Optional[str] = None,
    latency_seconds: float = 0.0,
    prompt_tokens: int = 0,
    cached_input_tokens: int = 0,
    tool_use_prompt_tokens: int = 0,
    candidates_output_tokens: int = 0,
    thoughts_tokens: int = 0,
    web_search_queries: Optional[List[str]] = None,
    is_grounded_request: Optional[bool] = None,
    response_cache_hit: bool = False,
    context_cache_name: Optional[str] = None,
    catalog: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Computes exact Standard PayGo token + Google Search grounding cost for one LLM call."""
    cat = catalog or load_pricing_catalog()
    effective_model = (
        normalize_model_name(resolved_model)
        or normalize_model_name(configured_model)
        or str(cat.get("default_model") or "gemini-3.8-flash")
    )
    pricing_key, spec, fallback_used = resolve_model_pricing(effective_model, cat)

    prompt_tok = max(0, int(prompt_tokens or 0))
    cached_tok = min(prompt_tok, max(0, int(cached_input_tokens or 0)))
    uncached_in_tok = max(0, prompt_tok - cached_tok)
    tool_in_tok = max(0, int(tool_use_prompt_tokens or 0))
    billable_uncached_in_tok = uncached_in_tok + tool_in_tok

    cand_out_tok = max(0, int(candidates_output_tokens or 0))
    thought_tok = max(0, int(thoughts_tokens or 0))
    billable_out_tok = cand_out_tok + thought_tok
    total_tok = prompt_tok + tool_in_tok + cand_out_tok + thought_tok

    queries_clean = [
        str(q).strip() for q in (web_search_queries or []) if str(q).strip()
    ]
    queries_count = len(queries_clean)
    grounded_flag = (
        bool(is_grounded_request)
        if is_grounded_request is not None
        else (queries_count > 0)
    )

    long_ctx_threshold = int(spec.get("long_context_threshold_tokens", 200_000))
    is_long_ctx = prompt_tok > long_ctx_threshold

    input_rate = float(
        spec.get(
            "long_context_input_per_1m_usd" if is_long_ctx else "input_per_1m_usd",
            spec.get("input_per_1m_usd", 0.30),
        )
    )
    cached_input_rate = float(
        spec.get(
            "long_context_cached_input_per_1m_usd"
            if is_long_ctx
            else "cached_input_per_1m_usd",
            spec.get("cached_input_per_1m_usd", input_rate * 0.1),
        )
    )
    output_rate = float(
        spec.get(
            "long_context_output_per_1m_usd"
            if is_long_ctx
            else "output_per_1m_usd",
            spec.get("output_per_1m_usd", 2.50),
        )
    )

    grounding_Defaults = cat.get("grounding_defaults") or {}
    grounding_cfg = spec.get("google_search_grounding") or grounding_Defaults
    billing_mode = str(
        grounding_cfg.get(
            "billing_mode",
            grounding_Defaults.get("billing_mode", "per_search_query"),
        )
    )
    search_unit_price = float(
        grounding_cfg.get(
            "price_per_unit_usd",
            grounding_Defaults.get("price_per_unit_usd", 0.014),
        )
    )
    if billing_mode == "per_grounded_request":
        billable_search_units = 1 if grounded_flag else 0
    else:
        billable_search_units = queries_count

    raw_uncached_in_cost = (billable_uncached_in_tok / 1_000_000.0) * input_rate
    raw_cached_in_cost = (cached_tok / 1_000_000.0) * cached_input_rate
    raw_ctx_cache_savings = max(
        0.0, (cached_tok / 1_000_000.0) * (input_rate - cached_input_rate)
    )
    raw_cand_out_cost = (cand_out_tok / 1_000_000.0) * output_rate
    raw_thoughts_cost = (thought_tok / 1_000_000.0) * output_rate
    raw_llm_token_cost = (
        raw_uncached_in_cost
        + raw_cached_in_cost
        + raw_cand_out_cost
        + raw_thoughts_cost
    )
    raw_grounding_cost = billable_search_units * search_unit_price
    raw_total_cost = raw_llm_token_cost + raw_grounding_cost

    if response_cache_hit:
        uncached_in_cost = 0.0
        cached_in_cost = 0.0
        ctx_cache_savings = 0.0
        cand_out_cost = 0.0
        thoughts_cost = 0.0
        llm_token_cost = 0.0
        grounding_cost = 0.0
        total_cost = 0.0
        response_cache_avoided = raw_total_cost
    else:
        uncached_in_cost = raw_uncached_in_cost
        cached_in_cost = raw_cached_in_cost
        ctx_cache_savings = raw_ctx_cache_savings
        cand_out_cost = raw_cand_out_cost
        thoughts_cost = raw_thoughts_cost
        llm_token_cost = raw_llm_token_cost
        grounding_cost = raw_grounding_cost
        total_cost = raw_total_cost
        response_cache_avoided = 0.0

    context_cache_hit = bool(cached_tok > 0 or context_cache_name)

    return {
        "author": author,
        "configured_model": normalize_model_name(configured_model) or effective_model,
        "resolved_model": effective_model,
        "pricing_model_key": pricing_key,
        "model_family": str(spec.get("family") or "gemini_3"),
        "pricing_fallback_used": fallback_used,
        "is_long_context_tier": is_long_ctx,
        "latency_seconds": round(float(latency_seconds or 0.0), 4),
        "prompt_tokens": prompt_tok,
        "uncached_input_tokens": uncached_in_tok,
        "cached_input_tokens": cached_tok,
        "tool_use_prompt_tokens": tool_in_tok,
        "billable_uncached_input_tokens": billable_uncached_in_tok,
        "candidates_output_tokens": cand_out_tok,
        "thoughts_tokens": thought_tok,
        "billable_output_tokens": billable_out_tok,
        "total_tokens": total_tok,
        "web_search_queries": queries_clean,
        "search_queries_count": queries_count,
        "is_grounded_request": grounded_flag,
        "grounding_billing_mode": billing_mode,
        "billable_search_units": 0 if response_cache_hit else billable_search_units,
        "response_cache_hit": bool(response_cache_hit),
        "context_cache_hit": context_cache_hit,
        "context_cache_name": context_cache_name,
        "rates_applied": {
            "input_per_1m_usd": input_rate,
            "cached_input_per_1m_usd": cached_input_rate,
            "output_per_1m_usd": output_rate,
            "search_unit_price_usd": search_unit_price,
        },
        "uncached_input_cost_usd": round(uncached_in_cost, 10),
        "cached_input_cost_usd": round(cached_in_cost, 10),
        "candidates_output_cost_usd": round(cand_out_cost, 10),
        "thoughts_cost_usd": round(thoughts_cost, 10),
        "llm_token_cost_usd": round(llm_token_cost, 10),
        "search_grounding_cost_usd": round(grounding_cost, 10),
        "total_cost_usd": round(total_cost, 10),
        "cost_per_1k_requests_usd": round(total_cost * 1000.0, 6),
        "llm_token_cost_per_1k_usd": round(llm_token_cost * 1000.0, 6),
        "search_grounding_cost_per_1k_usd": round(grounding_cost * 1000.0, 6),
        "context_cache_savings_usd": round(ctx_cache_savings, 10),
        "response_cache_avoided_cost_usd": round(response_cache_avoided, 10),
    }


def extract_step_usage_and_cost(
    *,
    author: str,
    llm_response: Any,
    configured_model: Optional[str] = None,
    latency_seconds: float = 0.0,
    catalog: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Extracts usage, grounding, and cache metadata from an ADK LlmResponse/Event and prices it."""
    usage = getattr(llm_response, "usage_metadata", None)
    prompt_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
    cached_tok = int(getattr(usage, "cached_content_token_count", 0) or 0)
    tool_in_tok = int(getattr(usage, "tool_use_prompt_token_count", 0) or 0)
    cand_out_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
    thought_tok = int(getattr(usage, "thoughts_token_count", 0) or 0)

    gm = getattr(llm_response, "grounding_metadata", None)
    raw_queries = getattr(gm, "web_search_queries", None) or [] if gm else []
    queries = [str(q).strip() for q in raw_queries if str(q).strip()]
    has_chunks = bool(getattr(gm, "grounding_chunks", None)) if gm else False
    is_grounded = bool(queries or has_chunks)

    cache_meta = getattr(llm_response, "cache_metadata", None)
    cache_name = getattr(cache_meta, "cache_name", None) if cache_meta else None

    custom_meta = getattr(llm_response, "custom_metadata", None)
    if not isinstance(custom_meta, Mapping):
        custom_meta = {}
    resp_cache_hit = bool(
        custom_meta.get("response_cache_hit")
        or str(custom_meta.get("cache_status") or "").lower() == "hit"
    )

    resolved_model = getattr(llm_response, "model_version", None)

    return compute_step_cost_from_counts(
        author=author,
        configured_model=configured_model,
        resolved_model=resolved_model,
        latency_seconds=latency_seconds,
        prompt_tokens=prompt_tok,
        cached_input_tokens=cached_tok,
        tool_use_prompt_tokens=tool_in_tok,
        candidates_output_tokens=cand_out_tok,
        thoughts_tokens=thought_tok,
        web_search_queries=queries,
        is_grounded_request=is_grounded,
        response_cache_hit=resp_cache_hit,
        context_cache_name=cache_name,
        catalog=catalog,
    )


def aggregate_invocation_cost(
    steps: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Aggregates sub-agent LLM step records into a single turn/request cost summary."""
    prompt_tokens = sum(int(s.get("prompt_tokens", 0)) for s in steps)
    uncached_input_tokens = sum(
        int(s.get("uncached_input_tokens", 0)) for s in steps
    )
    cached_input_tokens = sum(int(s.get("cached_input_tokens", 0)) for s in steps)
    tool_use_prompt_tokens = sum(
        int(s.get("tool_use_prompt_tokens", 0)) for s in steps
    )
    billable_uncached_input_tokens = sum(
        int(s.get("billable_uncached_input_tokens", 0)) for s in steps
    )
    candidates_output_tokens = sum(
        int(s.get("candidates_output_tokens", 0)) for s in steps
    )
    thoughts_tokens = sum(int(s.get("thoughts_tokens", 0)) for s in steps)
    billable_output_tokens = sum(
        int(s.get("billable_output_tokens", 0)) for s in steps
    )
    total_tokens = sum(int(s.get("total_tokens", 0)) for s in steps)

    search_queries_count = sum(
        int(s.get("search_queries_count", 0)) for s in steps
    )
    billable_search_units = sum(
        int(s.get("billable_search_units", 0)) for s in steps
    )
    grounded_requests_count = sum(
        1 for s in steps if s.get("is_grounded_request")
    )
    response_cache_hits_count = sum(
        1 for s in steps if s.get("response_cache_hit")
    )
    context_cache_hits_count = sum(
        1 for s in steps if s.get("context_cache_hit")
    )
    json_repair_triggered = any(
        s.get("author") == "json_parser" for s in steps
    )

    uncached_input_cost_usd = sum(
        float(s.get("uncached_input_cost_usd", 0.0)) for s in steps
    )
    cached_input_cost_usd = sum(
        float(s.get("cached_input_cost_usd", 0.0)) for s in steps
    )
    candidates_output_cost_usd = sum(
        float(s.get("candidates_output_cost_usd", 0.0)) for s in steps
    )
    thoughts_cost_usd = sum(
        float(s.get("thoughts_cost_usd", 0.0)) for s in steps
    )
    llm_token_cost_usd = sum(
        float(s.get("llm_token_cost_usd", 0.0)) for s in steps
    )
    search_grounding_cost_usd = sum(
        float(s.get("search_grounding_cost_usd", 0.0)) for s in steps
    )
    total_cost_usd = sum(float(s.get("total_cost_usd", 0.0)) for s in steps)
    context_cache_savings_usd = sum(
        float(s.get("context_cache_savings_usd", 0.0)) for s in steps
    )
    response_cache_avoided_cost_usd = sum(
        float(s.get("response_cache_avoided_cost_usd", 0.0)) for s in steps
    )

    by_agent: Dict[str, Dict[str, Any]] = {}
    for s in steps:
        ag = str(s.get("author") or "unknown")
        bucket = by_agent.setdefault(
            ag,
            {
                "calls": 0,
                "model": s.get("resolved_model") or s.get("pricing_model_key"),
                "prompt_tokens": 0,
                "cached_input_tokens": 0,
                "candidates_output_tokens": 0,
                "thoughts_tokens": 0,
                "total_tokens": 0,
                "search_queries_count": 0,
                "llm_token_cost_usd": 0.0,
                "search_grounding_cost_usd": 0.0,
                "total_cost_usd": 0.0,
            },
        )
        bucket["calls"] += 1
        bucket["prompt_tokens"] += int(s.get("prompt_tokens", 0))
        bucket["cached_input_tokens"] += int(s.get("cached_input_tokens", 0))
        bucket["candidates_output_tokens"] += int(
            s.get("candidates_output_tokens", 0)
        )
        bucket["thoughts_tokens"] += int(s.get("thoughts_tokens", 0))
        bucket["total_tokens"] += int(s.get("total_tokens", 0))
        bucket["search_queries_count"] += int(s.get("search_queries_count", 0))
        bucket["llm_token_cost_usd"] = round(
            bucket["llm_token_cost_usd"] + float(s.get("llm_token_cost_usd", 0.0)),
            10,
        )
        bucket["search_grounding_cost_usd"] = round(
            bucket["search_grounding_cost_usd"]
            + float(s.get("search_grounding_cost_usd", 0.0)),
            10,
        )
        bucket["total_cost_usd"] = round(
            bucket["total_cost_usd"] + float(s.get("total_cost_usd", 0.0)),
            10,
        )

    return {
        "llm_calls_count": len(steps),
        "prompt_tokens": prompt_tokens,
        "uncached_input_tokens": uncached_input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "tool_use_prompt_tokens": tool_use_prompt_tokens,
        "billable_uncached_input_tokens": billable_uncached_input_tokens,
        "candidates_output_tokens": candidates_output_tokens,
        "thoughts_tokens": thoughts_tokens,
        "billable_output_tokens": billable_output_tokens,
        "total_tokens": total_tokens,
        "search_queries_count": search_queries_count,
        "billable_search_units": billable_search_units,
        "grounded_requests_count": grounded_requests_count,
        "is_grounded_turn": grounded_requests_count > 0,
        "json_repair_triggered": json_repair_triggered,
        "response_cache_hits_count": response_cache_hits_count,
        "context_cache_hits_count": context_cache_hits_count,
        "uncached_input_cost_usd": round(uncached_input_cost_usd, 10),
        "cached_input_cost_usd": round(cached_input_cost_usd, 10),
        "candidates_output_cost_usd": round(candidates_output_cost_usd, 10),
        "thoughts_cost_usd": round(thoughts_cost_usd, 10),
        "llm_token_cost_usd": round(llm_token_cost_usd, 10),
        "search_grounding_cost_usd": round(search_grounding_cost_usd, 10),
        "total_cost_usd": round(total_cost_usd, 10),
        "cost_per_1k_requests_usd": round(total_cost_usd * 1000.0, 6),
        "llm_token_cost_per_1k_usd": round(llm_token_cost_usd * 1000.0, 6),
        "search_grounding_cost_per_1k_usd": round(
            search_grounding_cost_usd * 1000.0, 6
        ),
        "context_cache_savings_usd": round(context_cache_savings_usd, 10),
        "response_cache_avoided_cost_usd": round(
            response_cache_avoided_cost_usd, 10
        ),
        "by_agent": by_agent,
    }


def _percentile(sorted_values: List[float], q: float) -> float:
    """Computes linear-interpolated percentile for a pre-sorted float list."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    lower = int(math.floor(pos))
    upper = int(math.ceil(pos))
    if lower == upper:
        return sorted_values[lower]
    weight = pos - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


def compute_analytical_cache_projections(
    traced_records: List[Dict[str, Any]],
    catalog: Optional[Mapping[str, Any]] = None,
    response_cache_hit_rates: Optional[List[float]] = None,
    context_cache_hit_rates: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """Projects cost & latency savings across response-cache and Gemini context-cache hit rates.

    1. **Response Cache Sensitivity**: Models exact/semantic response caching where a cache
       hit short-circuits both LLM token generation and Google Search grounding (`$0` AI cost,
       near-zero AI latency).
    2. **Context Cache (Prefix Cache) Sensitivity**: Models discounting uncached prompt tokens
       to each model's ``cached_input_per_1m_usd`` rate while keeping output/thinking tokens and
       Google Search grounding fees unchanged. Reports both theoretical prefix savings and
       threshold-gated savings enforcing Gemini's minimum cacheable token thresholds
       (4,096 tokens on Gemini 3; 2,048 tokens on Gemini 2.5).
    """
    cat = catalog or load_pricing_catalog()
    resp_rates = (
        response_cache_hit_rates
        if response_cache_hit_rates is not None
        else list(cat.get("analytical_response_cache_hit_rates") or [0.0, 0.1, 0.2, 0.3, 0.5])
    )
    ctx_rates = (
        context_cache_hit_rates
        if context_cache_hit_rates is not None
        else list(cat.get("analytical_context_cache_hit_rates") or [0.0, 0.5, 0.8, 0.95])
    )
    min_tokens_map = cat.get("context_cache_min_tokens") or {
        "gemini_3": 4096,
        "gemini_2_5": 2048,
    }

    n_cases = len(traced_records)
    if n_cases == 0:
        return {
            "response_cache_sensitivity": [],
            "context_cache_prefix_sensitivity": [],
            "agent_context_cache_eligibility": {},
        }

    case_costs = [
        float((r.get("cost_summary") or {}).get("total_cost_usd", 0.0))
        for r in traced_records
    ]
    case_latencies = [
        float(r.get("latency_seconds", 0.0) or 0.0) for r in traced_records
    ]
    cold_cost_per_1k = (sum(case_costs) / n_cases) * 1000.0
    cold_mean_latency = sum(case_latencies) / n_cases

    response_projections: List[Dict[str, Any]] = []
    for hr in resp_rates:
        h = max(0.0, min(1.0, float(hr)))
        eff_cost_1k = (1.0 - h) * cold_cost_per_1k
        sav_1k = cold_cost_per_1k - eff_cost_1k
        eff_lat = (1.0 - h) * cold_mean_latency
        response_projections.append(
            {
                "hit_rate": round(h, 4),
                "hit_rate_pct": round(h * 100.0, 1),
                "effective_cost_per_1k_usd": round(eff_cost_1k, 4),
                "savings_per_1k_usd": round(sav_1k, 4),
                "cost_reduction_pct": round(h * 100.0, 1) if cold_cost_per_1k > 0 else 0.0,
                "effective_mean_latency_seconds": round(eff_lat, 3),
            }
        )

    # Compute potential input-token savings per step if uncached prompt tokens hit context cache
    total_theoretical_max_discount_usd = 0.0
    total_threshold_gated_max_discount_usd = 0.0
    agent_prompt_stats: Dict[str, Dict[str, Any]] = {}

    for rec in traced_records:
        for step in rec.get("sub_agent_usages") or []:
            if step.get("response_cache_hit"):
                continue
            author = str(step.get("author") or "unknown")
            family = str(step.get("model_family") or "gemini_3")
            min_req = int(min_tokens_map.get(family, 4096))
            prompt_tok = int(step.get("prompt_tokens", 0))
            uncached_prompt_tok = int(step.get("uncached_input_tokens", 0))
            rates = step.get("rates_applied") or {}
            in_rate = float(rates.get("input_per_1m_usd", 0.30))
            cached_rate = float(
                rates.get("cached_input_per_1m_usd", in_rate * 0.1)
            )
            step_max_discount = max(
                0.0,
                (uncached_prompt_tok / 1_000_000.0) * (in_rate - cached_rate),
            )
            total_theoretical_max_discount_usd += step_max_discount
            meets_min = prompt_tok >= min_req
            if meets_min:
                total_threshold_gated_max_discount_usd += step_max_discount

            st = agent_prompt_stats.setdefault(
                author,
                {
                    "calls": 0,
                    "prompt_tokens_sum": 0,
                    "max_prompt_tokens": 0,
                    "calls_meeting_min_tokens": 0,
                    "model_family": family,
                    "min_cache_tokens_required": min_req,
                },
            )
            st["calls"] += 1
            st["prompt_tokens_sum"] += prompt_tok
            st["max_prompt_tokens"] = max(st["max_prompt_tokens"], prompt_tok)
            if meets_min:
                st["calls_meeting_min_tokens"] += 1

    theoretical_max_sav_1k = (
        total_theoretical_max_discount_usd / n_cases
    ) * 1000.0
    gated_max_sav_1k = (
        total_threshold_gated_max_discount_usd / n_cases
    ) * 1000.0

    context_projections: List[Dict[str, Any]] = []
    for hr in ctx_rates:
        h = max(0.0, min(1.0, float(hr)))
        theo_sav_1k = h * theoretical_max_sav_1k
        theo_eff_1k = max(0.0, cold_cost_per_1k - theo_sav_1k)
        gated_sav_1k = h * gated_max_sav_1k
        gated_eff_1k = max(0.0, cold_cost_per_1k - gated_sav_1k)
        context_projections.append(
            {
                "prefix_hit_rate": round(h, 4),
                "prefix_hit_rate_pct": round(h * 100.0, 1),
                "theoretical_effective_cost_per_1k_usd": round(theo_eff_1k, 4),
                "theoretical_input_savings_per_1k_usd": round(theo_sav_1k, 4),
                "theoretical_cost_reduction_pct": (
                    round((theo_sav_1k / cold_cost_per_1k) * 100.0, 2)
                    if cold_cost_per_1k > 0
                    else 0.0
                ),
                "threshold_gated_effective_cost_per_1k_usd": round(gated_eff_1k, 4),
                "threshold_gated_input_savings_per_1k_usd": round(gated_sav_1k, 4),
                "threshold_gated_cost_reduction_pct": (
                    round((gated_sav_1k / cold_cost_per_1k) * 100.0, 2)
                    if cold_cost_per_1k > 0
                    else 0.0
                ),
            }
        )

    eligibility_summary: Dict[str, Dict[str, Any]] = {}
    for ag, st in agent_prompt_stats.items():
        calls = st["calls"]
        avg_prompt = st["prompt_tokens_sum"] / calls if calls else 0.0
        elig_pct = (st["calls_meeting_min_tokens"] / calls * 100.0) if calls else 0.0
        eligibility_summary[ag] = {
            "calls": calls,
            "mean_prompt_tokens": round(avg_prompt, 1),
            "max_prompt_tokens": st["max_prompt_tokens"],
            "model_family": st["model_family"],
            "min_cache_tokens_required": st["min_cache_tokens_required"],
            "calls_meeting_min_tokens": st["calls_meeting_min_tokens"],
            "eligible_call_rate_pct": round(elig_pct, 1),
        }

    return {
        "response_cache_sensitivity": response_projections,
        "context_cache_prefix_sensitivity": context_projections,
        "agent_context_cache_eligibility": eligibility_summary,
    }


def estimate_eval_judge_overhead_cost(
    traced_records: List[Dict[str, Any]],
    eval_config: Mapping[str, Any],
    catalog: Optional[Mapping[str, Any]] = None,
    evaluation_executed: bool = True,
) -> Dict[str, Any]:
    """Estimates Phase 2B LLM-as-a-Judge / Rubric evaluation cost (kept separate from SUT cost)."""
    cat = catalog or load_pricing_catalog()
    judge_model_raw = str(eval_config.get("judge_model") or "gemini-2.5-flash")
    pricing_key, spec, _ = resolve_model_pricing(judge_model_raw, cat)

    llm_metrics = [
        m
        for m in (eval_config.get("metrics") or [])
        if m.get("type") in {"predefined_rubric", "custom_llm"}
    ]
    n_cases = len(traced_records)
    if not evaluation_executed or n_cases == 0 or not llm_metrics:
        return {
            "evaluation_executed": bool(evaluation_executed),
            "judge_model": judge_model_raw,
            "pricing_model_key": pricing_key,
            "llm_judge_metrics_count": len(llm_metrics),
            "estimated_judge_calls": 0,
            "estimated_input_tokens": 0,
            "estimated_output_tokens": 0,
            "estimated_judge_cost_usd": 0.0,
        }

    # Estimate tokens from character lengths (~4 chars/token) + rubric template overhead
    est_in_tokens_total = 0
    est_out_tokens_total = 0
    for rec in traced_records:
        payload_chars = (
            len(str(rec.get("prompt") or ""))
            + len(str(rec.get("conversation_plan") or ""))
            + len(str(rec.get("context") or ""))
            + len(str(rec.get("response") or ""))
            + len(str(rec.get("tool_calls") or ""))
        )
        base_case_tokens = max(250, int(payload_chars / 4))
        for m in llm_metrics:
            is_adaptive_rubric = (
                m.get("type") == "predefined_rubric"
                and m.get("rubric_metric")
                in {"MULTI_TURN_TASK_SUCCESS", "MULTI_TURN_TRAJECTORY_QUALITY"}
            )
            # Adaptive rubrics perform rubric generation + verdict grading (~2 judge hops)
            hops = 2 if is_adaptive_rubric else 1
            est_in_tokens_total += hops * (base_case_tokens + 650)
            est_out_tokens_total += hops * 220

    in_rate = float(spec.get("input_per_1m_usd", 0.30))
    out_rate = float(spec.get("output_per_1m_usd", 2.50))
    est_cost = (est_in_tokens_total / 1_000_000.0) * in_rate + (
        est_out_tokens_total / 1_000_000.0
    ) * out_rate

    return {
        "evaluation_executed": True,
        "judge_model": judge_model_raw,
        "pricing_model_key": pricing_key,
        "llm_judge_metrics_count": len(llm_metrics),
        "estimated_judge_calls": n_cases * len(llm_metrics),
        "estimated_input_tokens": est_in_tokens_total,
        "estimated_output_tokens": est_out_tokens_total,
        "estimated_judge_cost_usd": round(est_cost, 6),
    }


def build_dataset_cost_overview(
    traced_records: List[Dict[str, Any]],
    eval_config: Mapping[str, Any],
    catalog: Optional[Mapping[str, Any]] = None,
    task_success_mean_score: Optional[float] = None,
    inference_reused: bool = False,
    evaluation_executed: bool = True,
) -> Dict[str, Any]:
    """Builds the run-level SUT cost overview, sub-agent attribution, and caching projections."""
    cat = catalog or load_pricing_catalog()
    n_cases = len(traced_records)

    summaries: List[Dict[str, Any]] = []
    for rec in traced_records:
        cs = rec.get("cost_summary")
        if not isinstance(cs, dict):
            cs = aggregate_invocation_cost(rec.get("sub_agent_usages") or [])
        summaries.append(cs)

    total_costs = sorted(float(cs.get("total_cost_usd", 0.0)) for cs in summaries)
    sut_total_cost = sum(total_costs)
    mean_cost = (sut_total_cost / n_cases) if n_cases else 0.0
    p50_cost = _percentile(total_costs, 0.50)
    p95_cost = _percentile(total_costs, 0.95)
    max_cost = total_costs[-1] if total_costs else 0.0

    llm_token_total_cost = sum(
        float(cs.get("llm_token_cost_usd", 0.0)) for cs in summaries
    )
    grounding_total_cost = sum(
        float(cs.get("search_grounding_cost_usd", 0.0)) for cs in summaries
    )
    ctx_savings_total = sum(
        float(cs.get("context_cache_savings_usd", 0.0)) for cs in summaries
    )
    resp_avoided_total = sum(
        float(cs.get("response_cache_avoided_cost_usd", 0.0))
        for cs in summaries
    )

    cost_per_1k = mean_cost * 1000.0
    token_cost_per_1k = (
        (llm_token_total_cost / n_cases) * 1000.0 if n_cases else 0.0
    )
    grounding_cost_per_1k = (
        (grounding_total_cost / n_cases) * 1000.0 if n_cases else 0.0
    )
    cost_per_1k_successful = (
        round(cost_per_1k / float(task_success_mean_score), 4)
        if task_success_mean_score and task_success_mean_score > 0
        else None
    )

    total_prompt_tok = sum(int(cs.get("prompt_tokens", 0)) for cs in summaries)
    total_uncached_in_tok = sum(
        int(cs.get("uncached_input_tokens", 0)) for cs in summaries
    )
    total_cached_in_tok = sum(
        int(cs.get("cached_input_tokens", 0)) for cs in summaries
    )
    total_tool_in_tok = sum(
        int(cs.get("tool_use_prompt_tokens", 0)) for cs in summaries
    )
    total_cand_out_tok = sum(
        int(cs.get("candidates_output_tokens", 0)) for cs in summaries
    )
    total_thoughts_tok = sum(
        int(cs.get("thoughts_tokens", 0)) for cs in summaries
    )
    total_billable_out_tok = sum(
        int(cs.get("billable_output_tokens", 0)) for cs in summaries
    )
    total_all_tok = sum(int(cs.get("total_tokens", 0)) for cs in summaries)
    total_llm_calls = sum(int(cs.get("llm_calls_count", 0)) for cs in summaries)
    total_search_queries = sum(
        int(cs.get("search_queries_count", 0)) for cs in summaries
    )
    grounded_turns = sum(1 for cs in summaries if cs.get("is_grounded_turn"))
    json_repairs = sum(
        1 for cs in summaries if cs.get("json_repair_triggered")
    )
    resp_cache_hits = sum(
        int(cs.get("response_cache_hits_count", 0)) for cs in summaries
    )

    # Per-sub-agent aggregation across dataset
    agent_totals: Dict[str, Dict[str, Any]] = {}
    for rec in traced_records:
        seen_in_case: set[str] = set()
        for step in rec.get("sub_agent_usages") or []:
            ag = str(step.get("author") or "unknown")
            bucket = agent_totals.setdefault(
                ag,
                {
                    "calls": 0,
                    "cases_invoked": 0,
                    "models_seen": set(),
                    "prompt_tokens": 0,
                    "cached_input_tokens": 0,
                    "candidates_output_tokens": 0,
                    "thoughts_tokens": 0,
                    "total_tokens": 0,
                    "search_queries_count": 0,
                    "llm_token_cost_usd": 0.0,
                    "search_grounding_cost_usd": 0.0,
                    "total_cost_usd": 0.0,
                },
            )
            bucket["calls"] += 1
            if ag not in seen_in_case:
                bucket["cases_invoked"] += 1
                seen_in_case.add(ag)
            bucket["models_seen"].add(
                str(step.get("resolved_model") or step.get("pricing_model_key"))
            )
            bucket["prompt_tokens"] += int(step.get("prompt_tokens", 0))
            bucket["cached_input_tokens"] += int(
                step.get("cached_input_tokens", 0)
            )
            bucket["candidates_output_tokens"] += int(
                step.get("candidates_output_tokens", 0)
            )
            bucket["thoughts_tokens"] += int(step.get("thoughts_tokens", 0))
            bucket["total_tokens"] += int(step.get("total_tokens", 0))
            bucket["search_queries_count"] += int(
                step.get("search_queries_count", 0)
            )
            bucket["llm_token_cost_usd"] += float(
                step.get("llm_token_cost_usd", 0.0)
            )
            bucket["search_grounding_cost_usd"] += float(
                step.get("search_grounding_cost_usd", 0.0)
            )
            bucket["total_cost_usd"] += float(step.get("total_cost_usd", 0.0))

    per_sub_agent_breakdown: Dict[str, Dict[str, Any]] = {}
    for ag, b in agent_totals.items():
        calls = b["calls"]
        amortized_1k = (
            (b["total_cost_usd"] / n_cases) * 1000.0 if n_cases else 0.0
        )
        share_pct = (
            (b["total_cost_usd"] / sut_total_cost) * 100.0
            if sut_total_cost > 0
            else 0.0
        )
        per_sub_agent_breakdown[ag] = {
            "calls": calls,
            "cases_invoked": b["cases_invoked"],
            "case_invocation_rate_pct": round(
                (b["cases_invoked"] / n_cases) * 100.0 if n_cases else 0.0, 1
            ),
            "models": sorted(b["models_seen"]),
            "mean_prompt_tokens_per_call": round(
                b["prompt_tokens"] / calls if calls else 0.0, 1
            ),
            "mean_output_tokens_per_call": round(
                b["candidates_output_tokens"] / calls if calls else 0.0, 1
            ),
            "mean_thoughts_tokens_per_call": round(
                b["thoughts_tokens"] / calls if calls else 0.0, 1
            ),
            "total_search_queries": b["search_queries_count"],
            "mean_cost_when_called_usd": round(
                b["total_cost_usd"] / calls if calls else 0.0, 6
            ),
            "amortized_cost_per_1k_requests_usd": round(amortized_1k, 4),
            "share_of_total_sut_cost_pct": round(share_pct, 1),
            "llm_token_cost_per_1k_requests_usd": round(
                (b["llm_token_cost_usd"] / n_cases) * 1000.0 if n_cases else 0.0,
                4,
            ),
            "search_grounding_cost_per_1k_requests_usd": round(
                (b["search_grounding_cost_usd"] / n_cases) * 1000.0
                if n_cases
                else 0.0,
                4,
            ),
        }

    projections = compute_analytical_cache_projections(
        traced_records=traced_records,
        catalog=cat,
    )
    judge_estimate = estimate_eval_judge_overhead_cost(
        traced_records=traced_records,
        eval_config=eval_config,
        catalog=cat,
        evaluation_executed=evaluation_executed,
    )

    return {
        "pricing_catalog_version": cat.get("catalog_version"),
        "billing_tier": cat.get("billing_tier"),
        "currency": cat.get("currency", "USD"),
        "num_cases": n_cases,
        "inference_reused_from_saved_traces": bool(inference_reused),
        "sut_live_inference_spend_usd": (
            0.0 if inference_reused else round(sut_total_cost, 6)
        ),
        "sut_modeled_run_cost_usd": round(sut_total_cost, 6),
        "mean_cost_per_request_usd": round(mean_cost, 6),
        "p50_cost_per_request_usd": round(p50_cost, 6),
        "p95_cost_per_request_usd": round(p95_cost, 6),
        "max_cost_per_request_usd": round(max_cost, 6),
        "cost_per_1k_requests_usd": round(cost_per_1k, 4),
        "llm_token_cost_per_1k_usd": round(token_cost_per_1k, 4),
        "search_grounding_cost_per_1k_usd": round(grounding_cost_per_1k, 4),
        "llm_token_share_of_cost_pct": round(
            (llm_token_total_cost / sut_total_cost) * 100.0
            if sut_total_cost > 0
            else 0.0,
            1,
        ),
        "search_grounding_share_of_cost_pct": round(
            (grounding_total_cost / sut_total_cost) * 100.0
            if sut_total_cost > 0
            else 0.0,
            1,
        ),
        "cost_per_1k_successful_tasks_usd": cost_per_1k_successful,
        "token_averages_per_request": {
            "mean_prompt_tokens": round(
                total_prompt_tok / n_cases if n_cases else 0.0, 1
            ),
            "mean_uncached_input_tokens": round(
                total_uncached_in_tok / n_cases if n_cases else 0.0, 1
            ),
            "mean_cached_input_tokens": round(
                total_cached_in_tok / n_cases if n_cases else 0.0, 1
            ),
            "mean_tool_use_prompt_tokens": round(
                total_tool_in_tok / n_cases if n_cases else 0.0, 1
            ),
            "mean_candidates_output_tokens": round(
                total_cand_out_tok / n_cases if n_cases else 0.0, 1
            ),
            "mean_thoughts_tokens": round(
                total_thoughts_tok / n_cases if n_cases else 0.0, 1
            ),
            "mean_total_tokens": round(
                total_all_tok / n_cases if n_cases else 0.0, 1
            ),
            "thoughts_share_of_output_pct": round(
                (total_thoughts_tok / total_billable_out_tok) * 100.0
                if total_billable_out_tok > 0
                else 0.0,
                1,
            ),
        },
        "workflow_efficiency": {
            "mean_llm_calls_per_request": round(
                total_llm_calls / n_cases if n_cases else 0.0, 2
            ),
            "grounded_turn_rate_pct": round(
                (grounded_turns / n_cases) * 100.0 if n_cases else 0.0, 1
            ),
            "mean_search_queries_per_request": round(
                total_search_queries / n_cases if n_cases else 0.0, 2
            ),
            "json_repair_rate_pct": round(
                (json_repairs / n_cases) * 100.0 if n_cases else 0.0, 1
            ),
            "response_cache_call_hit_rate_pct": round(
                (resp_cache_hits / total_llm_calls) * 100.0
                if total_llm_calls > 0
                else 0.0,
                1,
            ),
            "context_cache_token_hit_rate_pct": round(
                (total_cached_in_tok / total_prompt_tok) * 100.0
                if total_prompt_tok > 0
                else 0.0,
                1,
            ),
            "measured_context_cache_savings_per_1k_usd": round(
                (ctx_savings_total / n_cases) * 1000.0 if n_cases else 0.0, 4
            ),
            "measured_response_cache_avoided_per_1k_usd": round(
                (resp_avoided_total / n_cases) * 1000.0 if n_cases else 0.0, 4
            ),
        },
        "per_sub_agent_breakdown": per_sub_agent_breakdown,
        "analytical_cache_projections": projections,
        "eval_judge_overhead_estimate": judge_estimate,
    }


def reprice_traced_records(
    traced_records: List[Dict[str, Any]],
    catalog: Optional[Mapping[str, Any]] = None,
    model_overrides: Optional[Mapping[str, str]] = None,
) -> List[Dict[str, Any]]:
    """Recomputes ``sub_agent_usages`` and ``cost_summary`` on saved traces using a catalog and optional model overrides."""
    cat = catalog or load_pricing_catalog()
    overrides = dict(model_overrides or {})
    repriced_list: List[Dict[str, Any]] = []

    for rec in traced_records:
        new_rec = copy.deepcopy(rec)
        raw_steps = new_rec.get("sub_agent_usages") or []
        repriced_steps: List[Dict[str, Any]] = []

        for s in raw_steps:
            author = str(s.get("author") or "conversational")
            override_model = overrides.get(author) or overrides.get("*")
            resolved_model = override_model or s.get("resolved_model")
            configured_model = override_model or s.get("configured_model")

            repriced_steps.append(
                compute_step_cost_from_counts(
                    author=author,
                    configured_model=configured_model,
                    resolved_model=resolved_model,
                    latency_seconds=float(s.get("latency_seconds", 0.0) or 0.0),
                    prompt_tokens=int(s.get("prompt_tokens", 0) or 0),
                    cached_input_tokens=int(
                        s.get("cached_input_tokens", 0) or 0
                    ),
                    tool_use_prompt_tokens=int(
                        s.get("tool_use_prompt_tokens", 0) or 0
                    ),
                    candidates_output_tokens=int(
                        s.get("candidates_output_tokens", 0) or 0
                    ),
                    thoughts_tokens=int(s.get("thoughts_tokens", 0) or 0),
                    web_search_queries=list(s.get("web_search_queries") or []),
                    is_grounded_request=s.get("is_grounded_request"),
                    response_cache_hit=bool(s.get("response_cache_hit", False)),
                    context_cache_name=s.get("context_cache_name"),
                    catalog=cat,
                )
            )

        new_rec["sub_agent_usages"] = repriced_steps
        new_rec["cost_summary"] = aggregate_invocation_cost(repriced_steps)
        repriced_list.append(new_rec)

    return repriced_list
