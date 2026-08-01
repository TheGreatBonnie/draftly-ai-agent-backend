"""CockroachDB-backed InstallationStore for Slack Bolt."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import structlog
from slack_sdk.oauth.installation_store.async_installation_store import (
    AsyncInstallationStore,
)
from slack_sdk.oauth.installation_store.models.bot import Bot
from slack_sdk.oauth.installation_store.models.installation import Installation

from src.database import execute, fetch_one

logger = structlog.get_logger()


class CockroachInstallationStore(AsyncInstallationStore):
    """Persists Slack Bolt installations in CockroachDB."""

    @property
    def logger(self) -> Any:
        return logger

    async def async_save(self, installation: Installation) -> None:
        team_id = installation.team_id or ""
        user_id = installation.user_id or ""
        user_token = installation.user_token
        user_scopes = (
            ",".join(installation.user_scopes)
            if isinstance(installation.user_scopes, list)
            else installation.user_scopes
        )
        bot_scopes = (
            ",".join(installation.bot_scopes)
            if isinstance(installation.bot_scopes, list)
            else installation.bot_scopes
        )

        existing = await fetch_one(
            "SELECT id::text FROM slack_installations WHERE team_id = $1",
            team_id,
        )

        if existing:
            await execute(
                """UPDATE slack_installations
                   SET bot_user_id = $1, bot_token = $2, user_id = $3,
                       user_token = $4, team_name = $5, bot_scopes = $6,
                       user_scopes = $7, token_type = $8, updated_at = now()
                   WHERE team_id = $9""",
                installation.bot_user_id,
                installation.bot_token,
                user_id,
                user_token,
                installation.team_name,
                bot_scopes,
                user_scopes,
                installation.token_type,
                team_id,
            )
        else:
            await execute(
                """INSERT INTO slack_installations
                   (team_id, team_name, bot_user_id, bot_token,
                    bot_scopes, user_id, user_token, user_scopes, token_type)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
                team_id,
                installation.team_name,
                installation.bot_user_id,
                installation.bot_token,
                bot_scopes,
                user_id,
                user_token,
                user_scopes,
                installation.token_type,
            )

        logger.info(
            "slack_installation_saved",
            team_id=team_id,
            team_name=installation.team_name,
        )

    async def async_find_installation(
        self,
        enterprise_id: str | None,
        team_id: str | None,
        user_id: str | None = None,
        is_enterprise_install: bool | None = False,
    ) -> Installation | None:
        if team_id is None:
            return None

        if user_id:
            row = await fetch_one(
                """SELECT team_id, team_name, bot_user_id, bot_token, bot_scopes,
                          user_id, user_token, user_scopes, token_type, installed_at
                   FROM slack_installations
                   WHERE team_id = $1 AND user_id = $2""",
                team_id,
                user_id,
            )
        else:
            row = await fetch_one(
                """SELECT team_id, team_name, bot_user_id, bot_token, bot_scopes,
                          user_id, user_token, user_scopes, token_type, installed_at
                   FROM slack_installations
                   WHERE team_id = $1""",
                team_id,
            )

        if not row:
            return None

        return self._row_to_installation(row)

    async def async_find_bot(
        self,
        enterprise_id: str | None,
        team_id: str | None,
        is_enterprise_install: bool | None = False,
    ) -> Bot | None:
        if team_id is None:
            return None

        row = await fetch_one(
            """SELECT team_id, bot_user_id, bot_token, bot_scopes, installed_at
               FROM slack_installations
               WHERE team_id = $1""",
            team_id,
        )

        if not row:
            return None

        return Bot(
            team_id=row["team_id"],
            bot_id=row.get("bot_id", ""),
            bot_user_id=row["bot_user_id"],
            bot_token=row["bot_token"],
            bot_scopes=row["bot_scopes"].split(",") if row.get("bot_scopes") else [],
            installed_at=row["installed_at"],
        )

    async def async_delete_installation(
        self,
        enterprise_id: str | None,
        team_id: str | None,
        user_id: str | None = None,
    ) -> None:
        if team_id is None:
            return

        await execute(
            "DELETE FROM slack_installations WHERE team_id = $1",
            team_id,
        )
        logger.info("slack_installation_deleted", team_id=team_id)

    async def async_delete_bot(
        self,
        enterprise_id: str | None,
        team_id: str | None,
    ) -> None:
        if team_id is None:
            return

        await execute(
            "DELETE FROM slack_installations WHERE team_id = $1",
            team_id,
        )
        logger.info("slack_bot_deleted", team_id=team_id)

    async def async_delete_all(
        self,
        enterprise_id: str | None,
        team_id: str | None,
    ) -> None:
        if team_id is None:
            return

        await execute(
            "DELETE FROM slack_installations WHERE team_id = $1",
            team_id,
        )
        logger.info("slack_all_deleted", team_id=team_id)

    def _row_to_installation(self, row: Any) -> Installation:
        installed_at = row["installed_at"]
        if installed_at and not isinstance(installed_at, datetime):
            installed_at = datetime.fromisoformat(str(installed_at))

        bot_scopes = row["bot_scopes"]
        if isinstance(bot_scopes, str):
            bot_scopes = [s.strip() for s in bot_scopes.split(",") if s.strip()]

        user_scopes = row["user_scopes"]
        if isinstance(user_scopes, str):
            user_scopes = [s.strip() for s in user_scopes.split(",") if s.strip()]

        return Installation(
            team_id=row["team_id"],
            team_name=row["team_name"],
            bot_user_id=row["bot_user_id"],
            bot_token=row["bot_token"],
            bot_scopes=bot_scopes,
            user_id=row["user_id"],
            user_token=row["user_token"],
            user_scopes=user_scopes,
            token_type=row["token_type"],
            installed_at=installed_at,
        )


installation_store = CockroachInstallationStore()
