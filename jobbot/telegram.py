from __future__ import annotations

import html

import requests

from .config import Config
from .models import Classification, Job

# Telegram hard limit is 4096 chars per message; stay well under it.
MAX_MESSAGE_CHARS = 3800


def send_matches(config: Config, matches: list[tuple[Job, Classification]]) -> None:
    """Send all matches in as few Telegram messages as possible (batched)."""
    if not config.telegram_enabled:
        raise RuntimeError("Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
    if not matches:
        return

    for text in build_batch_messages(matches):
        _send(config, text)


def build_batch_messages(matches: list[tuple[Job, Classification]]) -> list[str]:
    blocks = [format_job_block(index, job, cls) for index, (job, cls) in enumerate(matches, 1)]

    # Pack blocks into as few chunks as possible (Telegram message size limit).
    chunks: list[list[str]] = [[]]
    length = 0
    for block in blocks:
        extra = len(block) + 2
        if chunks[-1] and length + extra > MAX_MESSAGE_CHARS:
            chunks.append([])
            length = 0
        chunks[-1].append(block)
        length += extra

    total = len(chunks)
    messages: list[str] = []
    for part, chunk in enumerate(chunks, 1):
        header = f"🔔 <b>{len(matches)} yeni uyğun elan tapıldı</b>"
        if total > 1:
            header += f" (bölüm {part}/{total})"
        messages.append("\n\n".join([header, *chunk]))
    return messages


def format_job_block(index: int, job: Job, classification: Classification) -> str:
    lines = [
        f"<b>{index}. {html.escape(job.title)}</b>",
        f"🏢 {html.escape(job.company or 'Qeyd edilməyib')}",
        f"✅ {classification.confidence}% {classification.label}",
    ]
    deadline = format_date(job.deadline)
    if deadline:
        lines.append(f"⏳ Son müraciət: {deadline}")
    if classification.matched_concepts:
        lines.append(f"🏷 {html.escape(', '.join(classification.matched_concepts))}")
    lines.append(f"🔗 <a href=\"{html.escape(job.url)}\">Elanı aç</a>")
    return "\n".join(lines)


def format_date(value: str) -> str:
    """Turn an ISO datetime like '2026-08-08T00:00:00+04:00' into '08.08.2026'."""
    if not value:
        return ""
    date_part = value.split("T", 1)[0]
    pieces = date_part.split("-")
    if len(pieces) == 3:
        year, month, day = pieces
        return f"{day}.{month}.{year}"
    return value


def _send(config: Config, text: str) -> None:
    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
    response = requests.post(
        url,
        json={
            "chat_id": config.telegram_chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=25,
    )
    response.raise_for_status()
