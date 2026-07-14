"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime settings for the Hostel Checkout API."""

    app_name: str = Field(
        default="Hostel Checkout API",
        validation_alias="APP_NAME",
    )
    app_env: Literal["development", "testing", "production"] = Field(
        default="development",
        validation_alias="APP_ENV",
    )
    debug: bool = Field(default=False, validation_alias="DEBUG")
    api_prefix: str = Field(default="/api", validation_alias="API_PREFIX")
    cors_origins: list[str] = Field(
        default_factory=list,
        validation_alias="CORS_ORIGINS",
    )

    database_url: str = Field(validation_alias="DATABASE_URL")
    database_connect_timeout_seconds: int = Field(
        default=5,
        ge=1,
        le=60,
        validation_alias="DATABASE_CONNECT_TIMEOUT_SECONDS",
    )
    secret_key: SecretStr = Field(validation_alias="SECRET_KEY")
    algorithm: Literal["HS256", "HS384", "HS512"] = Field(
        default="HS256",
        validation_alias="ALGORITHM",
    )
    access_token_expire_minutes: int = Field(
        default=30,
        gt=0,
        validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> str:
        """Normalize PostgreSQL URLs to SQLAlchemy's psycopg 3 dialect."""

        url = str(value).strip()
        if url.startswith("postgres://"):
            url = f"postgresql+psycopg://{url.removeprefix('postgres://')}"
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" f"{url.removeprefix('postgresql://')}"

        if not url.startswith("postgresql+psycopg://"):
            raise ValueError(
                "DATABASE_URL must use PostgreSQL through the psycopg driver"
            )
        return url

    @field_validator("api_prefix")
    @classmethod
    def normalize_api_prefix(cls, value: str) -> str:
        """Ensure the API prefix is absolute and has no trailing slash."""

        prefix = value.strip()
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        return prefix.rstrip("/") or "/api"

    @field_validator("cors_origins", mode="after")
    @classmethod
    def normalize_cors_origins(cls, value: list[str]) -> list[str]:
        """Normalize origins before they are passed to CORS middleware."""

        origins = [origin.strip().rstrip("/") for origin in value]
        if any(not origin for origin in origins):
            raise ValueError("CORS_ORIGINS cannot contain an empty origin")
        return origins

    @model_validator(mode="after")
    def validate_production_security(self) -> Self:
        """Reject known-insecure secrets and wildcard CORS in production."""

        if self.app_env != "production":
            return self

        secret = self.secret_key.get_secret_value()
        insecure_markers = ("replace", "change", "development", "example")
        if len(secret.encode("utf-8")) < 32 or any(
            marker in secret.lower() for marker in insecure_markers
        ):
            raise ValueError("SECRET_KEY must be a strong production secret")
        if self.debug:
            raise ValueError("DEBUG must be false in production")
        if self.api_prefix != "/api":
            raise ValueError("API_PREFIX must be '/api' in production")
        if "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS cannot contain '*' in production")
        if any(not origin.startswith("https://") for origin in self.cors_origins):
            raise ValueError("CORS_ORIGINS must use HTTPS origins in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide immutable-style settings instance."""

    return Settings()
