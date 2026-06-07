# Page Asset Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a page-first fake-S3 + SQLite publishing slice for reconciled Markdown, then validate it with three pages and a static viewer.

**Architecture:** Add a focused asset-store module that accepts `PageReconciliationResult`, writes page artifacts to a filesystem-backed object store, rewrites image links to `asset://` URIs, and stores a thin `pages` catalog row in SQLite. Add an assembler that joins published page Markdown, a prototype generator that fakes three pipeline outputs from `runs/Full_30015375000000`, and a static viewer generator that reads SQLite plus object-store artifacts.

**Tech Stack:** Python 3.10 stdlib (`dataclasses`, `hashlib`, `json`, `mimetypes`, `re`, `shutil`, `sqlite3`, `html`, `pathlib`), existing `pdf_extract` helpers, pytest.

---

## File Structure

- Create `pdf_extract/reconciled_store.py`
  - Data contracts: `PageReconciliationResult`, `PublishedPage`.
  - Fake-S3 helper: `LocalObjectStore`.
  - SQLite helper: `PageCatalog`.
  - Publisher: `ReconciledPagePublisher`.
  - Assembly function: `assemble_document()`.
- Create `pdf_extract/reconciled_prototype.py`
  - Builds three fake `PageReconciliationResult` objects from existing run pages.
  - Publishes them, assembles them, and writes a static viewer.
  - Exposes `run_three_page_prototype()`.
- Create `scripts/run_reconciled_store_prototype.py`
  - Thin CLI wrapper for the prototype.
- Create `tests/test_reconciled_store.py`
  - Unit tests for object keys, SQLite schema, publishing, link rewriting, idempotency, errors, and assembly.
- Create `tests/test_reconciled_prototype.py`
  - End-to-end prototype test using synthetic page directories in `tmp_path`, not the large checked-in run.
- Modify `README.md`
  - Add a short section explaining how to run the prototype and open the static viewer.

## Task 1: Contracts, Object Store, And SQLite Schema

**Files:**
- Create: `tests/test_reconciled_store.py`
- Create: `pdf_extract/reconciled_store.py`

- [ ] **Step 1: Write the failing tests**

Add `tests/test_reconciled_store.py`:

```python
import json
import sqlite3

from pdf_extract.reconciled_store import (
    LocalObjectStore,
    PageCatalog,
    PageReconciliationResult,
    page_dir_name,
)


def test_page_result_validates_required_fields():
    result = PageReconciliationResult(
        document_id="Full_30015375000000",
        page=2,
        reconciled_markdown="hello",
        winner="mixed",
        warnings=[],
        needs_human_review=False,
        model="prototype",
        prompt_version="reconcile-page-v1",
        source_refs={
            "page_image": "runs/doc/union/pages/page_0002/page.png",
            "union_markdown": "runs/doc/union/pages/page_0002/output.md",
            "small_markdown": "runs/doc/small/pages/page_0002/output.md",
        },
    )

    assert result.warning_count == 0
    assert result.decision_payload()["winner"] == "mixed"
    assert result.decision_payload()["source_refs"]["page_image"].endswith("page.png")


def test_local_object_store_writes_and_reads_by_key(tmp_path):
    store = LocalObjectStore(tmp_path / "object_store")

    path = store.write_text("pdf-extract/reconciled/doc/pages/page_0001/output.md", "hi")

    assert path == tmp_path / "object_store/pdf-extract/reconciled/doc/pages/page_0001/output.md"
    assert store.read_text("pdf-extract/reconciled/doc/pages/page_0001/output.md") == "hi"


def test_page_catalog_creates_thin_pages_table(tmp_path):
    db_path = tmp_path / "catalog.sqlite"
    catalog = PageCatalog(db_path)
    catalog.init_schema()

    with sqlite3.connect(db_path) as conn:
        columns = [
            row[1]
            for row in conn.execute("PRAGMA table_info(pages)").fetchall()
        ]

    assert columns == [
        "document_id",
        "page",
        "status",
        "markdown_key",
        "assets_key",
        "decision_key",
        "needs_human_review",
        "warning_count",
        "asset_count",
        "markdown_sha256",
        "markdown_text",
        "error_message",
        "published_at",
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_reconciled_store.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pdf_extract.reconciled_store'`.

