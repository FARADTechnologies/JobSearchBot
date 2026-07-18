from __future__ import annotations

import re

from .models import Classification, Job

# Interim per-user scorer (no LLM/embeddings yet). Mirrors the locked
# architecture's shape: cheap wide prefilter -> narrow deep scoring.
# The deep stage is replaced by embeddings + rerank + LLM-judge later
# (see ARCHITECTURE.md); the call sites stay the same.


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[\w+#.]{3,}", text.lower()))


def profile_terms(profile: dict) -> set[str]:
    terms: set[str] = set()
    for key in ("top_terms", "skills", "job_titles", "categories"):
        for item in profile.get(key) or []:
            terms.update(tokenize(str(item)))
    return terms


def exclude_terms(profile: dict) -> set[str]:
    terms: set[str] = set()
    for item in profile.get("exclude") or []:
        terms.update(tokenize(str(item)))
    return terms


def hits_in(terms: set[str], tokens: set[str]) -> set[str]:
    """Word-level matching with a prefix tolerance for agglutinative suffixes
    (az/tr: 'robotika' matches 'robotikanın'). Substring-inside-word is NOT a hit
    ('cad' must not match 'academy')."""
    found: set[str] = set()
    for term in terms:
        if term in tokens:
            found.add(term)
        elif len(term) >= 5 and any(token.startswith(term) for token in tokens):
            found.add(term)
    return found


def title_overlap(terms: set[str], job: Job) -> int:
    """Cheap prefilter signal: profile-term hits in title+company only."""
    return len(hits_in(terms, tokenize(f"{job.title} {job.company}")))


def score_job(profile: dict, job: Job) -> Classification:
    """Deep(er) interim score on the job's full text. Title hits weigh double."""
    terms = profile_terms(profile)
    negatives = exclude_terms(profile)

    title_tokens = tokenize(f"{job.title} {job.company}")
    body_tokens = tokenize(job.full_text)

    title_hits = hits_in(terms, title_tokens)
    body_hits = hits_in(terms, body_tokens)
    negative_hits = hits_in(negatives, body_tokens)

    score = sum(2 if term in title_hits else 1 for term in body_hits | title_hits)
    score -= 2 * len(negative_hits)
    shown = sorted(title_hits | body_hits)

    if score >= 6:
        label, confidence = "HIGH_MATCH", min(70 + score, 90)
        reason = "Profil terminləri ilə güclü üst-üstə düşmə."
    elif score >= 3:
        label, confidence = "MAYBE_MATCH", min(55 + score, 69)
        reason = "Profillə qismən uyğunluq."
    else:
        label, confidence = "NO_MATCH", 80
        reason = "Profillə kifayət qədər uyğunluq tapılmadı."

    return Classification(
        label=label,
        confidence=confidence,
        reason=reason,
        matched_concepts=shown[:8],
        source="term_overlap",
    )
