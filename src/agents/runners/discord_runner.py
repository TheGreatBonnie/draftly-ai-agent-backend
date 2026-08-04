"""Discord pipeline runner — orchestrates the Draftly graph for Discord messages."""
from __future__ import annotations

import structlog
from langchain_cockroachdb import AsyncCockroachDBSaver  # type: ignore[import-untyped]
from langchain_core.runnables import RunnableConfig

from src.agents.graph import build_hybrid_graph
from src.agents.state import DocumentationState
from src.config import settings

logger = structlog.get_logger()


def build_discord_state(
    guild_id: str,
    channel_id: str,
    message_id: str,
    thread_id: str | None,
    text: str,
    user_id: str,
    org_id: str,
) -> DocumentationState:
    """Build initial DocumentationState from Discord message event."""
    graph_thread_id = f"discord-{channel_id}-{message_id}"

    return {
        "org_id": org_id,
        "source": "discord",
        "channel_id": channel_id,
        "thread_id": thread_id or message_id,
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
            "guild_id": guild_id,
            "channel_id": channel_id,
            "message_id": message_id,
            "thread_id": thread_id,
            "user_id": user_id,
        },
        "message_history": [],
        "question_type": "unknown",
        "research_skill": {},
        "investigation_plan": [],
        "rubric_status": {},
        "subagent_results": {},
        "_node_traces": [],
        "_trace_collected": False,
        "episode_id": "",
        "reflection_id": "",
        "_reflected": False,
    }


async def run_discord_pipeline(
    guild_id: str,
    channel_id: str,
    message_id: str,
    thread_id: str | None,
    text: str,
    user_id: str,
) -> None:
    """Orchestrate the full Draftly pipeline for a Discord support request."""
    from src.database import get_pool
    from src.integrations.discord import send_discord_message
    from src.memory.organizations import (
        get_org_by_discord,
        link_workflow_to_document,
        store_discord_workflow,
        update_discord_workflow_status,
    )

    await get_pool()

    try:
        logger.info(
            "discord_pipeline_started",
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            text_preview=text[:100],
        )

        org = await get_org_by_discord(guild_id)
        if not org:
            logger.error("discord_pipeline_org_not_found", guild_id=guild_id)
            try:
                await send_discord_message(
                    channel_id,
                    "⚠️ Draftly is not linked to your organization yet. "
                    "Please go to Draftly Settings → Discord Integration → "
                    "enter your Server ID to link this server.",
                )
            except Exception:
                logger.error("failed_to_post_org_not_found_message")
            return
        org_id = org["id"]

        state = build_discord_state(
            guild_id, channel_id, message_id, thread_id, text, user_id, org_id
        )
        config: RunnableConfig = {"configurable": {"thread_id": state["graph_thread_id"]}}

        from uuid import uuid4

        workflow_id = str(uuid4())
        state["workflow_id"] = workflow_id
        await store_discord_workflow(
            org_id=org_id,
            workflow_id=workflow_id,
            channel_id=channel_id,
            message_id=message_id,
            thread_id=thread_id,
            source_message=text[:2000],
        )
        await update_discord_workflow_status(workflow_id, "running")

        logger.info(
            "discord_pipeline_running",
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

                if result.get("human_decision") == "":
                    await update_discord_workflow_status(workflow_id, "pending")
                    logger.info(
                        "discord_pipeline_paused",
                        workflow_id=workflow_id,
                        guild_id=guild_id,
                        channel_id=channel_id,
                        message_id=message_id,
                    )
                else:
                    await update_discord_workflow_status(workflow_id, "completed")
                    logger.info(
                        "discord_pipeline_completed",
                        workflow_id=workflow_id,
                        guild_id=guild_id,
                        channel_id=channel_id,
                    )

                if result.get("doc_id"):
                    await link_workflow_to_document(workflow_id, result["doc_id"])
            finally:
                structlog.contextvars.clear_contextvars()

    except Exception as e:
        logger.error("discord_pipeline_failed", error=str(e), exc_info=True)
        try:
            from src.integrations.discord import send_discord_message

            target = thread_id or channel_id
            await send_discord_message(target, f"Error processing request: {e}")
        except Exception:
            logger.error("failed_to_post_discord_error")