- [ ] **Step 3: Implement contracts, object store, and catalog schema**

Create `pdf_extract/reconciled_store.py`:

```python
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    warnings: list[str]
    needs_human_review: bool
    model: str | None
    prompt_version: str | None
    source_refs: dict[str, str]

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

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def decision_payload(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "page": self.page,
            "winner": self.winner,
            "warnings": self.warnings,
            "needs_human_review": self.needs_human_review,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "source_refs": self.source_refs,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_reconciled_store.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_extract/reconciled_store.py tests/test_reconciled_store.py
git commit -m "Add reconciled store contracts"
```

## Task 2: Publish Markdown And Referenced Assets

**Files:**
- Modify: `tests/test_reconciled_store.py`
- Modify: `pdf_extract/reconciled_store.py`

- [ ] **Step 1: Add failing publisher tests**

Append to `tests/test_reconciled_store.py`:

```python
from pathlib import Path

from pdf_extract.reconciled_store import ReconciledPagePublisher


def make_result(markdown: str, page: int = 2) -> PageReconciliationResult:
    return PageReconciliationResult(
        document_id="Full_30015375000000",
        page=page,
        reconciled_markdown=markdown,
        winner="mixed",
        warnings=["prototype warning"],
        needs_human_review=True,
        model="prototype",
        prompt_version="reconcile-page-v1",
        source_refs={
            "page_image": f"runs/doc/union/pages/page_{page:04d}/page.png",
            "union_markdown": f"runs/doc/union/pages/page_{page:04d}/output.md",
            "small_markdown": f"runs/doc/small/pages/page_{page:04d}/output.md",
        },
    )


def test_publish_page_with_no_assets_writes_page_artifacts(tmp_path):
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )

    published = publisher.publish(make_result("# Page body\n\nNo image."), asset_base_dir=tmp_path)

    assert published.status == "published"
    assert published.asset_count == 0
    assert publisher.store.read_text(published.markdown_key) == "# Page body\n\nNo image."
    assets = json.loads(publisher.store.read_text(published.assets_key))
    decision = json.loads(publisher.store.read_text(published.decision_key))
    assert assets == {"document_id": "Full_30015375000000", "page": 2, "assets": []}
    assert decision["winner"] == "mixed"


def test_publish_page_copies_imgs_reference_and_rewrites_to_asset_uri(tmp_path):
    source = tmp_path / "page_0002"
    (source / "imgs").mkdir(parents=True)
    (source / "imgs" / "seal.jpg").write_bytes(b"jpeg")
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )

    published = publisher.publish(
        make_result('<img src="imgs/seal.jpg" alt="Seal" />'),
        asset_base_dir=source,
    )

    rewritten = publisher.store.read_text(published.markdown_key)
    assert 'src="asset://pdf-extract/reconciled/Full_30015375000000/pages/page_0002/assets/seal.jpg"' in rewritten
    assert publisher.store.path_for_key(
        "pdf-extract/reconciled/Full_30015375000000/pages/page_0002/assets/seal.jpg"
    ).read_bytes() == b"jpeg"
    assets = json.loads(publisher.store.read_text(published.assets_key))
    assert assets["assets"][0]["source_path"].endswith("page_0002/imgs/seal.jpg")
    assert assets["assets"][0]["sha256"] == "41e5787e9f28562d07b891b1816b492309d646c0f2829743fa4963a9f9cc1d61"


def test_publish_page_with_missing_asset_records_failure(tmp_path):
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )

    published = publisher.publish(make_result("![missing](imgs/missing.jpg)"), asset_base_dir=tmp_path)

    assert published.status == "publish_failed"
    assert "Missing referenced asset: imgs/missing.jpg" in published.error_message
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_reconciled_store.py -q
```

Expected: FAIL with `ImportError` or `AttributeError` for `ReconciledPagePublisher`.

- [ ] **Step 3: Implement publisher, asset parsing, and link rewriting**

Add these imports and helpers to `pdf_extract/reconciled_store.py`:

