from __future__ import annotations

import sys

from .config import Config
from .cv import extract_profile, pdf_bytes_to_text
from .db import SupabaseDB
from .telegram import get_file_bytes, get_updates, send_text

WELCOME = (
    "👋 <b>Salam! Mən JobSearchBot-am.</b>\n\n"
    "Azərbaycandakı aktiv iş elanlarını 7/24 izləyirəm və profilinə uyğun olanları "
    "sənə göndərirəm.\n\n"
    "Başlamaq üçün <b>CV-ni PDF şəklində</b> bura göndər. 📄"
)

CV_RECEIVED = (
    "✅ <b>CV qəbul edildi!</b>\n\n"
    "Profilin hazırlandı. Bundan sonra sənə uyğun yeni elanlar tapılan kimi "
    "bildiriş göndərəcəyəm.\n\n"
    "İstəyə bağlı: CV-ni anonim namizəd hovuzumuza əlavə etmək istəyirsənsə "
    "/hovuz_aktiv yaz — şirkətlər uyğun namizəd axtaranda səni tapa bilər. "
    "(İstənilən vaxt /hovuz_deaktiv ilə çıxara bilərsən.)\n\n"
    "Komandalar: /status · /pause · /resume"
)

CV_UNREADABLE = (
    "⚠️ CV oxuna bilmədi. PDF şəkil-əsaslıdırsa (məs. Canva dizaynı), mətn "
    "çıxarmaq mümkün olmur. Zəhmət olmasa mətn-əsaslı PDF göndər."
)

HELP = (
    "📄 CV-ni PDF şəklində göndər — profilini hazırlayım.\n"
    "Komandalar:\n"
    "/status — vəziyyətin\n"
    "/pause — bildirişləri dayandır\n"
    "/resume — bildirişləri davam etdir\n"
    "/hovuz_aktiv — CV-ni namizəd hovuzuna əlavə et\n"
    "/hovuz_deaktiv — hovuzdan çıxar"
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
        state = {"active": "aktiv ✅", "paused": "dayandırılıb ⏸", "awaiting_cv": "CV gözlənilir 📄"}.get(
            user["state"], user["state"]
        )
        pool = "bəli" if user.get("cv_pool_opt_in") else "xeyr"
        cv_line = f"CV: {cv['file_name']}" if cv else "CV: yüklənməyib"
        send_text(config, chat_id, f"ℹ️ Vəziyyət: {state}\n{cv_line}\nHovuzda: {pool}")
    elif command.startswith("/pause"):
        db.update_user(user["id"], {"state": "paused"})
        send_text(config, chat_id, "⏸ Bildirişlər dayandırıldı. /resume ilə davam etdirə bilərsən.")
    elif command.startswith("/resume"):
        db.update_user(user["id"], {"state": "active" if db.get_active_cv(user["id"]) else "awaiting_cv"})
        send_text(config, chat_id, "▶️ Bildirişlər aktivdir.")
    elif command.startswith("/hovuz_aktiv"):
        db.update_user(user["id"], {"cv_pool_opt_in": True})
        send_text(config, chat_id, "✅ CV-n namizəd hovuzuna əlavə edildi. /hovuz_deaktiv ilə çıxara bilərsən.")
    elif command.startswith("/hovuz_deaktiv"):
        db.update_user(user["id"], {"cv_pool_opt_in": False})
        send_text(config, chat_id, "☑️ CV-n hovuzdan çıxarıldı.")
    elif text:
        send_text(config, chat_id, HELP)


def handle_cv_upload(config: Config, db: SupabaseDB, user: dict, chat_id: int, document: dict) -> None:
    name = document.get("file_name") or "cv.pdf"
    if not name.lower().endswith(".pdf"):
        send_text(config, chat_id, "⚠️ Zəhmət olmasa CV-ni <b>PDF</b> formatında göndər.")
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
