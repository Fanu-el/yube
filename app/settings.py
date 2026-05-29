from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_token: str = Field(..., env="TELEGRAM_TOKEN")
    youtube_api_key: str = Field(..., env="YOUTUBE_API_KEY")
    redis_url: str = Field("redis://localhost:6379/0", env="REDIS_URL")
    webhook_url: Optional[str] = Field(None, env="WEBHOOK_URL")
    webhook_path: str = Field("/webhook", env="WEBHOOK_PATH")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
