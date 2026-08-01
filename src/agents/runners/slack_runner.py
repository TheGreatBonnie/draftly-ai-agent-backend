"""Slack pipeline runner — orchestrates the Draftly graph for Slack messages."""
from __future__ import annotations

import structlog
from langchain_cockroachdb import AsyncCockroachDBSaver  # type: ignore[import-untyped]
from langchain_core.runnables import RunnableConfig

from src.agents.graph import build_hybrid_graph
from src.agents.state import DocumentationState
from src.config import settings

logger = structlog.get_logger()


def build_slack_state(
    team_id: str,
    channel: str,
    thread_ts: str,
    ts: str,
    text: str,
    user: str,
    org_id: str,
    message_history: list[dict[str, str]] | None = None,
) -> DocumentationState:
    """Build initial DocumentationState from Slack message event."""
    graph_thread_id = f"slack-{channel}-{thread_ts}"

    return {
        "org_id": org_id,
        "source": "slack",
        "channel_id": channel,
        "thread_id": thread_ts,
        "graph_thread_id": graph_thread_id,
        "question": text,
        "similar_threads": [],
        "existing_docs": [],
        "reviewer_feedback_history": [],
        "semantic_context": [],
        "github_context": [],
        "slack_context": [],
        "knowledge_package": {},
        "draft_content": "",
        "draft_title": "",
        "doc_type": "howto",
        "confidence_score": 0.0,
        "review_result": {},
        "review_feedback": "",
        "rubric_feedback": "",
        "rubric_evaluations": [],
        "human_decision": "",
        "human_feedback": "",
        "published_urls": [],
        "reply_errors": [],
        "support_thread_id": "",
        "workflow_id": "",
        "doc_id": "",
        "messages": [],
        "source_metadata": {
            "team_id": team_id,
            "channel": channel,
            "thread_ts": thread_ts,
            "ts": ts,
            "user_id": user,
        },
        "message_history": message_history or [],
        "question_type": "unknown",
        "research_skill": {},
        "investigation_plan": [],
        "rubric_status": {},
        "subagent_results": {},
        "_node_traces": [],
        "_trace_collected": False,
    }


async def run_slack_pipeline(
    team_id: str,
    channel: str,
    thread_ts: str,
    ts: str,
    text: str,
    user: str,
    message_history: list[dict[str, str]] | None = None,
) -> None:
    """Orchestrate the full Draftly pipeline for a Slack support request."""
    from src.database import get_pool
    from src.integrations.slack_conversation import conversation_store
    from src.integrations.slack_store import installation_store
    from src.memory.organizations import (
        get_org_by_slack,
        link_workflow_to_document,
        store_slack_workflow,
        update_slack_workflow_status,
    )

    await get_pool()

    try:
        logger.info(
            "slack_pipeline_started",
            team_id=team_id,
            channel=channel,
            thread_ts=thread_ts,
            text_preview=text[:100],
        )

        org = await get_org_by_slack(team_id)
        if not org:
            logger.error("slack_pipeline_org_not_found", team_id=team_id)
            try:
                from src.integrations.slack import send_slack_message

                await send_slack_message(
                    channel,
                    "⚠️ Draftly is not linked to your organization yet. "
                    "Please go to Draftly Settings → Slack Integration → "
                    '"Connect Slack Workspace" to link this workspace.',
                    thread_ts=thread_ts,
                )
            except Exception:
                logger.error("failed_to_post_org_not_found_message")
            return
        org_id = org["id"]

        from src.integrations.slack_mcp import get_slack_mcp_tools

        if team_id:
            installation = await installation_store.async_find_installation(
                None, team_id
            )
            if installation and installation.user_token:
                await get_slack_mcp_tools(installation.user_token, team_id)

        state = build_slack_state(
            team_id, channel, thread_ts, ts, text, user, org_id, message_history
        )
        # MCP client is cached in slack_mcp module, not stored in state
        # (not msgpack-serializable for the LangGraph checkpointer)
        config: RunnableConfig = {
            "configurable": {"thread_id": state["graph_thread_id"]}
        }

        from uuid import uuid4

        workflow_id = str(uuid4())
        state["workflow_id"] = workflow_id
        await store_slack_workflow(
            org_id=org_id,
            workflow_id=workflow_id,
            channel_id=channel,
            thread_ts=thread_ts,
        )
        await update_slack_workflow_status(workflow_id, "running")

        logger.info(
            "slack_pipeline_running",
            workflow_id=workflow_id,
            org_id=org_id,
            graph_thread_id=state["graph_thread_id"],
        )

        async with AsyncCockroachDBSaver.from_conn_string(
            settings.cockroachdb_url,
        ) as checkpointer:
            await checkpointer.setup()
            graph = build_hybrid_graph().compile(checkpointer=checkpointer)
            structlog.contextvars.bind_contextvars(workflow_id=workflow_id, org_id=org_id)
            try:
                result = await graph.ainvoke(state, config)

                if result.get("draft_content"):
                    await conversation_store.add_message(
                        channel, thread_ts, "assistant", result["draft_content"][:2000]
                    )

                if result.get("human_decision") == "":
                    await update_slack_workflow_status(workflow_id, "pending")
                    logger.info(
                        "slack_pipeline_paused",
                        workflow_id=workflow_id,
                        team_id=team_id,
                        channel=channel,
                        thread_ts=thread_ts,
                    )
                else:
                    await update_slack_workflow_status(workflow_id, "completed")
                    logger.info(
                        "slack_pipeline_completed",
                        workflow_id=workflow_id,
                        team_id=team_id,
                        channel=channel,
                    )

                if result.get("doc_id"):
                    await link_workflow_to_document(workflow_id, result["doc_id"])
            finally:
                structlog.contextvars.clear_contextvars()

    except Exception as e:
        logger.error("slack_pipeline_failed", error=str(e), exc_info=True)
        try:
            from src.integrations.slack import send_slack_message

            await send_slack_message(
                channel, f"Error processing request: {e}", thread_ts=ts
            )
        except Exception:
            logger.error("failed_to_post_slack_error")
