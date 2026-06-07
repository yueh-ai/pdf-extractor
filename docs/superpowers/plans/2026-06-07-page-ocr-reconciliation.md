# Page OCR Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a restartable page-level OCR reconciler that uses a vision-capable model to produce reconciled per-page Markdown and publish it through the existing page artifact contract.

**Architecture:** Add a focused `pdf_extract/reconciler.py` module for page input discovery, prompt construction, model response validation, and document-level orchestration. Keep the existing `ReconciledPagePublisher`, fake-S3 store, SQLite catalog, assembler, and viewer manifest writer as the storage and review boundary. Add a thin CLI wrapper in `scripts/run_reconcile.py` with all-pages default, resume-by-skipping published pages, and `--force` reruns.

**Tech Stack:** Python 3.10 stdlib (`argparse`, `base64`, `dataclasses`, `json`, `mimetypes`, `os`, `pathlib`, `typing`), OpenAI Responses API via the `openai` Python SDK, existing `pdf_extract` modules, pytest, injected fake model clients for tests.

---

## File Structure

- Create `pdf_extract/reconciler.py`
  - `PageReconcileInputs`: page-level input bundle.
  - `ModelReconcileResponse`: validated model response.
  - `VisionModelClient`: protocol for real or fake model clients.
  - `discover_reconcile_pages()`: find pages available in both `union` and `small`.
  - `load_page_inputs()`: load image path and Markdown drafts.
  - `build_reconcile_prompt()`: prompt text isolated for later iteration.
  - `VisionReconciler`: call client, validate response, return `PageReconciliationResult`.
  - `OpenAIResponsesVisionClient`: real vision-model client using Responses image input and structured JSON output.
  - `run_reconciliation()`: document/page loop with resume and force semantics.
- Create `scripts/run_reconcile.py`
  - CLI wrapper around `run_reconciliation()`.
  - Supports `--provider openai` for real runs and `--provider dry-run` for local pipeline smoke tests.
- Create `tests/test_reconciler.py`
  - Unit and integration tests using synthetic page directories and fake clients.
- Modify `pyproject.toml`
  - Add the `openai` Python SDK dependency.
- Modify `uv.lock`
  - Refresh after adding the `openai` dependency.
- Modify `README.md`
  - Add a short page OCR reconciliation section with example commands.

## Task 1: Page Input Discovery

**Files:**
- Create: `tests/test_reconciler.py`
- Create: `pdf_extract/reconciler.py`

- [ ] **Step 1: Write failing tests for page discovery and loading**

Add this to `tests/test_reconciler.py`:

```python
from pathlib import Path

import pytest

from pdf_extract.reconciler import (
    PageReconcileInputs,
    discover_reconcile_pages,
    load_page_inputs,
)


def write_page(run_root: Path, mode: str, page: int, markdown: str, *, image: bool = True) -> Path:
    page_dir = run_root / mode / "pages" / f"page_{page:04d}"
    page_dir.mkdir(parents=True, exist_ok=True)
    (page_dir / "output.md").write_text(markdown, encoding="utf-8")
    if image:
        (page_dir / "page.png").write_bytes(b"png")
    return page_dir


def test_discover_reconcile_pages_returns_pages_present_in_both_modes(tmp_path):
    run_root = tmp_path / "runs" / "Full_30015375000000"
    write_page(run_root, "union", 1, "union one")
    write_page(run_root, "small", 1, "small one")
    write_page(run_root, "union", 2, "union two")
    write_page(run_root, "small", 3, "small three")

    assert discover_reconcile_pages(run_root) == [1]


def test_load_page_inputs_prefers_union_page_image(tmp_path):
    run_root = tmp_path / "runs" / "Full_30015375000000"
    union_page = write_page(run_root, "union", 2, "union markdown")
    small_page = write_page(run_root, "small", 2, "small markdown")

    inputs = load_page_inputs(run_root, 2)

    assert isinstance(inputs, PageReconcileInputs)
    assert inputs.document_id == "Full_30015375000000"
    assert inputs.page == 2
    assert inputs.page_image_path == union_page / "page.png"
    assert inputs.union_markdown_path == union_page / "output.md"
    assert inputs.small_markdown_path == small_page / "output.md"
    assert inputs.union_markdown == "union markdown"
    assert inputs.small_markdown == "small markdown"


def test_load_page_inputs_falls_back_to_small_page_image(tmp_path):
    run_root = tmp_path / "runs" / "Full_30015375000000"
    write_page(run_root, "union", 4, "union markdown", image=False)
    small_page = write_page(run_root, "small", 4, "small markdown")

    inputs = load_page_inputs(run_root, 4)

    assert inputs.page_image_path == small_page / "page.png"


def test_load_page_inputs_requires_markdown_and_page_image(tmp_path):
    run_root = tmp_path / "runs" / "Full_30015375000000"
    write_page(run_root, "union", 5, "union markdown", image=False)
    write_page(run_root, "small", 5, "small markdown", image=False)

    with pytest.raises(FileNotFoundError, match="page image"):
        load_page_inputs(run_root, 5)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_reconciler.py -q
```

