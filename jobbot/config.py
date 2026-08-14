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
    # Faz 1: multi-user
    supabase_url: str
    supabase_secret_key: str
    groq_api_key: str
    groq_model: str
    enrich_budget_per_run: int
    # Global remote track (additive personal feature)
    remote_track_enabled: bool
    remote_seen_path: str
    remote_max_per_run: int
    remote_telegram_chat_id: str
    remote_geo_filter: bool
    adzuna_app_id: str
    adzuna_app_key: str
    gemini_api_key: str
    gemini_model: str
    llm_judge_enabled: bool
    llm_judge_max: int

    @property
    def adzuna_enabled(self) -> bool:
        return bool(self.adzuna_app_id and self.adzuna_app_key)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def ai_enabled(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def supabase_enabled(self) -> bool:
        return bool(self.supabase_url and self.supabase_secret_key)


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
        supabase_url=os.getenv("SUPABASE_URL", "").strip(),
        supabase_secret_key=os.getenv("SUPABASE_SECRET_KEY", "").strip(),
        groq_api_key=os.getenv("GROQ_API_KEY", "").strip(),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip(),
        enrich_budget_per_run=int(os.getenv("ENRICH_BUDGET_PER_RUN", "60")),
        remote_track_enabled=os.getenv("REMOTE_TRACK_ENABLED", "true").strip().lower()
        in {"1", "true", "yes", "y", "on"},
        remote_seen_path=os.getenv("REMOTE_SEEN_PATH", "data/seen_remote.json"),
        remote_max_per_run=int(os.getenv("REMOTE_MAX_PER_RUN", "25")),
        remote_telegram_chat_id=os.getenv("REMOTE_TELEGRAM_CHAT_ID", "").strip(),
        remote_geo_filter=os.getenv("REMOTE_GEO_FILTER", "true").strip().lower()
        in {"1", "true", "yes", "y", "on"},
        adzuna_app_id=os.getenv("ADZUNA_APP_ID", "").strip(),
        adzuna_app_key=os.getenv("ADZUNA_APP_KEY", "").strip(),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-flash-latest").strip(),
        llm_judge_enabled=os.getenv("LLM_JUDGE_ENABLED", "true").strip().lower()
        in {"1", "true", "yes", "y", "on"},
        llm_judge_max=int(os.getenv("LLM_JUDGE_MAX", "60")),
    )