```python
import mimetypes
import re


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
        path = match.group("path")
        if not path.startswith(("asset://", "http://", "https://", "data:")):
            refs.append(path)
    for match in _MARKDOWN_IMAGE_RE.finditer(markdown):
        path = match.group("path")
        if not path.startswith(("asset://", "http://", "https://", "data:")):
            refs.append(path)
    return refs


def resolve_asset_path(ref: str, asset_base_dir: Path) -> Path:
    ref_path = Path(ref)
    if ref_path.is_absolute():
        return ref_path
    if ref.startswith("pages/"):
        return asset_base_dir.parent.parent / ref
    return asset_base_dir / ref


def stable_asset_name(source_path: Path, used_names: set[str]) -> str:
    name = source_path.name
    if name not in used_names:
        used_names.add(name)
        return name
    stem = source_path.stem
    suffix = source_path.suffix
    digest = sha256_bytes(source_path.read_bytes())[:8]
    candidate = f"{stem}-{digest}{suffix}"
    used_names.add(candidate)
    return candidate
```

Add this class to `pdf_extract/reconciled_store.py`:

```python
class ReconciledPagePublisher:
    def __init__(self, *, store: LocalObjectStore, catalog: PageCatalog):
        self.store = store
        self.catalog = catalog
        self.catalog.init_schema()

    def publish(
        self, result: PageReconciliationResult, *, asset_base_dir: Path
    ) -> PublishedPage:
        try:
            return self._publish_success(result, asset_base_dir=asset_base_dir)
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
        self, result: PageReconciliationResult, *, asset_base_dir: Path
    ) -> PublishedPage:
        prefix = page_prefix(result.document_id, result.page)
        refs = iter_markdown_image_refs(result.reconciled_markdown)
        replacements: dict[str, str] = {}
        assets: list[dict[str, Any]] = []
        used_names: set[str] = set()

        for ref in refs:
            source_path = resolve_asset_path(ref, asset_base_dir)
            if not source_path.is_file():
                raise FileNotFoundError(f"Missing referenced asset: {ref}")
            asset_name = stable_asset_name(source_path, used_names)
            asset_key = f"{prefix}/assets/{asset_name}"
            data = source_path.read_bytes()
            self.store.write_bytes(asset_key, data)
            asset_uri = asset_uri_for_key(asset_key)
            replacements[ref] = asset_uri
            content_type = mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
            assets.append(
                {
                    "asset_uri": asset_uri,
                    "object_key": asset_key,
                    "source_path": source_path.as_posix(),
                    "description": source_path.stem.replace("_", " "),
                    "content_type": content_type,
                    "sha256": sha256_bytes(data),
                    "byte_size": len(data),
                }
            )

        markdown = rewrite_markdown_image_refs(result.reconciled_markdown, replacements)
        markdown_key = f"{prefix}/output.md"
        assets_key = f"{prefix}/assets.json"
        decision_key = f"{prefix}/decision.json"
        self.store.write_text(markdown_key, markdown)
        self.store.write_json(
            assets_key,
            {"document_id": result.document_id, "page": result.page, "assets": assets},
        )
        self.store.write_json(decision_key, result.decision_payload())
        published = PublishedPage(
            document_id=result.document_id,
            page=result.page,
            status=PUBLISHED,
            markdown_key=markdown_key,
            assets_key=assets_key,
            decision_key=decision_key,
            markdown_sha256=sha256_text(markdown),
            asset_count=len(assets),
        )
        self.catalog.upsert_page(
            published,
            markdown_text=markdown,
            needs_human_review=result.needs_human_review,
            warning_count=result.warning_count,
        )
        return published
```

Add the rewrite helper:

```python
def rewrite_markdown_image_refs(markdown: str, replacements: dict[str, str]) -> str:
    def rewrite_html(match: re.Match[str]) -> str:
        path = match.group("path")
        quote = match.group("quote")
        replacement = replacements.get(path, path)
        return f"{match.group(1)}{quote}{replacement}{quote}"

    def rewrite_markdown(match: re.Match[str]) -> str:
        path = match.group("path")
        replacement = replacements.get(path, path)
        return f"{match.group(1)}{replacement}{match.group(3)}"

    markdown = _HTML_IMAGE_SRC_RE.sub(rewrite_html, markdown)
    return _MARKDOWN_IMAGE_RE.sub(rewrite_markdown, markdown)
```

