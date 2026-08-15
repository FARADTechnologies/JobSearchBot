from __future__ import annotations

import json
import re

from openai import OpenAI

from .config import Config
from .models import Classification, Job


# Signals are matched in Azerbaijani (AZ), English (EN) and Russian (RU) because
# JobSearch.az posts appear in all three languages. Each pattern maps to a concept;
# concepts are grouped below and drive the decision in `heuristic_classify`.

# --- Positive signals ------------------------------------------------------

TEACHING_PATTERNS = {
    # roles
    r"\bmüəllim\w*\b": "teaching",
    r"\bmuəllim\w*\b": "teaching",
    r"\bmuellim\w*\b": "teaching",
    r"\bteacher\b": "teaching",
    r"\binstructor\b": "teaching",
    r"\binstruktor\b": "teaching",
    r"\btrainer\b": "teaching",
    r"\btəlimçi\b": "teaching",
    r"\btelimci\b": "teaching",
    r"\bmentor\w*\b": "teaching",
    r"\btutor\b": "teaching",
    r"\bpreporad\w*\b": "teaching",
    r"\bprepodavatel\w*\b": "teaching",
    r"преподавател": "teaching",
    r"педагог": "teaching",
    r"репетитор": "teaching",
    r"\bpedaqoq\w*\b": "teaching",
    r"\btədris\b": "teaching",
    r"\btedris\b": "teaching",
    r"обучени": "teaching",
    # venues
    r"\bacademy\b": "education",
    r"\bakademiya\b": "education",
    r"академи": "education",
    r"\bschool\b": "education",
    r"\bməktəb\w*\b": "education",
    r"\bmekteb\w*\b": "education",
    r"школ": "education",
    r"\bkurs\w*\b": "education",
    r"\bcourse\b": "education",
    r"курс": "education",
    r"\btəhsil mərkəzi\b": "education",
    r"\btədris mərkəzi\b": "education",
    r"\btəlim mərkəzi\b": "education",
    r"\blearning center\b": "education",
    r"\bcollege\b": "education",
    r"\bkollec\b": "education",
    r"\blisey\b": "education",
    r"\bgimnaziya\b": "education",
    # audience
    r"\buşaq\w*\b": "children",
    r"\busaq\w*\b": "children",
    r"\bkids\b": "children",
    r"\bchildren\b": "children",
    r"дет(?:и|ей|ям)\b": "children",
    r"\byeniyetmə\w*\b": "children",
    r"\bməktəbli\w*\b": "children",
}

# Robotics / hardware / mechatronics — the user's core engineering profile.
ROBOTICS_PATTERNS = {
    r"\brobot\w*\b": "robotics",
    r"\brobotika\b": "robotics",
    r"\brobototexnika\b": "robotics",
    r"робот": "robotics",
    r"\bmexatronika\b": "robotics",
    r"\bmechatronic\w*\b": "robotics",
    r"мехатроник": "robotics",
    r"\barduino\b": "robotics",
    r"\blego\b": "robotics",
    r"\bmicro:?bit\b": "robotics",
    r"\bmikro:?bit\b": "robotics",
    r"\braspberry\b": "electronics",
    r"\bjetson\b": "electronics",
    r"\bplc\b": "automation",
    r"\bavtomatika\b": "automation",
    r"\bautomation\b": "automation",
    r"\bavtomatlaşdırma\b": "automation",
    r"автоматизаци": "automation",
    r"\brpa\b": "automation",
    r"\bcnc\b": "cad3d",
    r"\b3d\s*(?:print|çap|model)\w*\b": "cad3d",
    r"\bsolidworks\b": "cad3d",
    r"\bautocad\b": "cad3d",
    r"\bembedded\b": "embedded",
    r"\bgömülü\b": "embedded",
    r"\bfirmware\b": "embedded",
    r"\bmicrocontroller\b": "embedded",
    r"\bmikrokontroller\b": "embedded",
    r"\biot\b": "iot",
    r"\bpcb\b": "electronics",
    r"\belektronika\b": "electronics",
}

