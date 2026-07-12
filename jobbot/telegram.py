from __future__ import annotations

import html

import requests

from .config import Config
from .models import Classification, Job


def send_job(config: Config, job: Job, classification: Classification) -> None:
    if not config.telegram_enabled:
        raise RuntimeError("Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")

    text = format_message(job, classification)
    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": config.telegram_chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=25,
    )
    response.raise_for_status()


def format_message(job: Job, classification: Classification) -> str:
    concepts = ", ".join(classification.matched_concepts) or "profil siqnali"
    return "\n".join(
        [
            "<b>Yeni uyğun elan tapıldı</b>",
            "",
            f"<b>Vəzifə:</b> {html.escape(job.title)}",
            f"<b>Şirkət:</b> {html.escape(job.company or 'Qeyd edilməyib')}",
            f"<b>Uyğunluq:</b> {classification.confidence}% ({classification.label})",
            f"<b>Mənbə:</b> {html.escape(classification.source)}",
            "",
            "<b>Səbəb:</b>",
            html.escape(classification.reason),
            "",
            f"<b>Siqnallar:</b> {html.escape(concepts)}",
            "",
            f"<a href=\"{html.escape(job.url)}\">Elanı aç</a>",
        ]
    )