Add `PageCatalog.upsert_page()`:

```python
    def upsert_page(
        self,
        published: PublishedPage,
        *,
        markdown_text: str | None,
        needs_human_review: bool,
        warning_count: int,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO pages (
                  document_id, page, status, markdown_key, assets_key, decision_key,
                  needs_human_review, warning_count, asset_count, markdown_sha256,
                  markdown_text, error_message, published_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    1 if needs_human_review else 0,
                    warning_count,
                    published.asset_count,
                    published.markdown_sha256,
                    markdown_text,
                    published.error_message,
                    utc_now_iso(),
                ),
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_reconciled_store.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_extract/reconciled_store.py tests/test_reconciled_store.py
git commit -m "Publish reconciled page artifacts"
```

## Task 3: Catalog Queries, Idempotency, And Assembly

**Files:**
- Modify: `tests/test_reconciled_store.py`
- Modify: `pdf_extract/reconciled_store.py`

- [ ] **Step 1: Add failing catalog and assembly tests**

Append to `tests/test_reconciled_store.py`:

```python
def test_republishing_page_updates_one_catalog_row(tmp_path):
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )

    publisher.publish(make_result("first"), asset_base_dir=tmp_path)
    publisher.publish(make_result("second"), asset_base_dir=tmp_path)

    rows = publisher.catalog.list_pages("Full_30015375000000")
    assert len(rows) == 1
    assert rows[0]["markdown_text"] == "second"


def test_assemble_document_joins_published_pages_and_reports_missing(tmp_path):
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )
    publisher.publish(make_result("page two", page=2), asset_base_dir=tmp_path)
    publisher.publish(make_result("page one", page=1), asset_base_dir=tmp_path)

    result = assemble_document(
        document_id="Full_30015375000000",
        store=publisher.store,
        catalog=publisher.catalog,
        expected_pages=[1, 2, 3],
    )

    combined = publisher.store.read_text(result["combined_markdown_key"])
    manifest = json.loads(publisher.store.read_text(result["manifest_key"]))
    assert combined == "# Page 1\n\npage one\n\n# Page 2\n\npage two\n"
    assert manifest["included_pages"] == [1, 2]
    assert manifest["missing_pages"] == [3]
```

Update the import line in `tests/test_reconciled_store.py` to include:

```python
from pdf_extract.reconciled_store import assemble_document
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_reconciled_store.py -q
```

Expected: FAIL with missing `list_pages` and `assemble_document`.

- [ ] **Step 3: Implement catalog query and assembler**

Add to `PageCatalog` in `pdf_extract/reconciled_store.py`:

```python
    def list_pages(self, document_id: str, *, status: str | None = None) -> list[sqlite3.Row]:
        sql = "SELECT * FROM pages WHERE document_id = ?"
        params: list[Any] = [document_id]
        if status is not None:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY page"
        with self.connect() as conn:
            return conn.execute(sql, params).fetchall()
```

Add module-level `assemble_document()`:

```python
def assemble_document(
    *,
    document_id: str,
    store: LocalObjectStore,
    catalog: PageCatalog,
    expected_pages: list[int] | None = None,
) -> dict[str, Any]:
    rows = catalog.list_pages(document_id, status=PUBLISHED)
    included_pages = [int(row["page"]) for row in rows]
    expected = expected_pages if expected_pages is not None else included_pages
    missing_pages = [page for page in expected if page not in set(included_pages)]

    parts: list[str] = []
    page_hashes: list[dict[str, Any]] = []
    for row in rows:
        page = int(row["page"])
        markdown = store.read_text(row["markdown_key"])
        parts.append(f"# Page {page}\n\n{markdown.strip()}\n")
        page_hashes.append(
            {
                "page": page,
                "markdown_key": row["markdown_key"],
                "markdown_sha256": row["markdown_sha256"],
            }
        )

    combined = "\n".join(parts)
    combined_key = f"pdf-extract/reconciled/{document_id}/combined/combined.md"
    manifest_key = f"pdf-extract/reconciled/{document_id}/combined/manifest.json"
    store.write_text(combined_key, combined)
    manifest = {
        "document_id": document_id,
        "included_pages": included_pages,
        "missing_pages": missing_pages,
        "page_count": len(included_pages),
        "combined_markdown_key": combined_key,
        "combined_sha256": sha256_text(combined),
        "pages": page_hashes,
        "generated_at": utc_now_iso(),
    }
    store.write_json(manifest_key, manifest)
    return {
        "combined_markdown_key": combined_key,
        "manifest_key": manifest_key,
        "included_pages": included_pages,
        "missing_pages": missing_pages,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_reconciled_store.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_extract/reconciled_store.py tests/test_reconciled_store.py
git commit -m "Assemble published reconciled pages"
```