# Coding / informatics / STEAM / AI-ML — CS side of the profile.
CS_PATTERNS = {
    r"\bcoding\b": "coding",
    r"\bkodla\w*\b": "coding",
    r"\bproqramlaşdırma\w*\b": "coding",
    r"\bprogramming\b": "coding",
    r"программирован": "coding",
    r"\bscratch\b": "coding",
    r"\bpython\b": "coding",
    r"\binformatika\b": "informatics",
    r"информатик": "informatics",
    r"\bsteam\b": "steam",
    r"\bstem\b": "steam",
    r"\bstiam\b": "steam",
    r"\bcomputer vision\b": "ai_ml",
    r"\bmachine learning\b": "ai_ml",
    r"\bdeep learning\b": "ai_ml",
    r"\bdata scien\w*\b": "ai_ml",
    r"\bdata analy\w*\b": "ai_ml",
    r"\bsüni intellekt\b": "ai_ml",
    r"\bartificial intelligence\b": "ai_ml",
    r"искусственн\w* интеллект": "ai_ml",
    r"\bməlumat analiti\w*\b": "ai_ml",
}

POSITIVE_PATTERNS = {**TEACHING_PATTERNS, **ROBOTICS_PATTERNS, **CS_PATTERNS}

# --- Negative signals (only override when there is no teaching context) -----

NEGATIVE_PATTERNS = {
    # web / enterprise software development (user explicitly does not want these)
    r"\bback[\s-]?end\b": "developer",
    r"\bfront[\s-]?end\b": "developer",
    r"\bfull[\s-]?stack\b": "developer",
    r"\bweb developer\b": "developer",
    r"\bsoftware developer\b": "developer",
    r"\bsoftware engineer\b": "developer",
    r"\bdeveloper\b": "developer",
    r"\bproqramçı\b": "developer",
    r"\bprogrammer\b": "developer",
    r"разработчик": "developer",
    r"\b\.net\b": "developer",
    r"\basp\.net\b": "developer",
    r"\bphp\b": "developer",
    r"\blaravel\b": "developer",
    r"\bwordpress\b": "developer",
    r"\b1[cс]\b": "developer",
    # information security (user explicitly does not want these)
    r"\bcyber\w*\b": "security",
    r"\bkiber\w*\b": "security",
    r"\btəhlükəsizli\w*\b": "security",
    r"\bsecurity\b": "security",
    r"\bpenetration\b": "security",
    r"\bpentest\w*\b": "security",
    r"\bnüfuzetm\w*\b": "security",
    r"безопасност": "security",
    # IT operations / support
    r"\bsystem administrator\b": "it_ops",
    r"\bsistem administrator\w*\b": "it_ops",
    r"\bsysadmin\b": "it_ops",
    r"\bhelp\s?desk\b": "it_ops",
    r"\bit support\b": "it_ops",
    r"\btexniki dəstək\b": "it_ops",
    r"\bnetwork administrator\b": "it_ops",
    r"\bdevops\b": "it_ops",
    r"\bdatabase administrator\b": "it_ops",
    # clearly unrelated
    r"\bsales\b": "nontech",
    r"\bsatış\b": "nontech",
    r"\bsatis\b": "nontech",
    r"\bcall center\b": "nontech",
    r"\bmühasib\w*\b": "nontech",
    r"\bmuhasib\w*\b": "nontech",
    r"\baccountant\b": "nontech",
    r"\bofis meneceri\b": "nontech",
    r"\boffice manager\b": "nontech",
    r"\bhüquqşünas\b": "nontech",
    r"\blawyer\b": "nontech",
    r"\bsürücü\b": "nontech",
    r"\bdriver\b": "nontech",
    r"\bkassir\b": "nontech",
    r"\brecruiter\b": "nontech",
}

TEACH_CONCEPTS = {"teaching", "education", "children"}
ROBOTICS_CONCEPTS = {"robotics", "electronics", "automation", "embedded", "iot", "cad3d"}
CS_CONCEPTS = {"coding", "informatics", "steam", "ai_ml"}