Expected: FAIL with `ModuleNotFoundError` or import errors for `pdf_extract.reconciler`.

- [ ] **Step 3: Implement page discovery and loading**

Create `pdf_extract/reconciler.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .render import page_dir_name


@dataclass(frozen=True)
class PageReconcileInputs:
    document_id: str
    page: int
    page_image_path: Path
    union_markdown_path: Path
    small_markdown_path: Path
    union_markdown: str
    small_markdown: str


def _page_number_from_dir(path: Path) -> int | None:
    name = path.name
    if not name.startswith("page_"):
        return None
    suffix = name.removeprefix("page_")
    if not suffix.isdigit():
        return None
    return int(suffix)


def discover_reconcile_pages(run_root: Path) -> list[int]:
    union_pages_dir = run_root / "union" / "pages"
    small_pages_dir = run_root / "small" / "pages"
    if not union_pages_dir.is_dir() or not small_pages_dir.is_dir():
        return []

    union_pages = {
        page
        for page in (_page_number_from_dir(path) for path in union_pages_dir.iterdir())
        if page is not None
    }
    small_pages = {
        page
        for page in (_page_number_from_dir(path) for path in small_pages_dir.iterdir())
        if page is not None
    }
    return sorted(union_pages & small_pages)


def _require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"Missing {label}: {path}")
    return path


def load_page_inputs(run_root: Path, page: int) -> PageReconcileInputs:
    page_label = page_dir_name(page)
    union_page_dir = run_root / "union" / "pages" / page_label
    small_page_dir = run_root / "small" / "pages" / page_label
    union_markdown_path = _require_file(union_page_dir / "output.md", "union markdown")
    small_markdown_path = _require_file(small_page_dir / "output.md", "small markdown")

    union_image = union_page_dir / "page.png"
    small_image = small_page_dir / "page.png"
    if union_image.is_file():
        page_image_path = union_image
    elif small_image.is_file():
        page_image_path = small_image
    else:
        raise FileNotFoundError(f"Missing page image: {union_image} or {small_image}")

    return PageReconcileInputs(
        document_id=run_root.name,
        page=page,
        page_image_path=page_image_path,
        union_markdown_path=union_markdown_path,
        small_markdown_path=small_markdown_path,
        union_markdown=union_markdown_path.read_text(encoding="utf-8"),
        small_markdown=small_markdown_path.read_text(encoding="utf-8"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_reconciler.py -q
```

Expected: PASS for the discovery/loading tests.

- [ ] **Step 5: Commit**

```bash
git add pdf_extract/reconciler.py tests/test_reconciler.py
git commit -m "Add reconcile page input discovery"
```

## Task 2: Prompt Builder And Model Response Validation

**Files:**
- Modify: `tests/test_reconciler.py`
- Modify: `pdf_extract/reconciler.py`

- [ ] **Step 1: Write failing tests for prompt and response validation**

Append to `tests/test_reconciler.py`:

```python
from pdf_extract.reconciler import (
    DEFAULT_RECONCILE_PROMPT_VERSION,
    ModelReconcileResponse,
    VisionReconciler,
    build_reconcile_prompt,
)


class FakeVisionClient:
    model = "fake-vision-model"

    def __init__(self, response: dict):
        self.response = response
        self.calls = []

    def reconcile(self, *, image_path: Path, prompt: str) -> dict:
        self.calls.append({"image_path": image_path, "prompt": prompt})
        return self.response


def test_build_reconcile_prompt_treats_image_as_authority(tmp_path):
    run_root = tmp_path / "runs" / "Full_30015375000000"
    write_page(run_root, "union", 1, "union draft")
    write_page(run_root, "small", 1, "small draft")
    inputs = load_page_inputs(run_root, 1)

    prompt = build_reconcile_prompt(inputs)

    assert "rendered page image is authoritative" in prompt
    assert "Do not use PaddleOCR res.json" in prompt
    assert "union/output.md" in prompt
    assert "small/output.md" in prompt
    assert "union draft" in prompt
    assert "small draft" in prompt


def test_model_response_validation_accepts_contract_fields():
    response = ModelReconcileResponse.from_payload(
        {
            "reconciled_markdown": "# Clean page",
            "winner": "mixed",
            "warnings": ["checked table visually"],
            "needs_human_review": True,
        }
    )

    assert response.reconciled_markdown == "# Clean page"
    assert response.winner == "mixed"
    assert response.warnings == ("checked table visually",)
    assert response.needs_human_review is True


def test_model_response_validation_rejects_invalid_winner():
    with pytest.raises(ValueError, match="Unsupported winner"):
        ModelReconcileResponse.from_payload(
            {
                "reconciled_markdown": "# Clean page",
                "winner": "bad",
                "warnings": [],
                "needs_human_review": False,
            }
        )


def test_vision_reconciler_returns_page_reconciliation_result(tmp_path):
    run_root = tmp_path / "runs" / "Full_30015375000000"
    write_page(run_root, "union", 7, "union draft")
    write_page(run_root, "small", 7, "small draft")
    inputs = load_page_inputs(run_root, 7)
    client = FakeVisionClient(
        {
            "reconciled_markdown": "# Reconciled",
            "winner": "mixed",
            "warnings": [],
            "needs_human_review": False,
        }
    )

    result = VisionReconciler(client).reconcile_page(inputs)

    assert result.document_id == "Full_30015375000000"
    assert result.page == 7
    assert result.reconciled_markdown == "# Reconciled"
    assert result.winner == "mixed"
    assert result.model == "fake-vision-model"
    assert result.prompt_version == DEFAULT_RECONCILE_PROMPT_VERSION
    assert result.source_refs == {
        "page_image": inputs.page_image_path.as_posix(),
        "union_markdown": inputs.union_markdown_path.as_posix(),
        "small_markdown": inputs.small_markdown_path.as_posix(),
    }
    assert client.calls[0]["image_path"] == inputs.page_image_path
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_reconciler.py -q
```

Expected: FAIL with missing `ModelReconcileResponse`, `VisionReconciler`, or `build_reconcile_prompt`.

- [ ] **Step 3: Implement prompt builder and response validation**

Add to `pdf_extract/reconciler.py`:

