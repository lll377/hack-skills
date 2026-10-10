from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True, slots=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8765
    db_path: Path = Path("data/memory.db")
    short_ttl_days: int = 7
    distill_interval_seconds: int = 86400
    instant_max_chars: int = 24000
    working_text_limit: int = 15
    openai_api_key: str = "sk-EHjIqJw1WnWPZP9OTR4eWXysrXL7A4mrpmVhWYAenAsG9aNb"
    openai_base_url: str = "https://api.ntrapi.cn/v1"
    openai_model: str = "gpt-5.4"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            host=os.getenv("MEMORY_HOST", "127.0.0.1"),
            port=_env_int("MEMORY_PORT", 8765),
            db_path=Path(os.getenv("MEMORY_DB_PATH", "data/memory.db")),
            short_ttl_days=_env_int("MEMORY_SHORT_TTL_DAYS", 7),
            distill_interval_seconds=_env_int(
                "MEMORY_DISTILL_INTERVAL_SECONDS", 86400
            ),
            instant_max_chars=_env_int("MEMORY_INSTANT_MAX_CHARS", 24000),
            working_text_limit=_env_int("MEMORY_WORKING_TEXT_LIMIT", 15),
            openai_api_key=os.getenv("MEMORY_OPENAI_API_KEY", ""),
            openai_base_url=os.getenv(
                "MEMORY_OPENAI_BASE_URL", "https://api.openai.com/v1"
            ).rstrip("/"),
            openai_model=os.getenv("MEMORY_OPENAI_MODEL", "gpt-4.1-mini"),
        )

    def validate(self) -> None:
        if not 0 <= self.port <= 65535:
            raise ValueError("MEMORY_PORT must be between 0 and 65535")
        if self.short_ttl_days < 1:
            raise ValueError("MEMORY_SHORT_TTL_DAYS must be positive")
        if self.distill_interval_seconds < 10:
            raise ValueError("MEMORY_DISTILL_INTERVAL_SECONDS must be at least 10")
        if self.instant_max_chars < 1000:
            raise ValueError("MEMORY_INSTANT_MAX_CHARS must be at least 1000")
