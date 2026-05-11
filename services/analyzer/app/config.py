"""Настройки Анализатора. Атрошенко Б. С."""

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DOTENV = os.path.join(os.path.dirname(__file__), ".env")


class Settings(BaseSettings):
    DB_USER: str = Field(default="user")
    DB_PASS: str = Field(default="user")
    DB_NAME: str = Field(default="postgresql")
    DB_HOST: str = Field(description="Хост базки", default="postgresql")
    DB_PORT: int = Field(default=5432)

    PORT_ANALYZER: int = Field(default=8001)

    CACHE_TTL: int = Field(description="Время живучести ключей в Redis", default=3600)

    REDIS_URL: str = "redis://localhost:6379"
    KAFKA_BOOTSTRAP: str = "localhost:9092"
    KAFKA_TOPIC: str = "reviews.raw"
    CRM_URL: str = "http://localhost:8000"
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    LANGFUSE_HOST: str = "http://localhost:3000"
    LANGFUSE_PUBLIC_KEY: str = Field(default="")
    LANGFUSE_SECRET_KEY: str = Field(default="")
    POLL_INTERVAL_SEC: int = 30
    ANOMALY_ZSCORE_THRESHOLD: float = 2.5
    ANOMALY_KL_THRESHOLD: float = 0.5

    @property
    def database_url(self) -> str:
        """DSN для asyncpg (прямое подключение)."""
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def async_database_url(self) -> str:
        """DSN для SQLAlchemy / Alembic."""
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    model_config = SettingsConfigDict(env_file=DOTENV)


settings = Settings()
