from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Stock Follow-Up"
    environment: str = "development"
    database_url: str = "sqlite:///./stock_followup.db"
    frontend_origin: str = "http://localhost:5173"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    dart_api_key: str | None = None
    dart_lookback_days: int = Field(default=30, ge=1, le=365)
    dart_max_disclosures_per_scan: int = Field(default=10, ge=1, le=100)

    news_max_items_per_tracking_item: int = Field(default=5, ge=1, le=20)
    news_min_relevance_score: float = Field(default=0.6, ge=0.0, le=1.0)
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = Field(default=300, ge=30)
    default_check_interval_minutes: int = Field(default=180, ge=15)


@lru_cache
def get_settings() -> Settings:
    return Settings()
