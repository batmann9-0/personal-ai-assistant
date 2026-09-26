"""
Central configuration for the Personal AI Assistant.
Loads settings from environment variables / a .env file.
"""
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SKILLS_DIR = DATA_DIR / "skills"
DB_PATH = DATA_DIR / "memory.sqlite3"
JOBS_PATH = DATA_DIR / "jobs.json"

DATA_DIR.mkdir(exist_ok=True)
SKILLS_DIR.mkdir(exist_ok=True, parents=True)


@dataclass
class Settings:
    provider: str = os.getenv("LLM_PROVIDER", "anthropic")          # anthropic | openai | openrouter
    model: str = os.getenv("LLM_MODEL", "claude-sonnet-4-6")
    api_key: str = os.getenv("LLM_API_KEY", "")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    discord_token: str = os.getenv("DISCORD_BOT_TOKEN", "")

    web_host: str = os.getenv("WEB_HOST", "0.0.0.0")
    web_port: int = int(os.getenv("WEB_PORT", "8000"))

    timezone: str = os.getenv("TIMEZONE", "UTC")
    max_history_messages: int = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))


settings = Settings()
