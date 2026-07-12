from __future__ import annotations

import argparse
import sys

from .classifier import classify_job, positive_signals
from .config import load_config
from .scraper import build_session, enrich_job, fetch_all_jobs
from .state import SeenStore
from .telegram import build_batch_messages, send_matches


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
    candidates = []
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
    matches: list = []  # (job, classification) to be sent in one batch.

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
            # Decided NO_MATCH -> remember it so it is not reprocessed.
            seen.add(job.id)

    # Send every match in a single (batched) Telegram message.
    if args.dry_run:
        print("\n----- Telegram preview -----")
        for message in build_batch_messages(matches) if matches else ["(no matches)"]:
            print(message)
            print("-----")
    elif matches:
        try:
            send_matches(config, matches)
            for job, _ in matches:
                seen.add(job.id)  # only mark sent matches seen after a successful send
        except Exception as exc:  # noqa: BLE001
            print(f"Telegram send failed, matches will retry next run: {exc}", file=sys.stderr)

    if not args.dry_run:
        seen.save()

    print(f"Processed {processed}. Matched {len(matches)} jobs.")

    if not config.telegram_enabled and not args.dry_run:
        print(
            "Warning: Telegram is not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.",
            file=sys.stderr,
        )
