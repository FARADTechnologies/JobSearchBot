from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from .models import Job


# JobSearch.az is a Nuxt SPA. The public site renders only the first ~30 jobs in
# server HTML; the real, paginated data comes from this JSON API. The endpoint
# only returns JSON when the "X-Requested-With: XMLHttpRequest" header is sent -
# otherwise it serves the HTML shell (this was the bug that limited the bot to 30
# jobs and made it miss almost every listing).
API_BASE = "https://jobsearch.az/api-az/vacancies-az"

LIST_QUERY = (
    "?hl=az&q=&posted_date=&seniority=&categories=&industries="
    "&ads=&location=&job_type=&salary=&order_by="
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json",
}


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def fetch_all_jobs(session: requests.Session | None = None, max_pages: int = 300) -> list[Job]:
    """Return every vacancy on the site by following the API's `next` cursor."""
    session = session or build_session()
    url = API_BASE + LIST_QUERY

    jobs: list[Job] = []
    seen_ids: set[str] = set()
    pages = 0

    while url and pages < max_pages:
        response = session.get(url, timeout=25)
        response.raise_for_status()
        data = response.json()

        items = data.get("items", [])
        for item in items:
            job = job_from_item(item)
            if job.id in seen_ids:
                continue
            seen_ids.add(job.id)
            jobs.append(job)

        pages += 1
        next_url = data.get("next")
        url = same_origin(next_url) if next_url else None
        if not items:
            break

    return jobs


def job_from_item(item: dict) -> Job:
    slug = item.get("slug") or str(item.get("id", ""))
    company = ""
    company_data = item.get("company")
    if isinstance(company_data, dict):
        company = clean_text(company_data.get("title", ""))

    return Job(
        id=str(item.get("id") or slug),
        title=clean_text(item.get("title", "")),
        company=company,
        url=f"https://jobsearch.az/vacancies/{slug}",
        date_text=str(item.get("created_at", "")),
    )


def enrich_job(job: Job, session: requests.Session | None = None) -> Job:
    """Fetch a single vacancy's full text + category from the detail API."""
    session = session or build_session()
    slug = job.url.rstrip("/").rsplit("/", 1)[-1]
    response = session.get(f"{API_BASE}/{slug}?hl=az", timeout=25)
    response.raise_for_status()
    data = response.json()

    title = clean_text(data.get("title", "")) or job.title

    company = job.company
    company_data = data.get("company")
    if isinstance(company_data, dict) and company_data.get("title"):
        company = clean_text(company_data.get("title", ""))

    category = ""
    category_data = data.get("category")
    if isinstance(category_data, dict):
        category = clean_text(category_data.get("title", ""))
    elif isinstance(category_data, str):
        category = clean_text(category_data)

    description = html_to_text(data.get("text", ""))

    full_description = "\n".join(part for part in [category, description] if part)

    return Job(
        id=job.id,
        title=title,
        company=company,
        url=job.url,
        date_text=job.date_text,
        summary=category,
        description=full_description[:12000],
    )


def same_origin(url: str) -> str:
    """Rewrite the API's absolute `next` URL to the main host we already use."""
    parts = urlsplit(url)
    return urlunsplit(("https", "jobsearch.az", parts.path, parts.query, ""))


def html_to_text(html: str) -> str:
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return clean_text(soup.get_text(" ", strip=True))


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()
