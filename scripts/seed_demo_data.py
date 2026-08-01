"""Seed CockroachDB with demo data for the hackathon demo."""

import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.database import fetch_one, get_pool
from src.memory.reviewers import create_reviewer
from src.memory.vector_store import store_embedding

DEMO_ORG = {
    "name": "Acme Corp",
    "slack_workspace_id": "T123456",
    "discord_guild_id": "789012",
    "github_org": "acme-corp",
}

# Org that receives GitHub webhooks — reviewer must exist here
GITHUB_WEBHOOK_ORG = "TheGreatBonnie"

SUPPORT_THREADS = [
    {
        "source": "slack",
        "title": "How to configure CockroachDB MCP with Claude Code",
        "question": "How do I set up CockroachDB MCP server to work with Claude Code? "
        "I keep getting connection errors.",
    },
    {
        "source": "slack",
        "title": "CockroachDB vector search performance",
        "question": "Our vector searches are slow with 1M embeddings. "
        "How do we optimize the index?",
    },
    {
        "source": "discord",
        "title": "Migrating from PostgreSQL to CockroachDB",
        "question": "What's the best approach for migrating a PostgreSQL database "
        "to CockroachDB? Any gotchas?",
    },
    {
        "source": "github",
        "title": "CockroachDB connection pooling best practices",
        "question": "What connection pool settings should we use for CockroachDB "
        "in production with asyncpg?",
    },
    {
        "source": "slack",
        "title": "CockroachDB cloud backup configuration",
        "question": "How do I set up automated backups for my CockroachDB Cloud cluster?",
    },
    {
        "source": "discord",
        "title": "Debugging slow queries in CockroachDB",
        "question": "Some queries that were fast in PostgreSQL are slow in CockroachDB. "
        "How do I debug this?",
    },
    {
        "source": "slack",
        "title": "CockroachDB multi-region setup",
        "question": "How do I configure a multi-region CockroachDB cluster "
        "for low-latency reads?",
    },
    {
        "source": "github",
        "title": "CockroachDB schema design for time-series data",
        "question": "What's the recommended schema pattern for time-series data "
        "in CockroachDB?",
    },
]


async def _get_or_create_org(github_org: str) -> str:
    """Get existing org by github_org, or create one."""
    row = await fetch_one(
        "SELECT id::text FROM organizations WHERE github_org = $1",
        github_org,
    )
    if row:
        return row["id"]

    row = await fetch_one(
        "INSERT INTO organizations (name, github_org) VALUES ($1, $2) RETURNING id::text",
        github_org,
        github_org,
    )
    print(f"Created org: {github_org} ({row['id']})")
    return row["id"]


