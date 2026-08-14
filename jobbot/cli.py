from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from .classifier import classify_job, positive_signals
from .config import Config, load_config
from .matching import profile_terms, score_job, title_overlap
from .models import Job
from .scraper import build_session, enrich_job, fetch_all_jobs
from .state import SeenStore
from .telegram import build_batch_messages, send_matches


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="JobSearch.az Telegram alert bot")
    parser.add_argument("--dry-run", action="store_true", help="Do not send Telegram messages or update state.")
    parser.add_argument("--max", type=int, default=None, help="Override max candidate jobs enriched per run.")
    args = parser.parse_args()

    config = load_config()
    session = build_session()

    jobs = fetch_all_jobs(session=session)
    print(f"Scraped {len(jobs)} jobs.")

    # ---- Faz 1: multi-user flow (Supabase-backed). Skipped in dry-run. ----
    if config.supabase_enabled and not args.dry_run:
        try:
            run_multiuser(config, jobs, session)
        except Exception as exc:  # noqa: BLE001 - never let it break the legacy flow
            print(f"Multi-user flow failed: {exc}", file=sys.stderr)

    # ---- Legacy single-user flow (env-configured user). Unchanged. ----
    run_legacy(config, jobs, session, args)

    # ---- Global remote track (ADDITIVE). Isolated: a failure here can never
    #      affect the flows above. ----
    if config.remote_track_enabled:
        try:
            run_remote_track(config, args)
        except Exception as exc:  # noqa: BLE001
            print(f"Remote track failed: {exc}", file=sys.stderr)


# ------------------------------------------------------------ global remote track


def run_remote_track(config: Config, args) -> None:
    from .remote_sources import fetch_global_remote
    from .telegram import build_remote_messages, send_remote

    jobs = fetch_global_remote()
    seen = SeenStore(config.remote_seen_path)
    fresh = [j for j in jobs if not seen.has(j["id"])]
    print(f"Remote track: {len(jobs)} relevant remote jobs, {len(fresh)} new.")

    # Bound each run so the first run does not flood; the rest arrive over
    # subsequent runs (seen store dedups).
    batch = fresh[: config.remote_max_per_run]

    if args.dry_run:
        print("\n----- Remote preview -----")
        for message in build_remote_messages(batch) if batch else ["(no new remote jobs)"]:
            print(message)
            print("-----")
        return

    if batch:
        try:
            send_remote(config, batch, chat_id=config.telegram_chat_id)
            for j in batch:
                seen.add(j["id"])
        except Exception as exc:  # noqa: BLE001
            print(f"Remote send failed, will retry next run: {exc}", file=sys.stderr)

    seen.save()


# ---------------------------------------------------------------- multi-user


