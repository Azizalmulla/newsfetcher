from functools import lru_cache
from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _to_psycopg_url(url: str) -> str:
    """Railway/Heroku style postgres:// → SQLAlchemy+psycopg3."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://") and "+psycopg" not in url.split("://", 1)[0]:
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    # Hosted Postgres often requires TLS; skip for local Compose.
    local_markers = ("localhost", "127.0.0.1", "@postgres:")
    if not any(marker in url for marker in local_markers) and "sslmode=" not in url:
        url = f"{url}&sslmode=require" if "?" in url else f"{url}?sslmode=require"
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "newsfetcher"
    log_level: str = "INFO"
    log_json: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"
    # Public no-auth dashboard + one-click demo ingest (turn off when multi-tenant SaaS hardens).
    demo_public_dashboard: bool = True
    demo_public_ingest: bool = True

    database_url: str = (
        "postgresql+psycopg://newsfetcher:newsfetcher_dev_password@localhost:5433/newsfetcher"
    )

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "newsfetcher"
    s3_region: str = "us-east-1"
    s3_force_path_style: bool = True
    storage_backend: str = "local"  # local|s3 — use s3 in Compose/prod
    storage_local_path: str = "/tmp/newsfetcher-storage"

    email_backend: str = "file"  # file|console|smtp
    email_file_dir: str = "/tmp/newsfetcher-mail"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@newsfetcher.local"
    smtp_use_tls: bool = True

    sentry_dsn: str = ""
    otel_exporter_otlp_endpoint: str = ""
    otel_service_name: str = "newsfetcher-api"
    otel_traces_exporter: str = "none"
    prometheus_metrics_enabled: bool = True

    ocr_provider: str = "mistral"
    mistral_api_key: str = ""
    mistral_ocr_model: str = Field(
        default="",
        description="Pinned Mistral OCR 4 model ID from official docs.",
    )

    embedding_provider: str = "voyage"
    embedding_model: str = "voyage-4-large"
    embedding_dimensions: int = 1024
    voyage_api_key: str = ""
    rerank_provider: str = "voyage"
    rerank_model: str = "rerank-2.5"
    # When voyage key is empty, providers fall back to local deterministic stubs.
    embedding_fallback_local: bool = True

    semantic_top_k: int = 20
    semantic_rerank_top_k: int = 10
    semantic_min_cosine: float = 0.45
    semantic_min_rerank: float = 0.10
    # Per-tenant thresholds can override these later via DB.

    # DeepSeek V4 via OpenAI-compatible API (https://api-docs.deepseek.com/).
    llm_provider: str = ""  # deepseek|...
    llm_model: str = "deepseek-v4-flash"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    # disabled for bulk work; enabled/high for ambiguous review escalation
    llm_thinking: str = "disabled"  # disabled|enabled

    # Logo recognition — local cascade by default; external only after cost approval.
    logo_provider: str = "local"  # local|external
    logo_external_api_key: str = ""
    logo_external_model: str = ""
    logo_external_endpoint: str = ""
    logo_min_confidence_default: float = 0.72

    # Social / X — official API only; live disabled until checklist + secrets.
    x_api_mode: str = "fixture"  # fixture|official
    x_api_live_enabled: bool = False
    x_api_bearer_token: str = ""
    x_api_base_url: str = "https://api.x.com/2"
    x_api_user_agent: str = "NewsFetcherBot/0.1 (+https://newsfetcher.local)"

    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    access_token_expire_minutes: int = 30

    @model_validator(mode="after")
    def _normalize_hosted_urls(self) -> Self:
        self.database_url = _to_psycopg_url(self.database_url)
        # Railway usually injects REDIS_URL only; mirror into Celery if still default-ish.
        if self.redis_url and self.redis_url != "redis://localhost:6379/0":
            if self.celery_broker_url == "redis://localhost:6379/0":
                self.celery_broker_url = self.redis_url
            if self.celery_result_backend == "redis://localhost:6379/1":
                self.celery_result_backend = self.redis_url
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
