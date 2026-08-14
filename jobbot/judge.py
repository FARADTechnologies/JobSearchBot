"""LLM evaluation stage (Gemini).

Job listings are PUBLIC data, so a free-tier LLM is fine here (the CV-privacy
rule in ARCHITECTURE.md is about CVs, not public postings). We send a short
candidate *profile spec* (skills + preferences, NOT the full CV) plus a BATCH of
jobs, and get back a structured verdict per job.

Batching (answering the design question): we send many jobs per request, not one
request per job. Fewer requests = far cheaper + faster. The tradeoff is that very
large batches spread the model's attention thin and can hit token limits, so we
cap the batch size (~12). Net: batching is a clear win at a sane batch size.
"""
from __future__ import annotations

import json
import time

import requests

from .config import Config

# Who the user is + what they want. This is the "the LLM knows me" part.
# (Later this can be generated per-user from their CV; for now it is Hesen's.)
PROFILE_SPEC = """Candidate: Robotics & Mechatronics engineer based in AZERBAIJAN.
Skills: Python, C/C++, embedded (Raspberry Pi, Jetson, sensors, motor drivers),
computer vision & ML (YOLO, OpenCV, segmentation, tracking), SOLIDWORKS/3D printing/CNC,
data science. Has taught robotics. Comfortable using AI tools to do knowledge work.

What the candidate is looking for RIGHT NOW:
- REMOTE or PART-TIME work (either is fine; remote preferred). Field is flexible:
  does NOT have to be robotics. Software, data, ML/AI, analysis, technical, content,
  or any knowledge work he can do (often with AI assistance) all count.
- Must be realistically doable from Azerbaijan as a remote worker / contractor.
  So: worldwide / anywhere / EMEA / Europe / remote-global roles are GOOD.
  Roles restricted to US-only, US-work-authorization, Canada-only, or a specific
  country he is not in are NOT suitable.
- Paid internships (təcrübə) that are remote/part-time are fine.

Reject: onsite-only roles; roles requiring local work authorization he lacks;
obvious scams (upfront payment, vague + too-good salary, personal/bank details asked
early, contact only via WhatsApp/Telegram with no real company); pure sales/clinical/
physical roles unrelated to his skills."""

PROMPT_TEMPLATE = """{spec}

Evaluate each job below for THIS candidate. Return ONLY a JSON array, one object per
job, in the same order, with keys:
- "id": the job id (copy exactly)
- "decision": "yes" | "maybe" | "no"
- "score": integer 0-100 (fit for this candidate to apply)
- "reason": <=12 words, why
- "why_fits": one short sentence the candidate would find useful (only if yes/maybe; else "")

Jobs:
{jobs}
"""


def _endpoint(config: Config) -> str:
    return (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{config.gemini_model}:generateContent?key={config.gemini_api_key}"
    )


def _job_line(job: dict) -> dict:
    return {
        "id": job["id"],
        "title": job.get("title", ""),
        "company": job.get("company", ""),
        "type": job.get("job_type", ""),
        "location": job.get("location", ""),
        "source": job.get("source", ""),
        "tags": ", ".join(job.get("tags", [])[:8]),
        "desc": (job.get("description") or "")[:600],
    }


def evaluate_batch(jobs: list[dict], config: Config, batch_size: int = 12, log=print) -> dict[str, dict]:
    """Return {job_id: {decision, score, reason, why_fits}}. Never raises."""
    verdicts: dict[str, dict] = {}
    if not config.llm_judge_enabled or not config.gemini_api_key:
        return verdicts

    for i in range(0, len(jobs), batch_size):
        chunk = jobs[i : i + batch_size]
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": PROMPT_TEMPLATE.format(
                                spec=PROFILE_SPEC,
                                jobs=json.dumps([_job_line(j) for j in chunk], ensure_ascii=False),
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0},
        }
        text = _post_with_retries(config, payload, log, i // batch_size + 1)
        if not text:
            continue  # transient failure -> those jobs stay unseen, retried next run
        try:
            if text.startswith("```"):
                text = text.split("```", 2)[1].lstrip("json").strip()
            for v in json.loads(text):
                if v.get("id"):
                    verdicts[str(v["id"])] = v
        except Exception as exc:  # noqa: BLE001 - bad JSON; skip this batch
            log(f"  LLM batch parse failed: {exc}")

    return verdicts


def _post_with_retries(config: Config, payload: dict, log, batch_no: int, attempts: int = 4) -> str:
    """POST with backoff on transient 429/5xx/timeouts (Gemini overloads briefly)."""
    for attempt in range(attempts):
        try:
            r = requests.post(_endpoint(config), json=payload, timeout=90)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            r.raise_for_status()
            parts = r.json()["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts).strip()
        except Exception as exc:  # noqa: BLE001
            if attempt < attempts - 1:
                time.sleep(2 * (attempt + 1))
            else:
                log(f"  LLM batch {batch_no} failed after {attempts} tries: {exc}")
    return ""

    return verdicts
