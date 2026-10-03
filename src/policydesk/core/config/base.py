"""Application settings.

One class reads the environment: ``Settings`` (a ``BaseSettings``).
Everything else (``DatabaseSettings``, ``PoolSettings`` ...) is a plain data
group (a ``BaseModel``) — a labeled folder inside the one big ``Settings`` box.
These folders never read env on their own and never touch the database.

Env keys are nested with ``__``:  ``DB__POOL__SIZE`` -> ``settings.db.pool.size``.
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Tests and CI can set ENV_FILE=.env.test to read a different file.
_ENV_FILE = os.environ.get("ENV_FILE", ".env")


class PoolSettings(BaseModel):
    """Database connection pool. Read from ``DB__POOL__*``."""

    size: int = 3
    max_overflow: int = 2
    timeout: int = 10  # seconds to wait for a free connection
    recycle: int = 1800  # seconds before a connection is replaced


class DatabaseSettings(BaseModel):
    """Database connection. Read from ``DB__*``."""

    host: str = "localhost"
    port: int = 5432
    name: str = "policydesk"
    user: str = "app"
    password: SecretStr = SecretStr("app")
    driver: str = "postgresql+asyncpg"
    pool: PoolSettings = Field(default_factory=PoolSettings)
    statement_timeout_ms: int = 10_000
    idle_tx_timeout_ms: int = 30_000
    # TODO:  Pool budget (lesson 13), used when we build the engine in M0.4:
    #  workers x (pool.size + pool.max_overflow) + workers + admin < max_connections


class MailSettings(BaseModel):
    """Email sending. Read from ``MAIL__*``."""

    backend: Literal["smtp", "console", "fake"] = "smtp"
    host: str = "mailhog"
    port: int = 1025


class StripeSettings(BaseModel):
    """Stripe keys. Read from ``STRIPE__*``."""

    secret_key: SecretStr = SecretStr("sk_test_change_me")
    webhook_secret: SecretStr = SecretStr("whsec_change_me")


class PaymentSettings(BaseModel):
    """Which payment provider to use. Read from ``PAYMENT__*``."""

    provider: Literal["fake", "stripe"] = "fake"


class Settings(BaseSettings):
    """The one big settings object. Built once by ``get_settings()``."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["local", "test", "staging", "prod"] = "local"
    debug: bool = True
    log_level: str = "DEBUG"
    secret_key: SecretStr = SecretStr("change-me")
    cors_origins: str = "http://localhost:5173"

    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    mail: MailSettings = Field(default_factory=MailSettings)
    stripe: StripeSettings = Field(default_factory=StripeSettings)
    payment: PaymentSettings = Field(default_factory=PaymentSettings)

    @property
    def cors_origins_list(self) -> list[str]:
        """Split the comma string into a clean list for CORS middleware."""
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _refuse_live_stripe_outside_prod(self) -> Settings:
        """a live Stripe key is only allowed in prod."""
        key = self.stripe.secret_key.get_secret_value()
        if key.startswith("sk_live_") and self.environment != "prod":
            raise ValueError(
                "STRIPE__SECRET_KEY starts with 'sk_live_' but ENVIRONMENT is not 'prod'."
            )
        return self