```python
from typing import Any, Protocol, Sequence

from .reconciled_store import PageReconciliationResult


DEFAULT_RECONCILE_PROMPT_VERSION = "reconcile-page-v1"
VALID_WINNERS = {"union", "small", "mixed", "uncertain"}


class VisionModelClient(Protocol):
    model: str

    def reconcile(self, *, image_path: Path, prompt: str) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ModelReconcileResponse:
    reconciled_markdown: str
    winner: str
    warnings: tuple[str, ...]
    needs_human_review: bool

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ModelReconcileResponse":
        markdown = payload.get("reconciled_markdown")
        if not isinstance(markdown, str) or markdown == "":
            raise ValueError("reconciled_markdown must be a non-empty string")

        winner = payload.get("winner")
        if winner not in VALID_WINNERS:
            raise ValueError(f"Unsupported winner: {winner}")

        warnings = payload.get("warnings", [])
        if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
            raise ValueError("warnings must be a list of strings")

        needs_human_review = payload.get("needs_human_review")
        if not isinstance(needs_human_review, bool):
            raise ValueError("needs_human_review must be a boolean")

        return cls(
            reconciled_markdown=markdown,
            winner=winner,
            warnings=tuple(warnings),
            needs_human_review=needs_human_review,
        )


def build_reconcile_prompt(inputs: PageReconcileInputs) -> str:
    return f"""You are reconciling OCR Markdown for one PDF page.

The rendered page image is authoritative. Use the OCR Markdown drafts as hints,
but correct them when the image clearly shows a different value, label, table
structure, checkbox state, heading, symbol, or reading order.

Do not invent content that is not visible in the image or supported by the OCR
drafts. Do not perform section extraction, cross-page deduplication, current
well-state selection, or domain-level interpretation. Do not use PaddleOCR
res.json for this task.

Return a JSON object with exactly these fields:
- reconciled_markdown: string
- winner: one of "union", "small", "mixed", "uncertain"
- warnings: array of short strings
- needs_human_review: boolean

Set needs_human_review to true if the page is unreadable, a table appears
structurally incomplete, important labels cannot be confidently transcribed,
image references cannot be preserved, or winner is "uncertain".

Source draft: union/output.md
```markdown
{inputs.union_markdown}
```

Source draft: small/output.md
```markdown
{inputs.small_markdown}
```
"""


class VisionReconciler:
    def __init__(
        self,
        client: VisionModelClient,
        *,
        prompt_version: str = DEFAULT_RECONCILE_PROMPT_VERSION,
    ):
        self.client = client
        self.prompt_version = prompt_version

    def reconcile_page(self, inputs: PageReconcileInputs) -> PageReconciliationResult:
        payload = self.client.reconcile(
            image_path=inputs.page_image_path,
            prompt=build_reconcile_prompt(inputs),
        )
        response = ModelReconcileResponse.from_payload(payload)
        return PageReconciliationResult(
            document_id=inputs.document_id,
            page=inputs.page,
            reconciled_markdown=response.reconciled_markdown,
            winner=response.winner,
            warnings=response.warnings,
            needs_human_review=response.needs_human_review,
            model=self.client.model,
            prompt_version=self.prompt_version,
            source_refs={
                "page_image": inputs.page_image_path.as_posix(),
                "union_markdown": inputs.union_markdown_path.as_posix(),
                "small_markdown": inputs.small_markdown_path.as_posix(),
            },
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_reconciler.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_extract/reconciler.py tests/test_reconciler.py
git commit -m "Add vision reconcile response contract"
```

## Task 3: Document Reconciliation Runner With Resume And Force

**Files:**
- Modify: `tests/test_reconciler.py`
- Modify: `pdf_extract/reconciler.py`

- [ ] **Step 1: Write failing tests for document runner**

Append to `tests/test_reconciler.py`:

```python
import json

from pdf_extract.reconciled_store import LocalObjectStore, PageCatalog
from pdf_extract.reconciler import run_reconciliation


class CountingVisionClient:
    model = "counting-vision-model"

    def __init__(self):
        self.pages = []

    def reconcile(self, *, image_path: Path, prompt: str) -> dict:
        page_text = image_path.parent.name.removeprefix("page_")
        page = int(page_text)
        self.pages.append(page)
        return {
            "reconciled_markdown": f"# Reconciled page {page}",
            "winner": "mixed",
            "warnings": [],
            "needs_human_review": False,
        }


def test_run_reconciliation_defaults_to_all_discovered_pages(tmp_path):
    run_root = tmp_path / "runs" / "Full_30015375000000"
    for page in [1, 2, 4]:
        write_page(run_root, "union", page, f"union {page}")
        write_page(run_root, "small", page, f"small {page}")
    client = CountingVisionClient()

    result = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=tmp_path / "viewer",
        client=client,
    )

    assert client.pages == [1, 2, 4]
    assert result["selected_pages"] == [1, 2, 4]
    assert result["processed_pages"] == [1, 2, 4]
    assert result["skipped_pages"] == []
    assert result["published_pages"] == [1, 2, 4]
    assert (tmp_path / "viewer" / "viewer-manifest.json").is_file()


def test_run_reconciliation_honors_pages_filter(tmp_path):
    run_root = tmp_path / "runs" / "Full_30015375000000"
    for page in [1, 2, 3]:
        write_page(run_root, "union", page, f"union {page}")
        write_page(run_root, "small", page, f"small {page}")
    client = CountingVisionClient()

    result = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=tmp_path / "viewer",
        client=client,
        pages=[2, 3],
    )

    assert client.pages == [2, 3]
    assert result["selected_pages"] == [2, 3]


def test_run_reconciliation_skips_published_pages_unless_forced(tmp_path):
    run_root = tmp_path / "runs" / "Full_30015375000000"
    for page in [1, 2]:
        write_page(run_root, "union", page, f"union {page}")
        write_page(run_root, "small", page, f"small {page}")

    first_client = CountingVisionClient()
    run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=tmp_path / "viewer",
        client=first_client,
    )
    second_client = CountingVisionClient()
    second_result = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=tmp_path / "viewer",
        client=second_client,
    )

    assert second_client.pages == []
    assert second_result["skipped_pages"] == [1, 2]

    forced_client = CountingVisionClient()
    forced_result = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=tmp_path / "viewer",
        client=forced_client,
        pages=[2],
        force=True,
    )

    assert forced_client.pages == [2]
    assert forced_result["processed_pages"] == [2]
    assert forced_result["skipped_pages"] == []


def test_run_reconciliation_writes_only_markdown_source_refs(tmp_path):
    run_root = tmp_path / "runs" / "Full_30015375000000"
    write_page(run_root, "union", 1, "union 1")
    write_page(run_root, "small", 1, "small 1")

    result = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=tmp_path / "viewer",
        client=CountingVisionClient(),
    )

    decision_key = "pdf-extract/reconciled/Full_30015375000000/pages/page_0001/decision.json"
    decision = json.loads((tmp_path / "object_store" / decision_key).read_text(encoding="utf-8"))
    assert decision["source_refs"].keys() == {"page_image", "union_markdown", "small_markdown"}
    assert "res.json" not in json.dumps(decision)
    assert result["assembly"]["included_pages"] == [1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_reconciler.py -q
```

