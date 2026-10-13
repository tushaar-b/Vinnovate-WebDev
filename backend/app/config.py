import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    ENVIRONMENT: str = Field(default="development")
    TEST_MODE: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")

    API_HOST: str = Field(default="127.0.0.1")
    API_PORT: int = Field(default=8000)

    DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/changedetection"
    )
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    DATA_DIR: str = Field(default="data/screenshots")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
