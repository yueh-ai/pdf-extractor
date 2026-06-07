from __future__ import annotations

import hashlib
import mimetypes
import json
import sqlite3
import re
from types import MappingProxyType
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .render import page_dir_name


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

    def upsert_page(
        self,
        published: PublishedPage,
        markdown_text: str | None,
        needs_human_review: bool,
        warning_count: int,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO pages (
                  document_id,
                  page,
                  status,
                  markdown_key,
                  assets_key,
                  decision_key,
                  needs_human_review,
                  warning_count,
                  asset_count,
                  markdown_sha256,
                  markdown_text,
                  error_message,
                  published_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id, page) DO UPDATE SET
                  status = excluded.status,
                  markdown_key = excluded.markdown_key,
                  assets_key = excluded.assets_key,
                  decision_key = excluded.decision_key,
                  needs_human_review = excluded.needs_human_review,
                  warning_count = excluded.warning_count,
                  asset_count = excluded.asset_count,
                  markdown_sha256 = excluded.markdown_sha256,
                  markdown_text = excluded.markdown_text,
                  error_message = excluded.error_message,
                  published_at = excluded.published_at
                """,
                (
                    published.document_id,
                    published.page,
                    published.status,
                    published.markdown_key,
                    published.assets_key,
                    published.decision_key,
                    int(needs_human_review),
                    warning_count,
                    published.asset_count,
                    published.markdown_sha256,
                    markdown_text,
                    published.error_message,
                    utc_now_iso(),
                ),
            )


_HTML_IMAGE_SRC_RE = re.compile(
    r'(<img\b[^>]*\bsrc\s*=\s*)(?P<quote>["\'])(?P<path>[^"\']+)(?P=quote)',
    re.IGNORECASE,
)
_MARKDOWN_IMAGE_RE = re.compile(r"(!\[[^\]]*\]\()(?P<path>[^)\s]+)(\))")


def page_prefix(document_id: str, page: int) -> str:
    return f"pdf-extract/reconciled/{document_id}/pages/{page_dir_name(page)}"


def asset_uri_for_key(key: str) -> str:
    return f"asset://{key}"


def iter_markdown_image_refs(markdown: str) -> list[str]:
    refs: list[str] = []

    for match in _HTML_IMAGE_SRC_RE.finditer(markdown):
        refs.append(match.group("path"))

    for match in _MARKDOWN_IMAGE_RE.finditer(markdown):
        refs.append(match.group("path"))

    return [
        ref
        for ref in refs
        if not (
            ref.startswith("asset://")
            or ref.startswith("http://")
            or ref.startswith("https://")
            or ref.startswith("data:")
        )
    ]


def resolve_asset_path(ref: str, asset_base_dir: Path) -> Path:
    if Path(ref).is_absolute():
        return Path(ref)
    if ref.startswith("pages/"):
        return asset_base_dir.parent.parent / ref
    return asset_base_dir / ref


def stable_asset_name(source_path: Path, used_names: set[str]) -> str:
    name = source_path.name
    if name not in used_names:
        return name

    stem = source_path.stem
    suffix = source_path.suffix
    hash_suffix = sha256_text(str(source_path))[:8]
    return f"{stem}_{hash_suffix}{suffix}"


def rewrite_markdown_image_refs(markdown: str, replacements: dict[str, str]) -> str:
    def _replace_html(match: re.Match[str]) -> str:
        original = match.group("path")
        if original in replacements:
            quote = match.group("quote")
            return f"{match.group(1)}{quote}{replacements[original]}{quote}"
        return match.group(0)

    rewritten = _HTML_IMAGE_SRC_RE.sub(_replace_html, markdown)
    return _MARKDOWN_IMAGE_RE.sub(
        lambda match: (
            f"{match.group(1)}{replacements[match.group('path')]}{match.group(3)}"
            if match.group("path") in replacements
            else match.group(0)
        ),
        rewritten,
    )


class ReconciledPagePublisher:
    def __init__(self, store: LocalObjectStore, catalog: PageCatalog):
        self.store = store
        self.catalog = catalog
        self.catalog.init_schema()

    def publish(self, result: PageReconciliationResult, asset_base_dir: Path) -> PublishedPage:
        try:
            return self._publish_success(result, asset_base_dir)
        except FileNotFoundError as exc:
            published = PublishedPage(
                document_id=result.document_id,
                page=result.page,
                status=PUBLISH_FAILED,
                markdown_key=None,
                assets_key=None,
                decision_key=None,
                markdown_sha256=None,
                asset_count=0,
                error_message=str(exc),
            )
            self.catalog.upsert_page(
                published,
                markdown_text=None,
                needs_human_review=result.needs_human_review,
                warning_count=result.warning_count,
            )
            return published

    def _publish_success(
        self,
        result: PageReconciliationResult,
        asset_base_dir: Path,
    ) -> PublishedPage:
        prefix = page_prefix(result.document_id, result.page)
        markdown_key = f"{prefix}/output.md"
        assets_key = f"{prefix}/assets.json"
        decision_key = f"{prefix}/decision.json"
        asset_prefix = f"{prefix}/assets"

        referenced_assets = iter_markdown_image_refs(result.reconciled_markdown)
        used_names: set[str] = set()
        replacements: dict[str, str] = {}
        assets: list[dict[str, Any]] = []

        for ref in referenced_assets:
            source_path = resolve_asset_path(ref, asset_base_dir)
            if not source_path.exists():
                raise FileNotFoundError(f"Missing referenced asset: {ref}")

            asset_name = stable_asset_name(source_path, used_names)
            used_names.add(asset_name)
            asset_key = f"{asset_prefix}/{asset_name}"
            asset_data = source_path.read_bytes()
            self.store.write_bytes(asset_key, asset_data)
            replacements[ref] = asset_uri_for_key(asset_key)

            mime_type, _ = mimetypes.guess_type(source_path.as_posix())
            asset_payload: dict[str, Any] = {
                "source_path": str(source_path),
                "dest_key": asset_key,
                "sha256": sha256_bytes(asset_data),
                "size": len(asset_data),
            }
            if mime_type is not None:
                asset_payload["mimetype"] = mime_type
            assets.append(asset_payload)

        rewritten_markdown = rewrite_markdown_image_refs(result.reconciled_markdown, replacements)
        self.store.write_text(markdown_key, rewritten_markdown)
        self.store.write_json(
            assets_key,
            {
                "document_id": result.document_id,
                "page": result.page,
                "assets": assets,
            },
        )
        self.store.write_json(decision_key, result.decision_payload())
        markdown_sha256 = sha256_text(rewritten_markdown)

        published = PublishedPage(
            document_id=result.document_id,
            page=result.page,
            status=PUBLISHED,
            markdown_key=markdown_key,
            assets_key=assets_key,
            decision_key=decision_key,
            markdown_sha256=markdown_sha256,
            asset_count=len(assets),
        )
        self.catalog.upsert_page(
            published,
            markdown_text=rewritten_markdown,
            needs_human_review=result.needs_human_review,
            warning_count=result.warning_count,
        )
        return published
