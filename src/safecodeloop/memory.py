from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from safecodeloop.llm import redact_secrets


@dataclass(frozen=True)
class MemoryItem:
    id: str
    content: str
    kind: str
    priority: int
    created_at: str

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "MemoryItem":
        return cls(
            id=str(payload["id"]),
            content=str(payload["content"]),
            kind=str(payload["kind"]),
            priority=int(payload["priority"]),
            created_at=str(payload["created_at"]),
        )


class MemoryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._items = self._load()

    def remember(self, content: str, kind: str = "note", priority: int = 1) -> MemoryItem:
        item = MemoryItem(
            id=uuid4().hex,
            content=redact_secrets(content),
            kind=kind,
            priority=priority,
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        self._items.append(item)
        self._save()
        return item

    def all(self) -> list[MemoryItem]:
        return list(self._items)

    def retrieve(self, query: str, limit: int = 5) -> list[MemoryItem]:
        if limit < 1:
            return []
        terms = {term.lower() for term in query.split() if term.strip()}
        scored = []
        for index, item in enumerate(self._items):
            haystack = f"{item.content} {item.kind}".lower()
            matches = sum(1 for term in terms if term in haystack)
            if matches == 0:
                continue
            scored.append((matches, index, item.priority, item))

        scored.sort(key=lambda row: (row[0], row[1], row[2]), reverse=True)
        return [item for _, _, _, item in scored[:limit]]

    def _load(self) -> list[MemoryItem]:
        if not self.path.exists():
            return []
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise ValueError("memory file must contain a JSON list")
        return [MemoryItem.from_dict(item) for item in payload]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [item.to_dict() for item in self._items]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
