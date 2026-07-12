from __future__ import annotations

import json
import re

from openai import OpenAI

from .config import Config
from .models import Classification, Job


POSITIVE_PATTERNS = {
    r"\bsteam\b": "steam",
    r"\bstem\b": "stem",
    r"\bstiam\b": "steam_typo",
    r"\brobot\w*\b": "robotics",
    r"\brobotika\b": "robotics",
    r"\brobototexnika\b": "robotics",
    r"\barduino\b": "robotics",
    r"\blego\b": "robotics",
    r"\bmicro:?bit\b": "robotics",
    r"\bmikro:?bit\b": "robotics",
    r"\bscratch\b": "coding",
    r"\bcoding\b": "coding",
    r"\bkod(?:laşdirma|laşdırma)?\b": "coding",
    r"\bproqramlaşdırma\b": "coding",
    r"\bprogramming\b": "coding",
    r"\binformatika\b": "informatics",
    r"\bit\s+müəllimi\b": "it_teacher",
    r"\bmüəllim\b": "teaching",
    r"\bmuellim\b": "teaching",
    r"\bteacher\b": "teaching",
    r"\btəhsil mərkəzi\b": "education",
    r"\btehsil merkezi\b": "education",
    r"\binstructor\b": "teaching",
    r"\binstuctor\b": "teaching",
    r"\btrainer\b": "teaching",
    r"\btəlimçi\b": "training",
    r"\btelimci\b": "training",
    r"\bməktəb\b": "school",
    r"\bmekteb\b": "school",
    r"\bacademy\b": "academy",
    r"\bakademiya\b": "academy",
    r"\bkurs\b": "course",
    r"\bcourse\b": "course",
    r"\buşaq\w*\b": "children",
    r"\busaq\w*\b": "children",
    r"\bkids\b": "children",
    r"\bchildren\b": "children",
}

NEGATIVE_PATTERNS = {
    r"\bsales\b": "sales",
    r"\bsatış\b": "sales",
    r"\bsatis\b": "sales",
    r"\bcall center\b": "call_center",
    r"\bmühasib\b": "accounting",
    r"\bmuhasib\b": "accounting",
    r"\baccountant\b": "accounting",
    r"\bdeveloper\b": "software_developer",
    r"\bit support\b": "it_support",
    r"\bsystem administrator\b": "it_admin",
    r"\bdatabase administrator\b": "it_admin",
    r"\bofis meneceri\b": "office_manager",
}

TECH_CONCEPTS = {"steam", "stem", "steam_typo", "robotics", "coding", "informatics", "it_teacher"}
EDUCATION_CONCEPTS = {"teaching", "training", "education", "school", "academy", "course", "children", "it_teacher"}


def classify_job(job: Job, config: Config) -> Classification:
    heuristic = heuristic_classify(job)

    if not config.ai_enabled:
        return heuristic

    # Do not spend AI calls on clearly unrelated jobs.
    if heuristic.label == "NO_MATCH" and heuristic.confidence >= 80:
        return heuristic

    try:
        return ai_classify(job, config)
    except Exception as exc:  # noqa: BLE001 - notification bot should degrade gracefully.
        return Classification(
            label=heuristic.label,
            confidence=heuristic.confidence,
            reason=f"AI classification failed; heuristic used. Error: {exc}",
            matched_concepts=heuristic.matched_concepts,
            source="heuristic_fallback",
        )


def positive_signals(text: str) -> set[str]:
    """Positive concepts found in `text` (used for the cheap title-only prefilter)."""
    normalized = normalize(text)
    return {
        concept
        for pattern, concept in POSITIVE_PATTERNS.items()
        if re.search(pattern, normalized)
    }


def heuristic_classify(job: Job) -> Classification:
    text = normalize(job.full_text)
    positives = sorted(
        {concept for pattern, concept in POSITIVE_PATTERNS.items() if re.search(pattern, text)}
    )
    negatives = sorted(
        {concept for pattern, concept in NEGATIVE_PATTERNS.items() if re.search(pattern, text)}
    )

    positive_set = set(positives)
    tech_signal = bool(TECH_CONCEPTS & positive_set)
    education_signal = bool(EDUCATION_CONCEPTS & positive_set)

    if tech_signal and education_signal:
        return Classification(
            label="HIGH_MATCH",
            confidence=86,
            reason="Ilanda texnologiya/robotika/kodlama ve tehsil/telim siqnali birlikde var.",
            matched_concepts=positives,
        )

    if tech_signal:
        return Classification(
            label="MAYBE_MATCH",
            confidence=62,
            reason="Ilanda texnologiya siqnali var, amma muellimlik/telim baglantisi net deyil.",
            matched_concepts=positives,
        )

    if negatives and not tech_signal:
        return Classification(
            label="NO_MATCH",
            confidence=88,
            reason="Ilan hedef texnologiya egitmenliyi profiline benzemiyor.",
            matched_concepts=sorted(set(negatives + positives)),
        )

    if education_signal:
        return Classification(
            label="NO_MATCH",
            confidence=74,
            reason="Ilanda tehsil/telim siqnali var, amma STEAM/STEM/robotika/kodlama baglantisi yoxdur.",
            matched_concepts=positives,
        )

    return Classification(
        label="NO_MATCH",
        confidence=80,
        reason="STEAM/STEM, robotika, kodlama veya teknoloji egitimi sinyali bulunmadi.",
        matched_concepts=[],
    )


def ai_classify(job: Job, config: Config) -> Classification:
    client = OpenAI(api_key=config.openai_api_key)
    prompt = build_prompt(job)

    response = client.responses.create(
        model=config.openai_model,
        input=[
            {
                "role": "system",
                "content": (
                    "You classify Azerbaijan job posts for a user looking for "
                    "STEAM/STEM, robotics, coding, programming, informatics "
                    "teacher/trainer jobs, especially for children or education centers."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "job_match_classification",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "label": {
                            "type": "string",
                            "enum": ["HIGH_MATCH", "MAYBE_MATCH", "NO_MATCH"],
                        },
                        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                        "reason": {"type": "string"},
                        "matched_concepts": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["label", "confidence", "reason", "matched_concepts"],
                },
                "strict": True,
            }
        },
    )

    raw = response.output_text
    data = json.loads(raw)
    return Classification(
        label=data["label"],
        confidence=int(data["confidence"]),
        reason=str(data["reason"]),
        matched_concepts=[str(item) for item in data["matched_concepts"]],
        source="openai",
    )


def build_prompt(job: Job) -> str:
    return f"""
User target:
- STEAM/STEM muellimliyi
- Robotika muellimliyi / robototexnika telimcisi
- Kodlama, proqramlasdirma, informatika muellimi
- Usaqlar ve yeniyetmeler ucun texnologiya tehsili
- Mekteb, kurs, academy, tehsil merkezi rolleri

Relevant even if:
- STEAM is misspelled as STEM/STIAM/STEM-like
- title is vague but description mentions robotics/coding/Arduino/children/education
- role is IT/informatics teacher or technology trainer

Not relevant:
- pure software developer roles
- IT support/admin roles
- sales, call center, accounting, office manager
- engineering role with no teaching/training/education context
- non-technology teachers such as IELTS, English, accounting, finance teachers

Return JSON only.

Job:
Title: {job.title}
Company: {job.company}
URL: {job.url}
Text:
{job.description[:10000]}
""".strip()


def normalize(text: str) -> str:
    lowered = text.lower()
    return re.sub(r"\s+", " ", lowered)




