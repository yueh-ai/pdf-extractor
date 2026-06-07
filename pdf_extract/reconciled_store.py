from __future__ import annotations

import hashlib
import json
import sqlite3
from types import MappingProxyType
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


PUBLISHED = "published"
PUBLISH_FAILED = "publish_failed"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


@dataclass(frozen=True)
class PageReconciliationResult:
    document_id: str
    page: int
    reconciled_markdown: str
    winner: str
    warnings: Sequence[str]
    needs_human_review: bool
    model: str | None
    prompt_version: str | None
    source_refs: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.document_id:
            raise ValueError("document_id is required")
        if self.page < 1:
            raise ValueError("page must be >= 1")
        if self.reconciled_markdown is None:
            raise ValueError("reconciled_markdown is required")
        if self.winner not in {"union", "small", "mixed", "uncertain"}:
            raise ValueError(f"Unsupported winner: {self.winner}")
        for key in ("page_image", "union_markdown", "small_markdown"):
            if key not in self.source_refs:
                raise ValueError(f"source_refs.{key} is required")
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "source_refs", MappingProxyType(dict(self.source_refs)))

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def decision_payload(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "page": self.page,
            "winner": self.winner,
            "warnings": list(self.warnings),
            "needs_human_review": self.needs_human_review,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "source_refs": dict(self.source_refs),
        }


@dataclass(frozen=True)
class PublishedPage:
    document_id: str
    page: int
    status: str
    markdown_key: str | None
    assets_key: str | None
    decision_key: str | None
    markdown_sha256: str | None
    asset_count: int
    error_message: str | None = None


class LocalObjectStore:
    def __init__(self, root: Path):
        self.root = root

    def path_for_key(self, key: str) -> Path:
        if key.startswith("/") or ".." in Path(key).parts:
            raise ValueError(f"Invalid object key: {key}")
        return self.root / key

    def write_text(self, key: str, text: str) -> Path:
        path = self.path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_json(self, key: str, payload: dict[str, Any]) -> Path:
        return self.write_text(key, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    def write_bytes(self, key: str, data: bytes) -> Path:
        path = self.path_for_key(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def read_text(self, key: str) -> str:
        return self.path_for_key(key).read_text(encoding="utf-8")


class PageCatalog:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pages (
                  document_id TEXT NOT NULL,
                  page INTEGER NOT NULL,
                  status TEXT NOT NULL,
                  markdown_key TEXT,
                  assets_key TEXT,
                  decision_key TEXT,
                  needs_human_review INTEGER NOT NULL DEFAULT 0,
                  warning_count INTEGER NOT NULL DEFAULT 0,
                  asset_count INTEGER NOT NULL DEFAULT 0,
                  markdown_sha256 TEXT,
                  markdown_text TEXT,
                  error_message TEXT,
                  published_at TEXT NOT NULL,
                  PRIMARY KEY (document_id, page)
                )
                """
            )