def run_multiuser(config: Config, jobs: list[Job], session) -> None:
    from .db import SupabaseDB
    from .onboarding import process_updates

    db = SupabaseDB(config.supabase_url, config.supabase_secret_key)

    # 1. Refresh the SHARED job corpus (cheap columns only; text cached on demand).
    db.upsert_jobs(
        [
            {
                "id": job.id,
                "url": job.url,
                "title": job.title,
                "company": job.company,
                "created_at_source": job.date_text,
            }
            for job in jobs
        ]
    )

    # 2. Handle onboarding messages (/start, CV uploads, commands).
    handled = process_updates(config, db)

    # 3. Per-user matching. Architecture shape: cheap wide prefilter ->
    #    narrow deep scoring (deep stage becomes embeddings+rerank+judge later).
    enrich_budget = config.enrich_budget_per_run
    users = db.active_users()
    notified_users = 0

    for user in users:
        if str(user["telegram_chat_id"]) == config.telegram_chat_id:
            continue  # this chat is served by the legacy flow

        cv = db.get_active_cv(user["id"])
        if not cv or not cv.get("profile"):
            continue

        profile = cv["profile"]
        terms = profile_terms(profile)
        if not terms:
            continue

        seen = db.match_job_ids(user["id"])
        candidates = [job for job in jobs if job.id not in seen]
        if not candidates:
            continue

        scored = [(title_overlap(terms, job), job) for job in candidates]
        ranked = sorted((item for item in scored if item[0] > 0), key=lambda item: -item[0])
        top = [job for _, job in ranked[:40]]

        # Zero-signal jobs are settled as prefiltered NO so they are never rescanned.
        # NOTE: with heuristic profiles this can be conservative; acceptable for Faz 1.
        zero_records = [
            {"user_id": user["id"], "job_id": job.id, "label": "NO_MATCH", "source": "title_prefilter"}
            for overlap, job in scored
            if overlap == 0
        ]

        # Deep stage: full text from shared cache, enrich (and cache) on miss.
        cached = db.job_texts([job.id for job in top])
        to_send: list = []
        records: list[dict] = []
        for job in top:
            row = cached.get(job.id) or {}
            if row.get("description"):
                detailed = Job(
                    id=job.id,
                    title=job.title,
                    company=job.company,
                    url=job.url,
                    date_text=job.date_text,
                    deadline=row.get("deadline_at") or "",
                    summary=row.get("category") or "",
                    description=row["description"],
                )
            elif enrich_budget > 0:
                try:
                    detailed = enrich_job(job, session=session)
                    enrich_budget -= 1
                    db.cache_job_text(detailed.id, detailed.description, detailed.summary, detailed.deadline or None)
                except Exception as exc:  # noqa: BLE001
                    print(f"    enrich failed for {job.id}: {exc}", file=sys.stderr)
                    continue
            else:
                continue  # out of budget: stays unseen, next run picks it up

            cls = score_job(profile, detailed)
            record = {
                "user_id": user["id"],
                "job_id": job.id,
                "label": cls.label,
                "confidence": cls.confidence,
                "reason": cls.reason,
                "source": cls.source,
            }
            should_send = cls.label == "HIGH_MATCH" or (cls.label == "MAYBE_MATCH" and config.send_maybe_matches)
            if should_send:
                to_send.append((detailed, cls, record))
            records.append(record)

        if to_send:
            try:
                send_matches(config, [(job, cls) for job, cls, _ in to_send], chat_id=user["telegram_chat_id"])
                stamp = datetime.now(timezone.utc).isoformat()
                for _, _, record in to_send:
                    record["notified_at"] = stamp
                notified_users += 1
            except Exception as exc:  # noqa: BLE001
                print(f"    send failed for user {user['id']}: {exc}", file=sys.stderr)
                # Drop unsent records so they retry next run.
                sent_ids = {record["job_id"] for _, _, record in to_send}
                records = [record for record in records if record["job_id"] not in sent_ids]

        db.record_matches(records + zero_records)

    print(
        f"Multi-user: {len(users)} active users, {handled} telegram updates, "
        f"{notified_users} users notified, enrich budget left {enrich_budget}."
    )


# ---------------------------------------------------------------- legacy


def run_legacy(config: Config, jobs: list[Job], session, args) -> None:
    seen = SeenStore(config.seen_db_path)
    new_jobs = [job for job in jobs if not seen.has(job.id)]

    # Stage 1 - cheap prefilter on title + company only (no network per job).
    candidates = []
    for job in new_jobs:
        if positive_signals(f"{job.title} {job.company}"):
            candidates.append(job)
        elif not args.dry_run:
            seen.add(job.id)

    limit = args.max if args.max is not None else config.max_jobs_per_run
    print(
        f"Legacy: {len(jobs)} jobs, {len(new_jobs)} new, "
        f"{len(candidates)} candidates (processing up to {limit})."
    )

    processed = 0
    matches: list = []

    for job in candidates[:limit]:
        processed += 1
        print(f"[{processed}/{min(len(candidates), limit)}] Checking: {job.title} - {job.url}")

        try:
            detailed_job = enrich_job(job, session=session)
        except Exception as exc:  # noqa: BLE001 - one bad page must not kill the run.
            print(f"    SKIP (fetch error): {exc}", file=sys.stderr)
            continue

        classification = classify_job(detailed_job, config)
        print(
            f"    {classification.label} {classification.confidence}% "
            f"({classification.source}) - {classification.reason}"
        )

        should_send = classification.label == "HIGH_MATCH" or (
            classification.label == "MAYBE_MATCH" and config.send_maybe_matches
        )

        if should_send:
            matches.append((detailed_job, classification))
        elif not args.dry_run:
            seen.add(job.id)

    if args.dry_run:
        print("\n----- Telegram preview -----")
        for message in build_batch_messages(matches) if matches else ["(no matches)"]:
            print(message)
            print("-----")
    elif matches:
        try:
            send_matches(config, matches)
            for job, _ in matches:
                seen.add(job.id)
        except Exception as exc:  # noqa: BLE001
            print(f"Telegram send failed, matches will retry next run: {exc}", file=sys.stderr)

    if not args.dry_run:
        seen.save()

    print(f"Legacy processed {processed}. Matched {len(matches)} jobs.")

    if not config.telegram_enabled and not args.dry_run:
        print(
            "Warning: Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.",
            file=sys.stderr,
        )