async def seed():
    pool = await get_pool()

    # Ensure reviewer exists for the GitHub webhook org
    webhook_org_id = await _get_or_create_org(GITHUB_WEBHOOK_ORG)

    existing_reviewer = await fetch_one(
        "SELECT id::text FROM reviewers WHERE org_id = $1 AND is_active = true",
        webhook_org_id,
    )
    if not existing_reviewer:
        reviewer = await create_reviewer(
            org_id=webhook_org_id,
            name="Default Reviewer",
            slack_user_id="U0BJABA1AH0",
            notify_slack=True,
        )
        print(f"Created reviewer: {reviewer['name']} (Slack: {reviewer['slack_user_id']})")
    else:
        print(f"Reviewer already exists for org {GITHUB_WEBHOOK_ORG}")

    # Create demo support threads for Acme Corp
    acme_org_id = await _get_or_create_org(DEMO_ORG["github_org"])

    for thread in SUPPORT_THREADS:
        row = await fetch_one(
            "INSERT INTO support_threads "
            "(org_id, source, channel_id, thread_id, title, question_summary, status) "
            "VALUES ($1, $2, $3, $4, $5, $6, 'resolved') RETURNING id::text",
            acme_org_id,
            thread["source"],
            f"C{random.randint(100, 999)}",
            f"T{random.randint(1000, 9999)}",
            thread["title"],
            thread["question"],
        )
        assert row is not None
        thread_id = row["id"]

        await store_embedding(
            org_id=acme_org_id,
            content_type="support_thread",
            content_id=thread_id,
            content_text=f"{thread['title']}\n\n{thread['question']}",
        )
        print(f"  Created thread + embedding: {thread['title'][:50]}")

    # Create demo documentation
    docs = [
        {
            "title": "CockroachDB MCP Server Setup Guide",
            "content": (
                "# Setting Up CockroachDB MCP\n\n"
                "## Prerequisites\n"
                "- CockroachDB Cloud account\n"
                "- Claude Code installed\n\n"
                "## Steps\n"
                "1. Go to Cloud Console\n"
                "2. Navigate to MCP section\n"
                "3. Copy connection string\n"
                "4. Configure in Claude Code\n\n"
                "## Troubleshooting\n"
                "- Check SSL certificates\n"
                "- Verify network access"
            ),
            "doc_type": "howto",
        },
        {
            "title": "Vector Search Optimization",
            "content": (
                "# Optimizing CockroachDB Vector Search\n\n"
                "## Index Configuration\n"
                "Use HNSW index for better performance:\n"
                "```sql\n"
                "CREATE INDEX ON embeddings USING vector "
                "(embedding vector_cosine_ops) WITH (lists = 100);\n"
                "```\n\n"
                "## Query Optimization\n"
                "- Limit results with LIMIT\n"
                "- Use WHERE clauses to filter before vector search"
            ),
            "doc_type": "tutorial",
        },
    ]

    # Company knowledge base docs (used as context for AI-generated solutions)
    company_docs = [
        {
            "title": "Internal Authentication & Authorization Guide",
            "content": (
                "# Authentication & Authorization\n\n"
                "## Overview\n"
                "Draftly uses Clerk for authentication and organization-based multi-tenancy.\n\n"
                "## JWT Structure\n"
                "Every request includes a Clerk JWT with these claims:\n"
                "- `sub`: Clerk user ID\n"
                "- `org_id`: Organization ID (clerk_org_id)\n"
                "- `org_role`: Role within the org (`org:admin` or `org:member`)\n\n"
                "## Authorization Rules\n"
                "- **Reading docs/reviews**: Any authenticated user in the org\n"
                "- **Creating reviewers**: Admin only (`org:admin`)\n"
                "- **Approving/rejecting reviews**: Assigned reviewers only\n"
                "- **Ingesting knowledge**: Any authenticated user in the org\n\n"
                "## API Token Flow\n"
                "1. Frontend obtains Clerk JWT via `@clerk/react`\n"
                "2. JWT sent as `Authorization: Bearer <token>` header\n"
                "3. Backend verifies via JWKS endpoint at `/.well-known/jwks.json`\n"
                "4. Token decoded to extract `user_id`, `org_id`, `org_role`"
            ),
            "doc_type": "reference",
        },
        {
            "title": "CockroachDB Schema Design Patterns",
            "content": (
                "# Schema Design Patterns\n\n"
                "## UUID Primary Keys\n"
                "All tables use `UUID PRIMARY KEY DEFAULT gen_random_uuid()` to avoid hotspot issues.\n\n"
                "## Vector Indexes\n"
                "Embeddings use HNSW index for approximate nearest neighbor search:\n"
                "```sql\n"
                "CREATE VECTOR INDEX idx_embeddings_vector ON embeddings (embedding vector_cosine_ops);\n"
                "```\n\n"
                "## Foreign Key Conventions\n"
                "- `org_id STRING REFERENCES organizations(clerk_org_id)` — multi-tenant isolation\n"
                "- `ON DELETE CASCADE` — org deletion removes all child data\n\n"
                "## JSONB Fields\n"
                "Used for flexible data: `participants`, `repositories`, `published_to`, `metadata`.\n"
                "Always store with `::jsonb` cast on insert."
            ),
            "doc_type": "reference",
        },
        {
            "title": "Agent Pipeline Architecture",
            "content": (
                "# Agent Pipeline Architecture\n\n"
                "## Overview\n"
                "Draftly uses LangGraph to orchestrate a multi-step documentation pipeline.\n\n"
                "## Pipeline Flow\n"
                "```\n"
                "ingest → memory_retrieve → research → synthesize → write_docs → ai_review\n"
                "                                                              |\n"
                "                                                    human_review (interrupt)\n"
                "                                                              |\n"
                "                                                    publish / reject / revise\n"
                "```\n\n"
                "## Node Descriptions\n"
                "- **ingest**: Creates support thread, classifies complexity, selects doc type\n"
                "- **memory_retrieve**: Searches 4 memory sources (semantic, episodic, org, reviewer)\n"
                "- **research**: Web search + investigation plan execution\n"
                "- **synthesize**: Merges research into JSON knowledge package\n"
                "- **write_docs**: Generates markdown documentation via LLM\n"
                "- **ai_review**: Rubric-based quality evaluation\n"
                "- **human_review**: Creates review session, notifies reviewers, pauses graph\n"
                "- **publish**: Updates doc status, stores embeddings, replies to source\n\n"
                "## State Management\n"
                "All state lives in `DocumentationState` TypedDict. Checkpointer persists\n"
                "graph state to CockroachDB for HITL resume across requests."
            ),
            "doc_type": "reference",
        },
        {
            "title": "Troubleshooting Common Issues",
            "content": (
                "# Troubleshooting Guide\n\n"
                "## Connection Errors\n"
                "**Symptom**: `connection refused` or `SSL error` when connecting to CockroachDB.\n"
                "**Fix**: Verify `COCKROCKDB_URL` env var includes `?sslmode=verify-full` and valid certs.\n\n"
                "## Embedding Failures\n"
                "**Symptom**: `store_embedding` raises timeout or API error.\n"
                "**Fix**: Check `REQUESTY_API_KEY` is valid. Embeddings use OpenAI-compatible API at\n"
                "the configured base URL. Timeout is 30s per embedding call.\n\n"
                "## Graph Stuck in Interrupt\n"
                "**Symptom**: Workflow shows `running` but no progress.\n"
                "**Fix**: Check `review_sessions` for pending reviews. Resume via\n"
                "`POST /api/reviews/{id}/decide` with approve/reject/revise.\n\n"
                "## GitHub Webhook Not Firing\n"
                "**Symptom**: Issues opened but no docs generated.\n"
                "**Fix**: Verify GitHub App installation, check webhook secret in env vars,\n"
                "and confirm `POST /api/github/webhook` is reachable from GitHub."
            ),
            "doc_type": "troubleshooting",
        },
        {
            "title": "Frequently Asked Questions",
            "content": (
                "# FAQ\n\n"
                "## What is Draftly?\n"
                "Draftly is an autonomous documentation engineering system with persistent agentic memory.\n"
                "It generates accurate technical documentation from support conversations.\n\n"
                "## How does the AI know my internal systems?\n"
                "Upload company docs to the Knowledge Base. The AI retrieves relevant context via\n"
                "vector similarity search before generating documentation.\n\n"
                "## What review process is required?\n"
                "Every generated doc goes through AI review (rubric-based) then human review.\n"
                "Reviewers are notified via Slack, Discord, or email.\n\n"
                "## Can I customize the doc types?\n"
                "Yes. Supported types: `howto`, `faq`, `tutorial`, `troubleshooting`, `reference`.\n"
                "The AI selects the best type based on the question content.\n\n"
                "## How are embeddings stored?\n"
                "CockroachDB with distributed vector index (`VECTOR(3072)`). Uses HNSW algorithm\n"
                "for approximate nearest neighbor search with cosine similarity."
            ),
            "doc_type": "faq",
        },
    ]

    for doc in docs:
        row = await fetch_one(
            "INSERT INTO documentation "
            "(org_id, title, content, doc_type, status, confidence_score) "
            "VALUES ($1, $2, $3, $4, 'approved', 0.85) RETURNING id::text",
            acme_org_id,
            doc["title"],
            doc["content"],
            doc["doc_type"],
        )
        assert row is not None
        doc_id = row["id"]

        await store_embedding(
            org_id=acme_org_id,
            content_type="documentation",
            content_id=doc_id,
            content_text=f"{doc['title']}\n\n{doc['content']}",
        )
        print(f"  Created doc + embedding: {doc['title']}")

    # Seed company knowledge base docs
    for doc in company_docs:
        row = await fetch_one(
            "INSERT INTO documentation "
            "(org_id, title, content, doc_type, status, confidence_score) "
            "VALUES ($1, $2, $3, $4, 'approved', 1.0) RETURNING id::text",
            acme_org_id,
            doc["title"],
            doc["content"],
            doc["doc_type"],
        )
        assert row is not None
        doc_id = row["id"]

        await store_embedding(
            org_id=acme_org_id,
            content_type="documentation",
            content_id=doc_id,
            content_text=f"{doc['title']}\n\n{doc['content']}",
            metadata={"source": "knowledge_upload", "doc_type": doc["doc_type"]},
        )
        print(f"  Created knowledge doc + embedding: {doc['title']}")

    print(f"\n✅ Seeded {len(SUPPORT_THREADS)} threads + {len(docs)} docs + {len(company_docs)} knowledge docs")
    print(f"   Webhook org ({GITHUB_WEBHOOK_ORG}): {webhook_org_id}")
    print(f"   Demo org ({DEMO_ORG['github_org']}): {acme_org_id}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(seed())
