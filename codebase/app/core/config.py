from asyncio import Semaphore
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(dotenv_path=".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    discord_bot_token: Optional[str] = None
    google_api_key: Optional[str] = None
    semaphore: Semaphore = Semaphore(1)


settings = Settings()