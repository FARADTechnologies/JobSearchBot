"""Global remote job boards (public, free, no-auth APIs).

Additive feature: a separate "remote track" for the user's personal job search.
Does NOT touch the existing jobsearch.az flow. Each source is isolated and
failure-tolerant: one bad source never breaks the others or the rest of the run.
"""
from __future__ import annotations

import html
import re

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobSearchBot/1.0; personal job alerts)",
    "Accept": "application/json",
}

# Broad tech / knowledge-work / AI-doable net. Remote boards are ~90% these
# already; this drops clearly-unfit roles (clinical, licensed, physical, pure
# sales) while keeping anything the user could plausibly do, incl. with AI.
RELEVANCE = re.compile(
    r"\b("
    r"engineer|developer|programmer|software|backend|back-end|frontend|front-end|full.?stack|"
    r"data|analyst|analytics|scien|machine learning|\bml\b|\bai\b|artificial intelligence|"
    r"deep learning|computer vision|\bnlp\b|llm|prompt|automation|robotic|embedded|firmware|"
    r"devops|cloud|aws|azure|gcp|kubernetes|docker|platform|infrastructure|sre|"
    r"python|javascript|typescript|react|node|golang|rust|\bc\+\+|java\b|"
    r"\bqa\b|test|quality|technical|architect|database|\bsql\b|"
    r"research|writer|content|copywrit|editor|documentation|technical writer|"
    r"designer|design|\bui\b|\bux\b|product manager|project manager|scrum|agile|"
    r"no.?code|web|api|integration|support engineer|solutions|consultant"
    r")\b",
    re.I,
)

# Hard drops even if a relevance word sneaks in.
EXCLUDE = re.compile(
    r"\b(nurse|nursing|clinical|therapist|dentist|physician|pharmacist|"
    r"real estate|insurance agent|driver|warehouse|forklift|"
    r"account executive|sales representative|sales rep|door.?to.?door|"
    r"cleaner|janitor|security guard)\b",
    re.I,
)


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def is_relevant(title: str, extra: str) -> bool:
    blob = f"{title} {extra}"
    if EXCLUDE.search(blob):
        return False
    return bool(RELEVANCE.search(blob))


# An Azerbaijan resident can realistically take these; drop region-locked ones.
GEO_ELIGIBLE = re.compile(
    r"worldwide|anywhere|global|remote|emea|europe|asia|middle east|cis|"
    r"azerbaijan|turkey|türkiye|any location|international", re.I
)
GEO_RESTRICTED = re.compile(
    r"\b(usa|u\.s\.|united states|us only|us-based|canada|americas|latam|"
    r"latin america|mexico|brazil|argentina|australia|new zealand)\b", re.I
)


def is_geo_eligible(location: str) -> bool:
    """Keep worldwide/EMEA/Europe-eligible; drop clearly region-locked. Unknown -> keep."""
    if not location:
        return True
    if GEO_ELIGIBLE.search(location):
        return True
    if GEO_RESTRICTED.search(location):
        return False
    return True  # benefit of the doubt for anything unrecognised


def _get(url: str) -> requests.Response:
    return requests.get(url, headers=HEADERS, timeout=25)


# ------------------------------------------------------------------ sources

def fetch_remotive() -> list[dict]:
    data = _get("https://remotive.com/api/remote-jobs?limit=200").json()
    out = []
    for j in data.get("jobs", []):
        out.append(
            {
                "id": f"remotive-{j.get('id')}",
                "source": "Remotive",
                "title": clean(j.get("title", "")),
                "company": clean(j.get("company_name", "")),
                "url": j.get("url", ""),
                "job_type": (j.get("job_type") or "").replace("_", "-"),
                "location": clean(j.get("candidate_required_location", "")),
                "salary": clean(j.get("salary", "")),
                "date": (j.get("publication_date") or "")[:10],
                "tags": [str(t) for t in (j.get("tags") or [])],
                "category": clean(j.get("category", "")),
            }
        )
    return out


def fetch_remoteok() -> list[dict]:
    data = _get("https://remoteok.com/api").json()
    out = []
    for j in data:
        if not isinstance(j, dict) or not j.get("id"):
            continue  # first element is a legal notice
        out.append(
            {
                "id": f"remoteok-{j.get('id')}",
                "source": "RemoteOK",
                "title": clean(j.get("position", "")),
                "company": clean(j.get("company", "")),
                "url": j.get("url") or j.get("apply_url", ""),
                "job_type": "",
                "location": clean(j.get("location", "")) or "Remote",
                "salary": _salary(j.get("salary_min"), j.get("salary_max")),
                "date": (j.get("date") or "")[:10],
                "tags": [str(t) for t in (j.get("tags") or [])],
                "category": "",
            }
        )
    return out


def fetch_arbeitnow() -> list[dict]:
    data = _get("https://www.arbeitnow.com/api/job-board-api").json()
    out = []
    for j in data.get("data", []):
        if not j.get("remote"):
            continue  # keep only remote ones
        out.append(
            {
                "id": f"arbeitnow-{j.get('slug')}",
                "source": "Arbeitnow",
                "title": clean(j.get("title", "")),
                "company": clean(j.get("company_name", "")),
                "url": j.get("url", ""),
                "job_type": ", ".join(j.get("job_types") or []),
                "location": clean(j.get("location", "")),
                "salary": "",
                "date": "",
                "tags": [str(t) for t in (j.get("tags") or [])],
                "category": "",
            }
        )
    return out


