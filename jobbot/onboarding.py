from __future__ import annotations

import sys

from .config import Config
from .cv import extract_profile, pdf_bytes_to_text
from .db import SupabaseDB
from .telegram import get_file_bytes, get_updates, send_text

WELCOME = (
    "👋 <b>Hi! I'm JobSearchBot.</b>\n\n"
    "I watch active job listings 24/7 and send you the ones matching your profile.\n\n"
    "To get started, send your <b>CV as a PDF</b> here. 📄"
)

CV_RECEIVED = (
    "✅ <b>CV received!</b>\n\n"
    "Your profile is ready. From now on I'll notify you as soon as new matching "
    "listings are found.\n\n"
    "Optional: if you want to add your CV to our anonymous candidate pool, type "
    "/pool_on — companies can find you when searching for suitable candidates. "
    "(You can remove it any time with /pool_off.)\n\n"
    "Commands: /status · /pause · /resume"
)

CV_UNREADABLE = (
    "⚠️ Could not read the CV. If the PDF is image-based (e.g. a Canva design), text "
    "cannot be extracted. Please send a text-based PDF."
)

HELP = (
    "📄 Send your CV as a PDF — I'll build your profile.\n"
    "Commands:\n"
    "/status — your status\n"
    "/pause — stop notifications\n"
    "/resume — resume notifications\n"
    "/pool_on — add your CV to the candidate pool\n"
    "/pool_off — remove it from the pool"
)


def process_updates(config: Config, db: SupabaseDB) -> int:
    """Handle pending Telegram messages (onboarding + commands). Returns count."""
    offset = db.get_state("telegram_offset")
    updates = get_updates(config, offset=offset)
    handled = 0

    for update in updates:
        try:
            handle_update(config, db, update)
        except Exception as exc:  # noqa: BLE001 - one bad update must not block the queue
            print(f"Update {update.get('update_id')} failed: {exc}", file=sys.stderr)
        handled += 1
        db.set_state("telegram_offset", update["update_id"] + 1)

    return handled


def handle_update(config: Config, db: SupabaseDB, update: dict) -> None:
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id or chat.get("type") != "private":
        return

    sender = message.get("from") or {}
    user = db.get_user_by_chat(chat_id)
    text = (message.get("text") or "").strip()
    document = message.get("document")

    if text.startswith("/start") or user is None:
        if user is None:
            full_name = " ".join(p for p in [sender.get("first_name"), sender.get("last_name")] if p)
            user = db.create_user(chat_id, sender.get("username") or "", full_name)
        if text.startswith("/start"):
            send_text(config, chat_id, WELCOME)
            return

    if document:
        handle_cv_upload(config, db, user, chat_id, document)
        return

    command = text.lower()
    if command.startswith("/status"):
        cv = db.get_active_cv(user["id"])
        state = {"active": "active ✅", "paused": "paused ⏸", "awaiting_cv": "awaiting CV 📄"}.get(
            user["state"], user["state"]
        )
        pool = "yes" if user.get("cv_pool_opt_in") else "no"
        cv_line = f"CV: {cv['file_name']}" if cv else "CV: not uploaded"
        send_text(config, chat_id, f"ℹ️ Status: {state}\n{cv_line}\nIn pool: {pool}")
    elif command.startswith("/pause"):
        db.update_user(user["id"], {"state": "paused"})
        send_text(config, chat_id, "⏸ Notifications paused. Resume any time with /resume.")
    elif command.startswith("/resume"):
        db.update_user(user["id"], {"state": "active" if db.get_active_cv(user["id"]) else "awaiting_cv"})
        send_text(config, chat_id, "▶️ Notifications are active.")
    elif command.startswith("/pool_on"):
        db.update_user(user["id"], {"cv_pool_opt_in": True})
        send_text(config, chat_id, "✅ Your CV was added to the candidate pool. Remove it with /pool_off.")
    elif command.startswith("/pool_off"):
        db.update_user(user["id"], {"cv_pool_opt_in": False})
        send_text(config, chat_id, "☑️ Your CV was removed from the pool.")
    elif text:
        send_text(config, chat_id, HELP)


def handle_cv_upload(config: Config, db: SupabaseDB, user: dict, chat_id: int, document: dict) -> None:
    name = document.get("file_name") or "cv.pdf"
    if not name.lower().endswith(".pdf"):
        send_text(config, chat_id, "⚠️ Please send your CV in <b>PDF</b> format.")
        return

    try:
        data = get_file_bytes(config, document["file_id"])
        raw_text = pdf_bytes_to_text(data)
    except Exception as exc:  # noqa: BLE001
        print(f"CV download/parse failed for chat {chat_id}: {exc}", file=sys.stderr)
        raw_text = ""

    if len(raw_text) < 200:
        send_text(config, chat_id, CV_UNREADABLE)
        return

    profile, source = extract_profile(raw_text, config)
    db.save_cv(user["id"], name, raw_text, profile, source)
    db.update_user(user["id"], {"state": "active"})
    send_text(config, chat_id, CV_RECEIVED)