## Task 4: Three-Page Prototype Publisher

**Files:**
- Create: `tests/test_reconciled_prototype.py`
- Create: `pdf_extract/reconciled_prototype.py`
- Create: `scripts/run_reconciled_store_prototype.py`

- [ ] **Step 1: Add failing prototype test**

Create `tests/test_reconciled_prototype.py`:

```python
import json
import sqlite3

from pdf_extract.reconciled_prototype import run_three_page_prototype


def write_page(run_root, mode, page, markdown, image_name=None):
    page_dir = run_root / mode / "pages" / f"page_{page:04d}"
    page_dir.mkdir(parents=True, exist_ok=True)
    (page_dir / "output.md").write_text(markdown, encoding="utf-8")
    (page_dir / "page.png").write_bytes(b"png")
    if image_name:
        (page_dir / "imgs").mkdir()
        (page_dir / "imgs" / image_name).write_bytes(b"jpeg")


def test_three_page_prototype_publishes_assembles_and_writes_viewer(tmp_path):
    run_root = tmp_path / "runs" / "Full_30015375000000"
    for page in [1, 2, 40]:
        write_page(run_root, "union", page, f"union page {page}")
        write_page(run_root, "small", page, f"small page {page}")
    write_page(
        run_root,
        "union",
        40,
        '<img src="imgs/seal.jpg" alt="Seal" />',
        image_name="seal.jpg",
    )

    result = run_three_page_prototype(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=tmp_path / "viewer",
        pages=[1, 2, 40],
    )

    assert result["document_id"] == "Full_30015375000000"
    assert result["published_pages"] == [1, 2, 40]
    assert (tmp_path / "viewer" / "index.html").is_file()
    with sqlite3.connect(tmp_path / "catalog.sqlite") as conn:
        rows = conn.execute("SELECT page, status, asset_count FROM pages ORDER BY page").fetchall()
    assert rows == [(1, "published", 0), (2, "published", 0), (40, "published", 1)]
    manifest = json.loads(
        (tmp_path / "object_store" / result["assembly"]["manifest_key"]).read_text(
            encoding="utf-8"
        )
    )
    assert manifest["included_pages"] == [1, 2, 40]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_reconciled_prototype.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pdf_extract.reconciled_prototype'`.

- [ ] **Step 3: Implement prototype generator**

Create `pdf_extract/reconciled_prototype.py`:

```python
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .reconciled_store import (
    LocalObjectStore,
    PageCatalog,
    PageReconciliationResult,
    ReconciledPagePublisher,
    assemble_document,
)
from .render import page_dir_name


def build_prototype_result(run_root: Path, page: int) -> PageReconciliationResult:
    page_label = page_dir_name(page)
    union_page_dir = run_root / "union" / "pages" / page_label
    small_page_dir = run_root / "small" / "pages" / page_label
    union_markdown_path = union_page_dir / "output.md"
    small_markdown_path = small_page_dir / "output.md"
    union_markdown = union_markdown_path.read_text(encoding="utf-8")
    small_markdown = small_markdown_path.read_text(encoding="utf-8")
    if "imgs/" in union_markdown:
        markdown = union_markdown
        winner = "union"
        asset_base_dir = union_page_dir
    else:
        markdown = union_markdown if union_markdown.strip() else small_markdown
        winner = "union" if union_markdown.strip() else "small"
        asset_base_dir = union_page_dir if union_markdown.strip() else small_page_dir
    return PageReconciliationResult(
        document_id=run_root.name,
        page=page,
        reconciled_markdown=markdown,
        winner=winner,
        warnings=[],
        needs_human_review=False,
        model="prototype-no-llm",
        prompt_version="prototype-page-v1",
        source_refs={
            "page_image": (union_page_dir / "page.png").as_posix(),
            "union_markdown": union_markdown_path.as_posix(),
            "small_markdown": small_markdown_path.as_posix(),
            "asset_base_dir": asset_base_dir.as_posix(),
        },
    )


def write_static_viewer(
    *,
    catalog: PageCatalog,
    store: LocalObjectStore,
    document_id: str,
    viewer_dir: Path,
) -> Path:
    rows = catalog.list_pages(document_id)
    viewer_dir.mkdir(parents=True, exist_ok=True)
    page_items: list[str] = []
    page_sections: list[str] = []
    for row in rows:
        page = int(row["page"])
        markdown = row["markdown_text"] or ""
        assets = {"assets": []}
        if row["assets_key"]:
            assets = json.loads(store.read_text(row["assets_key"]))
        page_items.append(
            f'<li><a href="#page-{page}">Page {page}</a> '
            f'<span>{html.escape(row["status"])}</span></li>'
        )
        asset_items = "".join(
            f'<li><code>{html.escape(asset["asset_uri"])}</code><br>'
            f'{html.escape(asset["description"])}</li>'
            for asset in assets["assets"]
        )
        page_sections.append(
            f'<section id="page-{page}">'
            f'<h2>Page {page}</h2>'
            f'<p>Status: {html.escape(row["status"])} | '
            f'Warnings: {row["warning_count"]} | Assets: {row["asset_count"]}</p>'
            f'<pre>{html.escape(markdown)}</pre>'
            f'<h3>Assets</h3><ul>{asset_items}</ul>'
            f'<p><code>{html.escape(row["decision_key"] or "")}</code></p>'
            f'</section>'
        )
    html_text = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Reconciled Page Viewer</title>"
        "<style>body{font-family:sans-serif;margin:2rem;}"
        "pre{white-space:pre-wrap;border:1px solid #ddd;padding:1rem;}"
        "section{border-top:1px solid #ccc;margin-top:2rem;padding-top:1rem;}"
        "</style></head><body>"
        f"<h1>{html.escape(document_id)}</h1>"
        f"<ul>{''.join(page_items)}</ul>"
        f"{''.join(page_sections)}"
        "</body></html>"
    )
    index_path = viewer_dir / "index.html"
    index_path.write_text(html_text, encoding="utf-8")
    return index_path


def run_three_page_prototype(
    *,
    run_root: Path,
    object_store_root: Path,
    sqlite_path: Path,
    viewer_dir: Path,
    pages: list[int] | None = None,
) -> dict[str, Any]:
    selected_pages = pages or [1, 2, 40]
    store = LocalObjectStore(object_store_root)
    catalog = PageCatalog(sqlite_path)
    publisher = ReconciledPagePublisher(store=store, catalog=catalog)
    published_pages: list[int] = []
    for page in selected_pages:
        result = build_prototype_result(run_root, page)
        asset_base_dir = Path(result.source_refs["asset_base_dir"])
        published = publisher.publish(result, asset_base_dir=asset_base_dir)
        if published.status == "published":
            published_pages.append(page)
    assembly = assemble_document(
        document_id=run_root.name,
        store=store,
        catalog=catalog,
        expected_pages=selected_pages,
    )
    viewer_path = write_static_viewer(
        catalog=catalog,
        store=store,
        document_id=run_root.name,
        viewer_dir=viewer_dir,
    )
    return {
        "document_id": run_root.name,
        "published_pages": published_pages,
        "assembly": assembly,
        "viewer_path": viewer_path.as_posix(),
    }
```