Expected: FAIL with missing `run_reconciliation`.

- [ ] **Step 3: Implement document runner**

Add imports to `pdf_extract/reconciler.py`:

```python
from typing import Iterable

from .reconciled_store import (
    PUBLISHED,
    LocalObjectStore,
    PageCatalog,
    ReconciledPagePublisher,
    assemble_document,
)
from .reconciled_viewer import write_viewer_manifest
```

Add:

```python
def _published_page_set(catalog: PageCatalog, document_id: str) -> set[int]:
    return {
        int(row["page"])
        for row in catalog.list_pages(document_id, status=PUBLISHED)
    }


def _selected_pages(run_root: Path, pages: Iterable[int] | None) -> list[int]:
    available_pages = discover_reconcile_pages(run_root)
    if pages is None:
        return available_pages
    available_set = set(available_pages)
    selected = sorted(set(int(page) for page in pages))
    missing = [page for page in selected if page not in available_set]
    if missing:
        raise ValueError(f"Selected pages are not available in both modes: {missing}")
    return selected


def run_reconciliation(
    *,
    run_root: Path,
    object_store_root: Path,
    sqlite_path: Path,
    viewer_dir: Path | None,
    client: VisionModelClient,
    pages: Iterable[int] | None = None,
    force: bool = False,
    assemble: bool = True,
) -> dict[str, Any]:
    selected_pages = _selected_pages(run_root, pages)
    store = LocalObjectStore(object_store_root)
    catalog = PageCatalog(sqlite_path)
    publisher = ReconciledPagePublisher(store=store, catalog=catalog)
    reconciler = VisionReconciler(client)

    published_before = _published_page_set(catalog, run_root.name)
    processed_pages: list[int] = []
    skipped_pages: list[int] = []
    published_pages: list[int] = []
    failed_pages: list[int] = []

    for page in selected_pages:
        if not force and page in published_before:
            skipped_pages.append(page)
            continue

        inputs = load_page_inputs(run_root, page)
        result = reconciler.reconcile_page(inputs)
        asset_base_dir = inputs.union_markdown_path.parent
        published = publisher.publish(result, asset_base_dir=asset_base_dir)
        processed_pages.append(page)
        if published.status == PUBLISHED:
            published_pages.append(page)
        else:
            failed_pages.append(page)

    assembly: dict[str, Any] | None = None
    if assemble:
        assembly = assemble_document(
            document_id=run_root.name,
            store=store,
            catalog=catalog,
            expected_pages=selected_pages,
        )

    viewer_manifest_path: str | None = None
    if viewer_dir is not None:
        repo_root = run_root.resolve().parent.parent
        viewer_manifest_path = write_viewer_manifest(
            catalog=catalog,
            store=store,
            document_id=run_root.name,
            viewer_dir=viewer_dir,
            repo_root=repo_root,
        ).as_posix()

    return {
        "document_id": run_root.name,
        "selected_pages": selected_pages,
        "processed_pages": processed_pages,
        "skipped_pages": skipped_pages,
        "published_pages": published_pages,
        "failed_pages": failed_pages,
        "assembly": assembly,
        "viewer_manifest_path": viewer_manifest_path,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_reconciler.py tests/test_reconciled_store.py tests/test_reconciled_viewer.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_extract/reconciler.py tests/test_reconciler.py
git commit -m "Add restartable reconcile runner"
```

