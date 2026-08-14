from __future__ import annotations

import html

import requests

from .config import Config
from .models import Classification, Job

# Telegram hard limit is 4096 chars per message; stay well under it.
MAX_MESSAGE_CHARS = 3800


def api_url(config: Config, method: str) -> str:
    return f"https://api.telegram.org/bot{config.telegram_bot_token}/{method}"


def send_matches(config: Config, matches: list[tuple[Job, Classification]], chat_id: str | int | None = None) -> None:
    """Send all matches in as few Telegram messages as possible (batched)."""
    if not config.telegram_enabled:
        raise RuntimeError("Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")
    if not matches:
        return

    for text in build_batch_messages(matches):
        _send(config, text, chat_id=chat_id)


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


def send_text(config: Config, chat_id: str | int, text: str) -> None:
    _send(config, text, chat_id=chat_id)


def _send(config: Config, text: str, chat_id: str | int | None = None) -> None:
    response = requests.post(
        api_url(config, "sendMessage"),
        json={
            "chat_id": chat_id if chat_id is not None else config.telegram_chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=25,
    )
    response.raise_for_status()


# ---------- inbound (multi-user onboarding) ----------


# ---------- global remote track (additive; independent of the jobsearch flow) ----------


def build_remote_messages(jobs: list[dict]) -> list[str]:
    blocks = [format_remote_block(i, j) for i, j in enumerate(jobs, 1)]
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
        header = f"🌍 <b>{len(jobs)} yeni remote iş</b>"
        if total > 1:
            header += f" (bölüm {part}/{total})"
        messages.append("\n\n".join([header, *chunk]))
    return messages


def format_remote_block(index: int, job: dict) -> str:
    header = f"<b>{index}. {html.escape(job['title'])}</b>"
    if job.get("score"):
        header += f"  ({job['score']}%)"
    lines = [header]
    if job.get("company"):
        lines.append(f"🏢 {html.escape(job['company'])}")
    meta = " · ".join(
        part
        for part in [job.get("source"), job.get("job_type"), job.get("location"), job.get("salary")]
        if part
    )
    if meta:
        lines.append(f"🌐 {html.escape(meta)}")
    if job.get("why_fits"):
        lines.append(f"💡 {html.escape(job['why_fits'])}")
    lines.append(f"🔗 <a href=\"{html.escape(job['url'])}\">Elanı aç</a>")
    return "\n".join(lines)


def send_remote(config: Config, jobs: list[dict], chat_id: str | int | None = None) -> None:
    if not config.telegram_enabled:
        raise RuntimeError("Telegram is not configured.")
    if not jobs:
        return
    for text in build_remote_messages(jobs):
        _send(config, text, chat_id=chat_id)


def get_updates(config: Config, offset: int | None = None) -> list[dict]:
    """Fetch pending updates once (no long polling - we run from cron)."""
    params: dict = {"timeout": 0, "allowed_updates": '["message"]'}
    if offset is not None:
        params["offset"] = offset
    response = requests.get(api_url(config, "getUpdates"), params=params, timeout=25)
    response.raise_for_status()
    return response.json().get("result", [])


def get_file_bytes(config: Config, file_id: str, max_bytes: int = 15_000_000) -> bytes:
    """Download a file (e.g. an uploaded CV pdf) from Telegram."""
    response = requests.get(api_url(config, "getFile"), params={"file_id": file_id}, timeout=25)
    response.raise_for_status()
    file_path = response.json()["result"]["file_path"]
    file_response = requests.get(
        f"https://api.telegram.org/file/bot{config.telegram_bot_token}/{file_path}",
        timeout=60,
        stream=True,
    )
    file_response.raise_for_status()
    data = file_response.raw.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("file too large")
    return data
