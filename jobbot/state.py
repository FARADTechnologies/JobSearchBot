from __future__ import annotations

import json
from pathlib import Path


class SeenStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.seen: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = []

        if isinstance(data, list):
            self.seen = {str(item) for item in data}

    def has(self, job_id: str) -> bool:
        return job_id in self.seen

    def add(self, job_id: str) -> None:
        self.seen.add(job_id)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(sorted(self.seen), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