## Task 4: OpenAI Responses Vision Client

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `tests/test_reconciler.py`
- Modify: `pdf_extract/reconciler.py`

- [ ] **Step 1: Write failing tests for the real client wrapper**

Append to `tests/test_reconciler.py`:

```python
from types import SimpleNamespace

from pdf_extract.reconciler import OpenAIResponsesVisionClient


class FakeResponsesResource:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text=json.dumps(
                {
                    "reconciled_markdown": "# From OpenAI",
                    "winner": "mixed",
                    "warnings": [],
                    "needs_human_review": False,
                }
            )
        )


class FakeOpenAISdkClient:
    def __init__(self):
        self.responses = FakeResponsesResource()


def test_openai_responses_client_sends_image_and_structured_format(tmp_path, monkeypatch):
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png-bytes")
    fake_sdk = FakeOpenAISdkClient()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = OpenAIResponsesVisionClient(model="gpt-test-vision", sdk_client=fake_sdk)

    payload = client.reconcile(image_path=image_path, prompt="reconcile this page")

    assert payload["reconciled_markdown"] == "# From OpenAI"
    call = fake_sdk.responses.calls[0]
    assert call["model"] == "gpt-test-vision"
    assert call["input"][0]["role"] == "user"
    content = call["input"][0]["content"]
    assert content[0] == {"type": "input_text", "text": "reconcile this page"}
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/png;base64,")
    assert content[1]["detail"] == "high"
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["name"] == "page_reconciliation_result"


def test_openai_responses_client_requires_api_key_without_injected_client(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIResponsesVisionClient(model="gpt-test-vision")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_reconciler.py::test_openai_responses_client_sends_image_and_structured_format tests/test_reconciler.py::test_openai_responses_client_requires_api_key_without_injected_client -q
```

Expected: FAIL with missing `OpenAIResponsesVisionClient`.

- [ ] **Step 3: Add OpenAI SDK dependency**

Modify `pyproject.toml`:

```toml
dependencies = [
  "numpy",
  "openai",
  "pypdfium2",
  "pillow",
  "tqdm",
]
```

- [ ] **Step 4: Refresh the lockfile**

Run:

```bash
uv lock
```

Expected: command exits `0` and updates `uv.lock` if dependency resolution changes.

- [ ] **Step 5: Implement OpenAI Responses client wrapper**

Add imports to `pdf_extract/reconciler.py`:

```python
import base64
import json
import mimetypes
import os
```

Add:

```python
RECONCILE_RESPONSE_FORMAT: dict[str, Any] = {
    "type": "json_schema",
    "name": "page_reconciliation_result",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "reconciled_markdown",
            "winner",
            "warnings",
            "needs_human_review",
        ],
        "properties": {
            "reconciled_markdown": {"type": "string"},
            "winner": {"type": "string", "enum": ["union", "small", "mixed", "uncertain"]},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "needs_human_review": {"type": "boolean"},
        },
    },
}


def image_data_url(image_path: Path) -> str:
    content_type = mimetypes.guess_type(image_path.as_posix())[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


class OpenAIResponsesVisionClient:
    def __init__(
        self,
        *,
        model: str,
        api_key_env: str = "OPENAI_API_KEY",
        sdk_client: Any | None = None,
    ):
        self.model = model
        if sdk_client is not None:
            self._client = sdk_client
            return

        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"{api_key_env} is required for OpenAI reconciliation")

        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)

    def reconcile(self, *, image_path: Path, prompt: str) -> dict[str, Any]:
        response = self._client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": image_data_url(image_path),
                            "detail": "high",
                        },
                    ],
                }
            ],
            text={"format": RECONCILE_RESPONSE_FORMAT},
        )
        return json.loads(response.output_text)
```

- [ ] **Step 6: Run client tests**

Run:

```bash
uv run pytest tests/test_reconciler.py::test_openai_responses_client_sends_image_and_structured_format tests/test_reconciler.py::test_openai_responses_client_requires_api_key_without_injected_client -q
```

Expected: PASS.

- [ ] **Step 7: Run reconciliation tests**

Run:

