from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # CockroachDB
    cockroachdb_url: str

    # Requesty (OpenAI-compatible API)
    requesty_api_key: str = ""
    requesty_base_url: str = "https://api.requesty.ai/v1"
    llm_model: str = "tensorx/deepseek-v4-flash"
    embedding_model: str = "azure/openai/text-embedding-3-large@francecentral"

    # NVIDIA (per-stage provider switch; models aliased to dotted .env names)
    nvidia_api_key: SecretStr = SecretStr("")
    nvidia_glm_model: str = Field(
        default="z-ai/glm-5.2", validation_alias=AliasChoices("GLM_5.2_MODEL", "nvidia_glm_model")
    )
    nvidia_deepseek_v4_pro: str = Field(
        default="deepseek-ai/deepseek-v4-pro",
        validation_alias=AliasChoices("DEEPSEEK_V4_PRO_MODEL", "nvidia_deepseek_v4_pro"),
    )
    nvidia_deepseek_v4_flash: str = Field(
        default="deepseek-ai/deepseek-v4-flash",
        validation_alias=AliasChoices("DEEPSEEK_V4_FLASH_MODEL", "nvidia_deepseek_v4_flash"),
    )
    nvidia_minimax_m3: str = Field(
        default="minimax-ai/minimax-m3",
        validation_alias=AliasChoices("MINIMAX_M3_MODEL", "nvidia_minimax_m3"),
    )
    nvidia_kimi_k2_6: str = Field(
        default="moonshotai/kimi-k2.6",
        validation_alias=AliasChoices("KIMI_K2.6_MODEL", "nvidia_kimi_k2_6"),
    )

    # Slack
    slack_bot_token: SecretStr = SecretStr("")
    slack_signing_secret: SecretStr = SecretStr("")
    slack_app_token: SecretStr = SecretStr("")
    slack_client_id: str = ""
    slack_client_secret: SecretStr = SecretStr("")
    slack_redirect_uri: str = "https://grit-flagstone-recreate.ngrok-free.dev/api/slack/oauth/callback"

    # Discord
    discord_bot_token: SecretStr = SecretStr("")
    discord_public_key: SecretStr = SecretStr("")
    discord_guild_id: str = ""
    discord_app_id: str = ""

    # GitHub (Personal Access Token)
    github_token: SecretStr = SecretStr("")

    # GitHub App
    github_app_id: str = ""
    github_webhook_secret: SecretStr = SecretStr("")
    github_private_key_path: str = "./private-key.pem"
    github_app_slug: str = ""

    # Clerk (auth + organizations)
    clerk_publishable_key: str = ""
    clerk_secret_key: SecretStr = SecretStr("")
    clerk_signing_secret: SecretStr = SecretStr("")

    # Email (SendGrid)
    sendgrid_api_key: SecretStr = SecretStr("")
    sendgrid_from_email: str = "noreply@draftly.app"
    sendgrid_from_name: str = "Draftly"

    # Security
    secret_key: str = "change-me-in-production"

    # Per-stage LLM models (all routed through Requesty)
    research_model: str = "anthropic/claude-sonnet-4-6"
    review_model: str = "anthropic/claude-sonnet-4-6"
    rubric_grader_model: str = "anthropic/claude-haiku-4-5"
    rubric_max_iterations: int = 3
    rubric_max_content_chars: int = 20000
    rubric_max_run_tokens: int = 20000

    # LLM resilience
    llm_timeout: int = 60
    llm_max_retries: int = 2

    # Per-stage provider routing (requesty | nvidia). When *_nvidia_model is
    # empty, the stage falls back to the corresponding named model field above.
    research_provider: Literal["requesty", "nvidia"] = "requesty"
    review_provider: Literal["requesty", "nvidia"] = "requesty"
    rubric_grader_provider: Literal["requesty", "nvidia"] = "requesty"
    analysis_provider: Literal["requesty", "nvidia"] = "requesty"
    research_nvidia_model: str = ""
    review_nvidia_model: str = ""
    rubric_grader_nvidia_model: str = ""
    analysis_nvidia_model: str = ""

    # Hill-climbing (Loop 4)
    analysis_model: str = "tensorx/deepseek-v4-flash"
    trace_analysis_interval: int = 100
    auto_apply_improvements: bool = False
    trace_retention_days: int = 90

    # Event capture (dashboard telemetry)
    event_capture_enabled: bool = True
    event_flush_interval_seconds: float = 5.0
    event_buffer_size: int = 500
    event_retention_days: int = 90

    # Verification
    deterministic_verification_enabled: bool = True
    max_verification_issues_per_type: int = 10

    # App
    app_url: str = "http://localhost:5173"
    review_dashboard_url: str = "http://localhost:5173"
    uvicorn_host: str = "0.0.0.0"
    uvicorn_port: int = 8000
    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()  # type: ignore[call-arg]  # required fields come from .env

