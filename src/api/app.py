from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.analytics.events import (
    configure_logging,
    start_flusher,
    start_retention,
    stop_flusher,
    stop_retention,
)
from src.api.routes import (
    activity,
    clerk,
    discord,
    docs,
    github,
    improvements,
    knowledge,
    memory,
    review,
    reviewers,
    reviews,
    slack,
)
from src.database import close_pool, get_pool

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    import asyncio

    from src.agents.graph import set_trace_collector
    from src.analytics.hill_climber import HillClimber
    from src.analytics.traces import TraceCollector
    from src.config import settings
    from src.integrations.discord_gateway import gateway

    await get_pool()
    await start_flusher()
    await start_retention()

    # Initialize trace collection
    trace_collector = TraceCollector(
        flush_threshold=settings.trace_analysis_interval,
    )
    hill_climber = HillClimber(
        trace_collector=trace_collector,
        org_id="",
        analysis_interval=settings.trace_analysis_interval,
    )
    set_trace_collector(trace_collector)

    async def on_flush() -> None:
        if await hill_climber.should_analyze():
            asyncio.create_task(hill_climber.run_analysis_cycle())

    trace_collector.set_on_flush_callback(on_flush)

    # Start Discord Gateway WebSocket in background if configured
    discord_task = None
    if settings.discord_bot_token.get_secret_value():
        discord_task = asyncio.create_task(gateway.start())

    yield

    # Flush remaining traces on shutdown
    await trace_collector.flush()

    # Stop Discord Gateway on shutdown
    await gateway.stop()
    if discord_task:
        discord_task.cancel()

    # Flush remaining events on shutdown
    await stop_flusher()
    await stop_retention()

    await close_pool()


app = FastAPI(title="Draftly Review Dashboard", lifespan=lifespan)

app.include_router(reviews.router, prefix="/api/reviews", tags=["reviews"])
app.include_router(reviewers.router, prefix="/api/reviewers", tags=["reviewers"])
app.include_router(review.router, prefix="/api/review", tags=["review"])
app.include_router(docs.router, prefix="/api/docs", tags=["docs"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
app.include_router(github.router, prefix="/api/github", tags=["github"])
app.include_router(clerk.router, prefix="/api/clerk", tags=["clerk"])
app.include_router(slack.router, prefix="/api/slack", tags=["slack"])
app.include_router(discord.router, prefix="/api/discord", tags=["discord"])
app.include_router(activity.router, prefix="/api/activity", tags=["activity"])
app.include_router(improvements.router, prefix="/api", tags=["improvements"])

DIST_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="static-assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def serve_spa(request: Request, full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        file_path = DIST_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(DIST_DIR / "index.html")
