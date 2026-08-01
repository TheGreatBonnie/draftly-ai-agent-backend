from __future__ import annotations

import json
import re
from typing import Any

import structlog

from src.analytics.traces import AgentTrace
from src.integrations.llm import call_llm, stage_llm_kwargs

logger = structlog.get_logger()

ANALYSIS_PROMPT = (
    """You are an agent performance analyst. Analyze these execution traces
and identify improvement opportunities.

## Traces Summary
{traces_summary}

## Analysis Tasks

1. **Failure Pattern Analysis**
   - Identify common failure modes
   - Find nodes with highest error rates
   - Detect timeout patterns

2. **Quality Pattern Analysis**
   - Identify prompts that consistently produce low confidence
   - Find rubric criteria that frequently fail
   - Detect verification check patterns

3. **Performance Analysis**
   - Find bottleneck nodes (highest duration)
   - Identify parallelization opportunities
   - Detect resource waste

4. **Improvement Suggestions**
   - Specific prompt rewrites for underperforming nodes
   - New tool suggestions for research gaps
   - Rubric criteria adjustments

Return a JSON object with:
{{
    "failure_patterns": [{{"pattern": "string", "frequency": 0, "impact": "string"}}],
    "quality_patterns": [{{"pattern": "string", "frequency": 0, "suggestion": "string"}}],
    "performance_patterns": [
        {{"node": "string", "avg_duration_ms": 0.0, "optimization": "string"}}
    ],
    "improvements": {{
        "prompts": [
            {{"node": "string", "current_issue": "string",
              "suggested_fix": "string", "rationale": "string"}}
        ],
        "tools": [{{"gap": "string", "suggested_tool": "string", "rationale": "string"}}],
        "rubrics": [{{"criterion": "string", "issue": "string", "suggested_change": "string"}}]
    }},
    "confidence_trend": 0.0,
    "overall_health": "good" | "needs_attention" | "critical"
}}

Return ONLY valid JSON."""
)


def _summarize_traces(traces: list[AgentTrace]) -> str:
    if not traces:
        return "No traces available."

    total = len(traces)
    avg_confidence = sum(t.final_confidence for t in traces) / total
    publish_count = sum(1 for t in traces if t.published)
    node_stats: dict[str, dict] = {}

    for trace in traces:
        for nt in trace.node_traces:
            node = nt.node_name
            if node not in node_stats:
                node_stats[node] = {"count": 0, "total_duration_ms": 0, "errors": 0}
            node_stats[node]["count"] += 1
            node_stats[node]["total_duration_ms"] += nt.duration_ms
            if nt.error:
                node_stats[node]["errors"] += 1

    for stats in node_stats.values():
        stats["avg_duration_ms"] = (
            stats["total_duration_ms"] / stats["count"] if stats["count"] else 0
        )
        stats["error_rate"] = stats["errors"] / stats["count"] if stats["count"] else 0

    summary = {
        "total_traces": total,
        "avg_confidence": round(avg_confidence, 3),
        "publish_rate": round(publish_count / total, 3) if total else 0,
        "node_statistics": node_stats,
        "failure_summary": {
            "total_errors": sum(s["errors"] for s in node_stats.values()),
            "error_nodes": [n for n, s in node_stats.items() if s["errors"] > 0],
        },
    }
    return json.dumps(summary, indent=2, default=str)


async def analyze_production_traces(traces: list[AgentTrace]) -> dict[str, Any]:
    if not traces:
        return {"error": "no_traces", "overall_health": "unknown"}

    traces_summary = _summarize_traces(traces)

    try:
        response = await call_llm(
            prompt=ANALYSIS_PROMPT.format(traces_summary=traces_summary),
            system_prompt=(
                "You are an expert at analyzing AI agent performance."
                " Be specific and actionable."
            ),
            **stage_llm_kwargs("analysis"),
        )
        analysis = _parse_json_response(response)
    except Exception as e:
        logger.error("trace_analysis_failed", error=str(e))
        return {"error": str(e), "overall_health": "unknown"}

    analysis["metrics"] = {
        "total_traces": len(traces),
        "avg_confidence": sum(t.final_confidence for t in traces) / len(traces),
        "publish_ratio": sum(1 for t in traces if t.published) / len(traces),
    }
    return analysis


def _parse_json_response(response: str) -> dict[str, Any]:
    try:
        return json.loads(response)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", response)
        if match:
            return json.loads(match.group())  # type: ignore[no-any-return]
        return {"error": "Failed to parse analysis response", "overall_health": "unknown"}
