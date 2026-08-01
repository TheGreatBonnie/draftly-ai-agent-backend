from __future__ import annotations

from datetime import timedelta

import structlog

from src.analytics.analyzer import analyze_production_traces
from src.analytics.improver import (
    apply_improvement,
    create_improvement_proposals,
    generate_improvements,
    load_current_config,
)
from src.analytics.traces import TraceCollector
from src.config import settings

logger = structlog.get_logger()


class HillClimber:
    def __init__(
        self,
        trace_collector: TraceCollector,
        org_id: str,
        analysis_interval: int = 100,
    ):
        self.trace_collector = trace_collector
        self.org_id = org_id
        self.analysis_interval = analysis_interval
        self._trace_count = 0

    async def should_analyze(self) -> bool:
        self._trace_count += 1
        if self._trace_count >= self.analysis_interval:
            self._trace_count = 0
            return True
        return False

    async def run_analysis_cycle(self) -> dict:
        logger.info("hill_climbing_cycle_started", org_id=self.org_id)

        traces = await self.trace_collector.get_traces_for_analysis(
            org_id=self.org_id,
            time_window=timedelta(days=7),
        )

        if not traces:
            logger.info("no_traces_for_analysis", org_id=self.org_id)
            return {"status": "no_traces"}

        analysis = await analyze_production_traces(traces)
        if "error" in analysis and analysis.get("overall_health") == "unknown":
            logger.error("analysis_failed_skipping_improvements", org_id=self.org_id)
            return {"status": "analysis_failed", "analysis": analysis}

        current_config = await load_current_config(self.org_id)
        improvements = await generate_improvements(analysis, current_config)
        if "error" in improvements:
            logger.error("improvement_generation_failed", org_id=self.org_id)
            return {"status": "improvement_failed", "analysis": analysis}

        proposals = await create_improvement_proposals(self.org_id, improvements, analysis=analysis)

        if settings.auto_apply_improvements:
            for proposal in proposals:
                if proposal.improvement_type == "rubric":
                    await apply_improvement(proposal.id)
                    logger.info(
                        "rubric_auto_applied",
                        proposal_id=proposal.id,
                    )

        logger.info(
            "hill_climbing_cycle_completed",
            org_id=self.org_id,
            traces_analyzed=len(traces),
            proposals_created=len(proposals),
        )

        return {
            "status": "completed",
            "traces_analyzed": len(traces),
            "proposals_created": len(proposals),
            "analysis": analysis,
        }
