from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


@dataclass(slots=True)
class Settings:
    flask_env: str = os.getenv("FLASK_ENV", "development")
    flask_debug: bool = os.getenv("FLASK_DEBUG", "1") == "1"
    serpapi_api_key: str | None = os.getenv("SERPAPI_API_KEY")
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "12"))


def get_settings() -> Settings:
    return Settings()
