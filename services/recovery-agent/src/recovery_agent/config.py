from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Same HS256 secret customer-service signs with (raw UTF-8 bytes, not base64-decoded)
    jwt_secret_key: str = Field(min_length=32)
    database_url: str = "postgresql://recovery_user:recovery_password@localhost:5439/recovery_db"

    order_service_url: str = "http://localhost:8085"
    payment_service_url: str = "http://localhost:8082"
    http_timeout_seconds: float = 5.0

    # Observer runs only when a broker is configured
    kafka_bootstrap_servers: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
