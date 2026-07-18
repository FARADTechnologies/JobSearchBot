from __future__ import annotations

import io
import json
import re
from collections import Counter

import requests

from .config import Config


def pdf_bytes_to_text(data: bytes) -> str:
    """Extract text from a PDF. Returns '' for image-based PDFs."""
    from pypdf import PdfReader  # local import: keeps startup fast

    reader = PdfReader(io.BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - a single broken page must not kill intake
            continue
    return re.sub(r"[ \t]+", " ", "\n".join(parts)).strip()


# Minimal multi-language stopwords (az/tr/en/ru) for the heuristic profile.
STOPWORDS = {
    "and", "the", "for", "with", "that", "this", "from", "have", "has", "was", "were",
    "are", "not", "you", "your", "our", "их", "как", "что", "для", "или", "это",
    "или", "год", "лет", "опыт", "работа", "работы", "ve", "ile", "bir", "bu", "da",
    "de", "en", "ki", "olan", "olarak", "üçün", "ucun", "üzrə", "uzre", "daxil",
    "etmək", "etmek", "edir", "var", "yox", "aid", "digər", "diger", "həm", "hem",
    "based", "using", "used", "such", "into", "also", "can", "will", "all", "its",
    "than", "more", "other", "etc", "il", "ay", "gün", "gun", "may", "one", "two",
}


def build_heuristic_profile(raw_text: str) -> dict:
    """Placeholder profile until the LLM extractor runs: top distinctive terms.

    Works for any profession/language without an LLM. Replaced by Groq when
    GROQ_API_KEY is configured (see extract_profile).
    """
    words = re.findall(r"[a-zA-ZəüöğışçƏÜÖĞIŞÇа-яА-Я+#.]{3,}", raw_text.lower())
    words = [w.strip(".") for w in words if w not in STOPWORDS and not w.isdigit()]
    counts = Counter(words)
    top_terms = [term for term, _ in counts.most_common(60)]
    return {
        "summary": raw_text[:600],
        "skills": [],
        "job_titles": [],
        "categories": [],
        "seniority": "any",
        "languages": [],
        "exclude": [],
        "top_terms": top_terms,
    }


GROQ_PROMPT = """You extract a structured job-seeker profile from a CV.
Return ONLY valid JSON with these keys:
- summary: 2-3 sentence English summary of who this person is professionally
- skills: list of concrete skills (English, lowercase)
- job_titles: list of job titles this person is qualified for (English, lowercase)
- categories: broad fields, e.g. ["robotics", "teaching", "software", "finance"]
- seniority: one of "intern", "junior", "mid", "senior"
- languages: spoken languages as ISO codes, e.g. ["az", "en", "ru", "tr"]
- exclude: role types clearly NOT fitting this person (English, lowercase)
- top_terms: 40 most distinctive terms for matching (English, lowercase)

CV text:
"""


def extract_profile(raw_text: str, config: Config) -> tuple[dict, str]:
    """Returns (profile, source). Uses Groq when configured, else heuristic.

    Privacy rule (ARCHITECTURE.md): CVs are personal data -> only providers that
    do NOT train on API data (Groq/Cohere/Cerebras). Never free-tier Gemini.
    """
    if config.groq_api_key:
        try:
            return groq_extract_profile(raw_text, config), "groq"
        except Exception as exc:  # noqa: BLE001 - degrade gracefully, never block intake
            print(f"Groq profile extraction failed, using heuristic: {exc}")
    return build_heuristic_profile(raw_text), "heuristic"


def groq_extract_profile(raw_text: str, config: Config) -> dict:
    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {config.groq_api_key}"},
        json={
            "model": config.groq_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": GROQ_PROMPT + raw_text[:15000]}],
        },
        timeout=60,
    )
    response.raise_for_status()
    profile = json.loads(response.json()["choices"][0]["message"]["content"])
    profile.setdefault("top_terms", [])
    return profile
