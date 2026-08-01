"""Draftly AI — Entry point for the application."""

import asyncio

import structlog
import uvicorn
from pydantic_settings import BaseSettings

from src.analytics.events import configure_logging
from src.integrations.slack_socket import should_use_socket_mode

configure_logging()

logger = structlog.get_logger()


class Settings(BaseSettings):
    uvicorn_host: str = "0.0.0.0"
    uvicorn_port: int = 8000


async def _run_http_server(host: str, port: int) -> None:
    config = uvicorn.Config("src.api.app:app", host=host, port=port)
    server = uvicorn.Server(config)
    await server.serve()


async def main() -> None:
    settings = Settings()
    tasks = [_run_http_server(settings.uvicorn_host, settings.uvicorn_port)]

    if should_use_socket_mode():
        from src.integrations.slack_socket import start_socket_mode

        logger.info("slack_socket_mode_enabled")
        tasks.append(start_socket_mode())

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