def positive_signals(text: str) -> set[str]:
    """Positive concepts found in `text` (used for the cheap title-only prefilter)."""
    normalized = normalize(text)
    return {
        concept
        for pattern, concept in POSITIVE_PATTERNS.items()
        if re.search(pattern, normalized)
    }


def classify_job(job: Job, config: Config) -> Classification:
    heuristic = heuristic_classify(job)

    if not config.ai_enabled:
        return heuristic

    if heuristic.label == "NO_MATCH" and heuristic.confidence >= 85:
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


def heuristic_classify(job: Job) -> Classification:
    text = normalize(job.full_text)
    positives = {
        concept for pattern, concept in POSITIVE_PATTERNS.items() if re.search(pattern, text)
    }
    negatives = {
        concept for pattern, concept in NEGATIVE_PATTERNS.items() if re.search(pattern, text)
    }

    teaching = bool(TEACH_CONCEPTS & positives)
    robotics_eng = bool(ROBOTICS_CONCEPTS & positives)
    cs_ml = bool(CS_CONCEPTS & positives)
    tech = robotics_eng or cs_ml
    shown = sorted(positives)

    # 1. Technology teaching role - the user's primary target.
    if teaching and tech:
        return Classification(
            label="HIGH_MATCH",
            confidence=88,
            reason="A teaching/training role in technology/robotics/coding.",
            matched_concepts=shown,
        )

    # 2. Teacher, but not in a technology field (English, maths, etc.).
    if teaching and not tech:
        return Classification(
            label="NO_MATCH",
            confidence=78,
            reason="Education/training present, but not a technology/robotics/coding field.",
            matched_concepts=shown,
        )

    # 3. Robotics/mechatronics/embedded/automation engineering - core CV profile.
    #    Relevant even without a teaching angle, since pure robotics jobs are rare.
    if robotics_eng:
        return Classification(
            label="MAYBE_MATCH",
            confidence=68,
            reason="An engineering role matching the robotics/mechatronics/embedded/automation profile.",
            matched_concepts=shown,
        )

    # 4. Excluded tech: web/enterprise dev, infosec, IT-ops - user does not want these.
    if negatives:
        return Classification(
            label="NO_MATCH",
            confidence=88,
            reason="A role that does not fit the profile, such as software development / cybersecurity / IT support.",
            matched_concepts=sorted(negatives),
        )

    # 5. Data/AI/informatics role without excluded-dev signals - borderline.
    if cs_ml:
        return Classification(
            label="MAYBE_MATCH",
            confidence=60,
            reason="A role in coding/data/AI; the teaching connection is unclear.",
            matched_concepts=shown,
        )

    return Classification(
        label="NO_MATCH",
        confidence=82,
        reason="No signal matching the profile (robotics/STEAM/coding/technology teaching) was found.",
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
                    "You classify Azerbaijan job posts for a Robotics & Mechatronics "
                    "engineer who wants STEAM/robotics/coding/informatics teaching jobs, "
                    "and is also open to robotics/mechatronics/embedded/computer-vision/"
                    "data-science engineering roles. He does NOT want pure web/backend "
                    "software developer, cybersecurity, or IT-support/sysadmin roles."
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
Candidate profile: Robotics & Mechatronics engineer. Skills: Python, C/C++, embedded
(Raspberry Pi, Jetson, sensors, motor drivers), computer vision / ML, SOLIDWORKS / 3D
printing / CNC. Has taught robotics & electronics.

HIGH_MATCH:
- STEAM/STEM, robotics, coding, programming, informatics teacher/instructor/mentor
- technology education for children / academies / courses / schools

MAYBE_MATCH:
- robotics/mechatronics/embedded/electronics/automation/RPA engineering roles
- computer vision / machine learning / data science / AI roles

NO_MATCH:
- pure web/backend/frontend/software developer roles
- cybersecurity / penetration / infosec roles
- IT support / sysadmin / network / DevOps roles
- sales, accounting, call center, office manager, driver, and other non-technical roles
- non-technology teachers (English, maths, language, etc.)

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
