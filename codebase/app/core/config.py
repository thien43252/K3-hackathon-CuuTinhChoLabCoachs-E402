from asyncio import Semaphore
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(dotenv_path=".env")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    discord_bot_token: Optional[str] = None
    semaphore: Semaphore = Semaphore(1)

    database_path: str = str(BASE_DIR / "data" / "app.db")
    upload_dir: str = str(BASE_DIR / "data" / "uploads" / "materials")


settings = Settings()