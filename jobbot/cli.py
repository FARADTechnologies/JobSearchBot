from __future__ import annotations

import argparse
import sys

from .classifier import classify_job, positive_signals
from .config import load_config
from .scraper import build_session, enrich_job, fetch_all_jobs
from .state import SeenStore
from .telegram import format_message, send_job


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="JobSearch.az Telegram alert bot")
    parser.add_argument("--dry-run", action="store_true", help="Do not send Telegram messages or update seen DB.")
    parser.add_argument("--max", type=int, default=None, help="Override max candidate jobs enriched per run.")
    args = parser.parse_args()

    config = load_config()
    seen = SeenStore(config.seen_db_path)
    session = build_session()

    jobs = fetch_all_jobs(session=session)
    new_jobs = [job for job in jobs if not seen.has(job.id)]

    # Stage 1 - cheap prefilter on title + company only (no network per job).
    # A job is a candidate if its title/company carries any tech OR education
    # signal; the expensive detail fetch + full classification runs only on these.
    candidates: list = []
    for job in new_jobs:
        if positive_signals(f"{job.title} {job.company}"):
            candidates.append(job)
        elif not args.dry_run:
            # No signal at all -> settled as NO_MATCH, never look at it again.
            seen.add(job.id)

    limit = args.max if args.max is not None else config.max_jobs_per_run
    print(
        f"Found {len(jobs)} jobs, {len(new_jobs)} new, "
        f"{len(candidates)} candidates (processing up to {limit})."
    )

    processed = 0
    notified = 0

    # Stage 2 - enrich + classify each candidate.
    for job in candidates[:limit]:
        processed += 1
        print(f"[{processed}/{min(len(candidates), limit)}] Checking: {job.title} - {job.url}")

        try:
            detailed_job = enrich_job(job, session=session)
        except Exception as exc:  # noqa: BLE001 - one bad page must not kill the run.
            print(f"    SKIP (fetch error): {exc}", file=sys.stderr)
            continue

        classification = classify_job(detailed_job, config)

        should_send = classification.label == "HIGH_MATCH" or (
            classification.label == "MAYBE_MATCH" and config.send_maybe_matches
        )

        print(
            f"    {classification.label} {classification.confidence}% "
            f"({classification.source}) - {classification.reason}"
        )

        if args.dry_run:
            if should_send:
                print(format_message(detailed_job, classification))
            continue

        if should_send:
            send_job(config, detailed_job, classification)
            notified += 1

        seen.add(job.id)

    if not args.dry_run:
        seen.save()

    print(f"Processed {processed}. Sent {notified} Telegram notifications.")

    if not config.telegram_enabled and not args.dry_run:
        print(
            "Warning: Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.",
            file=sys.stderr,
        )
