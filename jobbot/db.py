from __future__ import annotations

import json
from typing import Any

import requests


class SupabaseDB:
    """Thin PostgREST client for Supabase using the secret (service_role) key.

    No extra dependency: plain HTTPS calls to <url>/rest/v1/<table>.
    """

    def __init__(self, url: str, secret_key: str) -> None:
        self.base = url.rstrip("/") + "/rest/v1"
        self.session = requests.Session()
        self.session.headers.update(
            {
                "apikey": secret_key,
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/json",
            }
        )

    # ---------- low level ----------

    def _req(
        self,
        method: str,
        table: str,
        params: dict | None = None,
        payload: Any = None,
        headers: dict | None = None,
    ) -> list:
        response = self.session.request(
            method,
            f"{self.base}/{table}",
            params=params,
            data=json.dumps(payload) if payload is not None else None,
            headers=headers,
            timeout=30,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Supabase {method} {table}: {response.status_code} {response.text[:300]}")
        if response.text:
            try:
                return response.json()
            except ValueError:
                return []
        return []

    def select(self, table: str, params: dict, limit: int = 1000, offset: int = 0) -> list:
        headers = {"Range-Unit": "items", "Range": f"{offset}-{offset + limit - 1}"}
        return self._req("GET", table, params=params, headers=headers)

    def select_all(self, table: str, params: dict, page: int = 1000) -> list:
        rows: list = []
        offset = 0
        while True:
            batch = self.select(table, params, limit=page, offset=offset)
            rows.extend(batch)
            if len(batch) < page:
                return rows
            offset += page

    def insert(self, table: str, rows: list | dict, upsert_on: str | None = None) -> list:
        headers = {"Prefer": "return=representation"}
        params = {}
        if upsert_on:
            headers["Prefer"] = "resolution=merge-duplicates,return=representation"
            params["on_conflict"] = upsert_on
        return self._req("POST", table, params=params, payload=rows, headers=headers)

    def update(self, table: str, filters: dict, patch: dict) -> list:
        return self._req("PATCH", table, params=filters, payload=patch, headers={"Prefer": "return=representation"})

    # ---------- app_state ----------

    def get_state(self, key: str, default: Any = None) -> Any:
        rows = self.select("app_state", {"key": f"eq.{key}", "select": "value"})
        return rows[0]["value"] if rows else default

    def set_state(self, key: str, value: Any) -> None:
        self.insert("app_state", {"key": key, "value": value}, upsert_on="key")

    # ---------- users ----------

    def get_user_by_chat(self, chat_id: int) -> dict | None:
        rows = self.select("users", {"telegram_chat_id": f"eq.{chat_id}", "select": "*"})
        return rows[0] if rows else None

    def create_user(self, chat_id: int, username: str = "", full_name: str = "") -> dict:
        rows = self.insert(
            "users",
            {"telegram_chat_id": chat_id, "telegram_username": username, "full_name": full_name},
            upsert_on="telegram_chat_id",
        )
        return rows[0]

    def update_user(self, user_id: str, patch: dict) -> None:
        self.update("users", {"id": f"eq.{user_id}"}, patch)

    def active_users(self) -> list:
        return self.select_all("users", {"state": "eq.active", "select": "*"})

    # ---------- cvs ----------

    def save_cv(self, user_id: str, file_name: str, raw_text: str, profile: dict, source: str) -> dict:
        # Deactivate previous CVs, keep exactly one active per user.
        self.update("cvs", {"user_id": f"eq.{user_id}", "is_active": "eq.true"}, {"is_active": False})
        rows = self.insert(
            "cvs",
            {
                "user_id": user_id,
                "file_name": file_name,
                "raw_text": raw_text,
                "profile": profile,
                "profile_source": source,
            },
        )
        return rows[0]

    def get_active_cv(self, user_id: str) -> dict | None:
        rows = self.select(
            "cvs",
            {"user_id": f"eq.{user_id}", "is_active": "eq.true", "select": "id,profile,profile_source,file_name"},
        )
        return rows[0] if rows else None

    # ---------- jobs (shared corpus) ----------

    def upsert_jobs(self, jobs: list[dict]) -> None:
        for i in range(0, len(jobs), 500):
            self._req(
                "POST",
                "jobs",
                params={"on_conflict": "id"},
                payload=jobs[i : i + 500],
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            )

    def job_texts(self, job_ids: list[str]) -> dict[str, dict]:
        """Fetch cached descriptions for the given ids. Returns {id: row}."""
        out: dict[str, dict] = {}
        for i in range(0, len(job_ids), 100):
            chunk = job_ids[i : i + 100]
            rows = self.select(
                "jobs",
                {"id": f"in.({','.join(chunk)})", "select": "id,description,category,deadline_at"},
                limit=100,
            )
            for row in rows:
                out[row["id"]] = row
        return out

    def cache_job_text(self, job_id: str, description: str, category: str, deadline_at: str | None) -> None:
        patch: dict = {"description": description, "category": category}
        if deadline_at:
            patch["deadline_at"] = deadline_at
        self.update("jobs", {"id": f"eq.{job_id}"}, patch)

    # ---------- matches (per-user seen + decisions) ----------

    def match_job_ids(self, user_id: str) -> set[str]:
        rows = self.select_all("matches", {"user_id": f"eq.{user_id}", "select": "job_id"})
        return {row["job_id"] for row in rows}

    def record_matches(self, rows: list[dict]) -> None:
        for i in range(0, len(rows), 500):
            self._req(
                "POST",
                "matches",
                params={"on_conflict": "user_id,job_id"},
                payload=rows[i : i + 500],
                headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            )