```bash
uv run pytest tests/test_reconciler.py tests/test_reconciled_store.py tests/test_reconciled_viewer.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml uv.lock pdf_extract/reconciler.py tests/test_reconciler.py
git commit -m "Add OpenAI vision reconcile client"
```

## Task 5: CLI Wrapper

**Files:**
- Modify: `tests/test_reconciler.py`
- Create: `scripts/run_reconcile.py`

- [ ] **Step 1: Write failing CLI parser tests**

Append to `tests/test_reconciler.py`:

```python
from scripts.run_reconcile import create_client, parse_pages_arg


def test_parse_pages_arg_accepts_comma_list():
    assert parse_pages_arg("1,2,40") == [1, 2, 40]


def test_parse_pages_arg_accepts_blank_as_all_pages():
    assert parse_pages_arg(None) is None
    assert parse_pages_arg("") is None


def test_parse_pages_arg_rejects_invalid_page():
    with pytest.raises(ValueError, match="Invalid page number"):
        parse_pages_arg("1,nope")


def test_create_client_can_create_dry_run_client():
    client = create_client(provider="dry-run", model="ignored")

    assert client.model == "dry-run-no-llm"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_reconciler.py::test_parse_pages_arg_accepts_comma_list -q
```

Expected: FAIL with `ModuleNotFoundError` for `scripts.run_reconcile`.

- [ ] **Step 3: Implement CLI wrapper with OpenAI and dry-run providers**

Create `scripts/run_reconcile.py`:

```python
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from pdf_extract.reconciler import OpenAIResponsesVisionClient, run_reconciliation


class DryRunVisionClient:
    model = "dry-run-no-llm"

    def reconcile(self, *, image_path: Path, prompt: str) -> dict[str, Any]:
        return {
            "reconciled_markdown": (
                "<!-- dry-run reconciliation did not call a vision model -->\n"
            ),
            "winner": "uncertain",
            "warnings": ["dry-run client did not call a vision model"],
            "needs_human_review": True,
        }


def create_client(*, provider: str, model: str):
    if provider == "dry-run":
        return DryRunVisionClient()
    if provider == "openai":
        return OpenAIResponsesVisionClient(model=model)
    raise ValueError(f"Unsupported provider: {provider}")


def parse_pages_arg(value: str | None) -> list[int] | None:
    if value is None or value.strip() == "":
        return None
    pages: list[int] = []
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part.isdigit():
            raise ValueError(f"Invalid page number: {part!r}")
        page = int(part)
        if page < 1:
            raise ValueError(f"Invalid page number: {part!r}")
        pages.append(page)
    return sorted(set(pages))


def create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run page-level OCR reconciliation and publish artifacts."
    )
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
        default=None,
        help="Optional directory for viewer-manifest.json.",
    )
    parser.add_argument(
        "--pages",
        help="Comma-separated page numbers. Omit to reconcile all discovered pages.",
    )
    parser.add_argument(
        "--provider",
        choices=("openai", "dry-run"),
        default="openai",
        help="Model provider. Use dry-run for local pipeline tests.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENAI_RECONCILE_MODEL", "gpt-5.5"),
        help="Vision-capable model name for --provider openai.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rerun selected pages even if already published.",
    )
    return parser


def main() -> int:
    parser = create_arg_parser()
    args = parser.parse_args()

    result = run_reconciliation(
        run_root=args.run_root,
        object_store_root=args.object_store_root,
        sqlite_path=args.sqlite_path,
        viewer_dir=args.viewer_dir,
        client=create_client(provider=args.provider, model=args.model),
        pages=parse_pages_arg(args.pages),
        force=args.force,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run parser tests**

Run:

```bash
uv run pytest tests/test_reconciler.py::test_parse_pages_arg_accepts_comma_list tests/test_reconciler.py::test_parse_pages_arg_accepts_blank_as_all_pages tests/test_reconciler.py::test_parse_pages_arg_rejects_invalid_page tests/test_reconciler.py::test_create_client_can_create_dry_run_client -q
```

Expected: PASS.

- [ ] **Step 5: Smoke the dry-run CLI on synthetic data**

Run:

```bash
tmpdir="$(mktemp -d)"
mkdir -p "$tmpdir/runs/doc/union/pages/page_0001" "$tmpdir/runs/doc/small/pages/page_0001"
printf 'union page\n' > "$tmpdir/runs/doc/union/pages/page_0001/output.md"
printf 'small page\n' > "$tmpdir/runs/doc/small/pages/page_0001/output.md"
printf 'png' > "$tmpdir/runs/doc/union/pages/page_0001/page.png"
printf 'png' > "$tmpdir/runs/doc/small/pages/page_0001/page.png"
uv run python scripts/run_reconcile.py \
  --run-root "$tmpdir/runs/doc" \
  --object-store-root "$tmpdir/object_store" \
  --sqlite-path "$tmpdir/catalog.sqlite" \
  --viewer-dir "$tmpdir/viewer" \
  --provider dry-run
