from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


class Settings(BaseModel):
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./stackforge.db")
    cors_origins: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174",
        ).split(",")
        if o.strip()
    ]
    steam_api_key: str | None = os.getenv("STEAM_API_KEY") or None
    faceit_api_key: str | None = os.getenv("FACEIT_API_KEY") or None
    leetify_api_key: str | None = os.getenv("LEETIFY_API_KEY") or None
    provider_timeout_seconds: float = float(os.getenv("PROVIDER_TIMEOUT_SECONDS", "4.0"))
    provider_cache_ttl_seconds: int = int(os.getenv("PROVIDER_CACHE_TTL_SECONDS", "900"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