Create `scripts/run_reconciled_store_prototype.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pdf_extract.reconciled_prototype import run_three_page_prototype


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a three-page reconciled store prototype.")
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path("runs/Full_30015375000000"),
        help="Document run root containing union/ and small/ directories.",
    )
    parser.add_argument(
        "--object-store-root",
        type=Path,
        default=Path("object_store"),
        help="Local fake-S3 root.",
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=Path("reconciled_catalog.sqlite"),
        help="SQLite catalog path.",
    )
    parser.add_argument(
        "--viewer-dir",
        type=Path,
        default=Path("runs/Full_30015375000000/reconciled_viewer"),
        help="Directory for static viewer files.",
    )
    parser.add_argument(
        "--pages",
        default="1,2,40",
        help="Comma-separated page numbers to publish.",
    )
    args = parser.parse_args()
    pages = [int(part) for part in args.pages.split(",") if part.strip()]
    result = run_three_page_prototype(
        run_root=args.run_root,
        object_store_root=args.object_store_root,
        sqlite_path=args.sqlite_path,
        viewer_dir=args.viewer_dir,
        pages=pages,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run prototype tests to verify they pass**

Run:

```bash
uv run pytest tests/test_reconciled_prototype.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_extract/reconciled_prototype.py scripts/run_reconciled_store_prototype.py tests/test_reconciled_prototype.py
git commit -m "Add three-page reconciled store prototype"
```

## Task 5: README And Real Run Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add README instructions**

Append to `README.md`:

````markdown
## Reconciled Asset Store Prototype

The reconciled asset store prototype publishes three page-level reconciled
Markdown artifacts into a local fake-S3 directory and a SQLite catalog. It does
not call an LLM. It fakes the reconciliation pipeline output from existing
`union` and `small` page Markdown so the storage contract can be tested first.

```bash
uv run python scripts/run_reconciled_store_prototype.py \
  --run-root runs/Full_30015375000000 \
  --object-store-root object_store \
  --sqlite-path reconciled_catalog.sqlite \
  --viewer-dir runs/Full_30015375000000/reconciled_viewer \
  --pages 1,2,40
```

Open the generated viewer:

```text
runs/Full_30015375000000/reconciled_viewer/index.html
```

The prototype writes page artifacts under:

```text
object_store/pdf-extract/reconciled/Full_30015375000000/
```

SQLite stores one thin `pages` row per published page. Rich page details remain
in `decision.json`, `assets.json`, and `output.md`.
````

- [ ] **Step 2: Run focused tests**

Run:

```bash
uv run pytest tests/test_reconciled_store.py tests/test_reconciled_prototype.py -q
```

Expected: PASS.

- [ ] **Step 3: Run the prototype against the checked-in run**

Run:

```bash
uv run python scripts/run_reconciled_store_prototype.py \
  --run-root runs/Full_30015375000000 \
  --object-store-root object_store \
  --sqlite-path reconciled_catalog.sqlite \
  --viewer-dir runs/Full_30015375000000/reconciled_viewer \
  --pages 1,2,40
```

Expected output includes:

```json
{
  "document_id": "Full_30015375000000",
  "published_pages": [1, 2, 40]
}
```

- [ ] **Step 4: Inspect generated artifacts**

Run:

```bash
find object_store/pdf-extract/reconciled/Full_30015375000000 -maxdepth 4 -type f | sort
sqlite3 reconciled_catalog.sqlite "SELECT page, status, asset_count FROM pages ORDER BY page;"
```

Expected:

```text
1|published|0
2|published|0
40|published|3
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "Document reconciled store prototype"
```

## Task 6: Full Regression Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run full test suite**

Run:

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 2: Check git status**

Run:

```bash
git status --short
```

Expected: only intentional generated prototype artifacts may remain untracked:

```text
?? object_store/
?? reconciled_catalog.sqlite
?? runs/Full_30015375000000/reconciled_viewer/
```

Do not stage generated prototype artifacts unless the user explicitly wants
sample outputs committed.

- [ ] **Step 3: Report viewer path**

Report this file to the user:

```text
runs/Full_30015375000000/reconciled_viewer/index.html
```

If the Browser plugin is available during execution, open the local HTML viewer
and verify it shows pages 1, 2, and 40 with page 40 assets listed.