```

Expected: JSON output includes `"processed_pages": [1]`, `"published_pages": [1]`, and a `viewer_manifest_path`.

- [ ] **Step 6: Run broader tests**

Run:

```bash
uv run pytest tests/test_reconciler.py tests/test_reconciled_store.py tests/test_reconciled_viewer.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add scripts/run_reconcile.py tests/test_reconciler.py
git commit -m "Add reconcile CLI wrapper"
```

## Task 6: README Documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a README section**

Add this after the dual-mode run instructions:

```markdown
## Reconcile Page OCR

After running both `union` and `small` extraction modes for a document, run the
page-level reconciler to publish reconciled Markdown artifacts:

```bash
uv run python scripts/run_reconcile.py \
  --run-root runs/Full_30015375000000 \
  --object-store-root object_store \
  --sqlite-path reconciled_catalog.sqlite \
  --viewer-dir runs/Full_30015375000000/reconciled_viewer \
  --provider openai \
  --model gpt-5.5
```

If `--pages` is omitted, the reconciler discovers all pages present in both
`union` and `small`. Already published pages are skipped by default so a long run
can be restarted without repeating model calls.

Use `--pages` to reconcile a subset:

```bash
uv run python scripts/run_reconcile.py \
  --run-root runs/Full_30015375000000 \
  --pages 1,2,40 \
  --provider openai \
  --model gpt-5.5
```

Use `--force` to regenerate pages already published in the SQLite catalog:

```bash
uv run python scripts/run_reconcile.py \
  --run-root runs/Full_30015375000000 \
  --pages 28 \
  --force \
  --provider openai \
  --model gpt-5.5
```

For local pipeline validation without a model call, use `--provider dry-run`.
Real OpenAI runs require `OPENAI_API_KEY`. The default model can be overridden
with `--model` or `OPENAI_RECONCILE_MODEL`.
```

- [ ] **Step 2: Run tests**

Run:

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Document page OCR reconciliation"
```

## Task 7: Final Verification

**Files:**
- No code edits.

- [ ] **Step 1: Run full pytest suite**

Run:

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run dry-run CLI smoke test**

Run:

```bash
tmpdir="$(mktemp -d)"
mkdir -p "$tmpdir/runs/doc/union/pages/page_0001" "$tmpdir/runs/doc/small/pages/page_0001"
printf 'union page\n' > "$tmpdir/runs/doc/union/pages/page_0001/output.md"
printf 'small page\n' > "$tmpdir/runs/doc/small/pages/page_0001/output.md"
printf 'png' > "$tmpdir/runs/doc/union/pages/page_0001/page.png"
printf 'png' > "$tmpdir/runs/doc/small/pages/page_0001/page.png"
uv run python scripts/run_reconcile.py \
  --run-root "$tmpdir/runs/doc" \
  --object-store-root "$tmpdir/object_store" \
  --sqlite-path "$tmpdir/catalog.sqlite" \
  --viewer-dir "$tmpdir/viewer" \
  --provider dry-run
test -f "$tmpdir/object_store/pdf-extract/reconciled/doc/pages/page_0001/output.md"
test -f "$tmpdir/object_store/pdf-extract/reconciled/doc/pages/page_0001/decision.json"
test -f "$tmpdir/object_store/pdf-extract/reconciled/doc/pages/page_0001/assets.json"
test -f "$tmpdir/viewer/viewer-manifest.json"
```

Expected: command exits `0`.

- [ ] **Step 3: Confirm no `res.json` source refs**

Run:

```bash
rg -n "union_json|small_json|source_refs.*res" pdf_extract/reconciler.py scripts/run_reconcile.py
```

Expected: no matches.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short
```

Expected: only intentional changes remain.