def fetch_jobicy() -> list[dict]:
    data = _get("https://jobicy.com/api/v2/remote-jobs?count=100").json()
    out = []
    for j in data.get("jobs", []):
        out.append(
            {
                "id": f"jobicy-{j.get('id')}",
                "source": "Jobicy",
                "title": clean(j.get("jobTitle", "")),
                "company": clean(j.get("companyName", "")),
                "url": j.get("url", ""),
                "job_type": ", ".join(j.get("jobType") or []) if isinstance(j.get("jobType"), list) else clean(str(j.get("jobType", ""))),
                "location": clean(j.get("jobGeo", "")) or "Anywhere",
                "salary": "",
                "date": (j.get("pubDate") or "")[:10],
                "tags": [],
                "category": clean(j.get("jobIndustry", "") if isinstance(j.get("jobIndustry"), str) else ""),
            }
        )
    return out


def fetch_adzuna(app_id: str, app_key: str, pages: int = 3) -> list[dict]:
    """Adzuna aggregates millions of listings across countries. We query several
    countries (multiple pages) for 'remote' postings; the LLM decides eligibility."""
    countries = ["gb", "us", "de", "nl", "ie", "at", "fr", "au", "in", "sg", "ca"]
    out = []
    for c in countries:
        for page in range(1, pages + 1):
            try:
                url = (
                    f"https://api.adzuna.com/v1/api/jobs/{c}/search/{page}"
                    f"?app_id={app_id}&app_key={app_key}&results_per_page=50"
                    f"&what=remote&content-type=application/json"
                )
                results = _get(url).json().get("results", [])
            except Exception:  # noqa: BLE001 - one page failing must not stop the rest
                break
            if not results:
                break
            for j in results:
                out.append(
                    {
                        "id": f"adzuna-{j.get('id')}",
                        "source": f"Adzuna/{c}",
                        "title": clean(j.get("title", "")),
                        "company": clean((j.get("company") or {}).get("display_name", "")),
                        "url": j.get("redirect_url", ""),
                        "job_type": (j.get("contract_time") or "").replace("_", "-"),
                        "location": clean((j.get("location") or {}).get("display_name", "")),
                        "salary": _salary(j.get("salary_min"), j.get("salary_max")),
                        "date": (j.get("created") or "")[:10],
                        "tags": [],
                        "category": clean((j.get("category") or {}).get("label", "")),
                    }
                )
    return out


def fetch_themuse(pages: int = 3) -> list[dict]:
    """The Muse public API (no key). Remote-flexible jobs."""
    out = []
    for page in range(1, pages + 1):
        try:
            url = f"https://www.themuse.com/api/public/jobs?page={page}&location=Flexible%20%2F%20Remote"
            results = _get(url).json().get("results", [])
        except Exception:  # noqa: BLE001
            break
        if not results:
            break
        for j in results:
            locs = ", ".join(l.get("name", "") for l in (j.get("locations") or []))
            out.append(
                {
                    "id": f"themuse-{j.get('id')}",
                    "source": "TheMuse",
                    "title": clean(j.get("name", "")),
                    "company": clean((j.get("company") or {}).get("name", "")),
                    "url": (j.get("refs") or {}).get("landing_page", ""),
                    "job_type": clean(j.get("type", "")),
                    "location": clean(locs) or "Remote",
                    "salary": "",
                    "date": (j.get("publication_date") or "")[:10],
                    "tags": [c.get("name", "") for c in (j.get("categories") or [])],
                    "category": ", ".join(l.get("name", "") for l in (j.get("levels") or [])),
                }
            )
    return out


def _salary(lo, hi) -> str:
    if lo and hi:
        return f"${int(lo)//1000}k-${int(hi)//1000}k"
    return ""


def salary_min_usd(text: str) -> int | None:
    """Best-effort lower salary bound from a fuzzy string. None if unknown."""
    if not text:
        return None
    m = re.search(r"(\d[\d,\.]*)\s*([kK])?", text.replace(",", ""))
    if not m:
        return None
    try:
        value = float(m.group(1))
    except ValueError:
        return None
    if m.group(2):
        value *= 1000
    return int(value)


def passes_salary(job: dict, floor: int) -> bool:
    """Keep jobs at/above floor. Unknown salary -> kept (don't drop on missing data)."""
    if floor <= 0:
        return True
    low = salary_min_usd(job.get("salary", ""))
    return low is None or low >= floor


SOURCES = [fetch_remotive, fetch_remoteok, fetch_arbeitnow, fetch_jobicy, fetch_themuse]


def fetch_global_remote(log=print, geo_filter: bool = True, adzuna: tuple | None = None) -> list[dict]:
    """Fetch + relevance-filter + (optional) geo-filter + dedup. Never raises."""
    sources = list(SOURCES)
    if adzuna and adzuna[0] and adzuna[1]:
        sources.append(lambda: fetch_adzuna(adzuna[0], adzuna[1]))

    collected: list[dict] = []
    for fetch in sources:
        try:
            rows = fetch()
            kept = [
                r
                for r in rows
                if r.get("url")
                and is_relevant(r["title"], " ".join(r.get("tags", [])) + " " + r.get("category", ""))
                and (not geo_filter or is_geo_eligible(r.get("location", "")))
            ]
            collected.extend(kept)
            log(f"  {fetch.__name__}: {len(rows)} fetched, {len(kept)} relevant+eligible")
        except Exception as exc:  # noqa: BLE001
            log(f"  {fetch.__name__}: FAILED ({exc})")

    # Dedup: same role reposted across boards -> company+title fingerprint.
    seen_fp: set[str] = set()
    unique: list[dict] = []
    for r in collected:
        fp = re.sub(r"\W+", "", f"{r['company']}{r['title']}".lower())
        if fp in seen_fp:
            continue
        seen_fp.add(fp)
        unique.append(r)
    return unique
