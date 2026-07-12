from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    base_url: str
    list_url: str
    telegram_bot_token: str
    telegram_chat_id: str
    openai_api_key: str
    openai_model: str
    send_maybe_matches: bool
    max_jobs_per_run: int
    seen_db_path: str

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def ai_enabled(self) -> bool:
        return bool(self.openai_api_key)


def load_config() -> Config:
    load_dotenv()

    return Config(
        base_url=os.getenv("JOBSEARCH_BASE_URL", "https://jobsearch.az").rstrip("/"),
        list_url=os.getenv("JOBSEARCH_LIST_URL", "https://jobsearch.az/vacancies"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip(),
        send_maybe_matches=os.getenv("SEND_MAYBE_MATCHES", "true").strip().lower()
        in {"1", "true", "yes", "y", "on"},
        max_jobs_per_run=int(os.getenv("MAX_JOBS_PER_RUN", "150")),
        seen_db_path=os.getenv("SEEN_DB_PATH", "data/seen_jobs.json"),
    )
