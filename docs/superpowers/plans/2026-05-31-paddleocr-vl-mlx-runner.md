# PaddleOCR-VL MLX Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and smoke test a resumable page-by-page PaddleOCR-VL runner that uses the MLX VLM server backend and preserves each page's rendered PNG plus PaddleOCR artifacts.

**Architecture:** The CLI delegates pure behavior to a small `pdf_extract` package so resume logic, page parsing, artifact checks, and combining outputs can be tested without PaddleOCR. The runtime path renders one PDF page at a time with PaddleX-compatible `pypdfium2` settings, calls a single long-lived `PaddleOCRVL` pipeline, and saves each page bundle atomically before appending manifest status.

**Tech Stack:** Python 3.11+, `paddleocr[doc-parser]`, `pypdfium2`, `Pillow`, `tqdm`, `pytest`.

---

## File Structure

- `pyproject.toml`: project metadata, dependencies, pytest config, console script.
- `scripts/run_pdf_vl.py`: thin executable wrapper for local script usage.
- `pdf_extract/__init__.py`: package marker and version.
- `pdf_extract/cli.py`: argument parsing and orchestration.
- `pdf_extract/page_ranges.py`: parse `--pages` specs.
- `pdf_extract/manifest.py`: append/load manifest entries and check completed pages.
- `pdf_extract/render.py`: PaddleX-compatible PDF page rendering.
- `pdf_extract/paddle_output.py`: save PaddleOCR result objects to the expected bundle.
- `pdf_extract/combine.py`: build `combined.md`, `combined.jsonl`, and `failed_pages.txt`.
- `tests/`: focused unit tests for pure helper behavior.

## Tasks

### Task 1: Project Skeleton And Page Range Parser

**Files:**
- Create: `pyproject.toml`
- Create: `pdf_extract/__init__.py`
- Create: `pdf_extract/page_ranges.py`
- Create: `tests/test_page_ranges.py`

- [ ] **Step 1: Write failing page range tests**

Create `tests/test_page_ranges.py`:

```python
import pytest

from pdf_extract.page_ranges import parse_page_spec


def test_parse_none_selects_all_pages():
    assert parse_page_spec(None, total_pages=3) == [1, 2, 3]


def test_parse_single_ranges_and_commas():
    assert parse_page_spec("1,3,5-7", total_pages=8) == [1, 3, 5, 6, 7]


def test_parse_deduplicates_and_sorts():
    assert parse_page_spec("3,1-2,2", total_pages=5) == [1, 2, 3]


@pytest.mark.parametrize("spec", ["0", "4", "3-2", "abc"])
def test_parse_rejects_invalid_specs(spec):
    with pytest.raises(ValueError):
        parse_page_spec(spec, total_pages=3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_page_ranges.py -v`
Expected: FAIL because `pdf_extract` does not exist yet.

- [ ] **Step 3: Add project metadata and parser**

Create `pyproject.toml`:

```toml
[project]
name = "pdf-extract"
version = "0.1.0"
description = "Resumable PaddleOCR-VL PDF extraction runner"
requires-python = ">=3.11"
dependencies = [
  "pypdfium2",
  "pillow",
  "tqdm",
]

[project.optional-dependencies]
dev = ["pytest"]
paddle = ["paddleocr[doc-parser]"]

[project.scripts]
run-pdf-vl = "pdf_extract.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Create `pdf_extract/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `pdf_extract/page_ranges.py`:

```python
from __future__ import annotations


def parse_page_spec(spec: str | None, *, total_pages: int) -> list[int]:
    if total_pages < 1:
        return []
    if spec is None or spec.strip() == "":
        return list(range(1, total_pages + 1))

    pages: set[int] = set()
    for raw_part in spec.split(","):
        part = raw_part.strip()
        if not part:
            raise ValueError(f"Invalid empty page range in {spec!r}")
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            if not start_text.isdigit() or not end_text.isdigit():
                raise ValueError(f"Invalid page range {part!r}")
            start = int(start_text)
            end = int(end_text)
            if start < 1 or end < start or end > total_pages:
                raise ValueError(f"Page range {part!r} is outside 1-{total_pages}")
            pages.update(range(start, end + 1))
        else:
            if not part.isdigit():
                raise ValueError(f"Invalid page number {part!r}")
            page = int(part)
            if page < 1 or page > total_pages:
                raise ValueError(f"Page {page} is outside 1-{total_pages}")
            pages.add(page)
    return sorted(pages)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_page_ranges.py -v`
Expected: PASS.

### Task 2: Manifest And Completion Logic

**Files:**
- Create: `pdf_extract/manifest.py`
- Create: `tests/test_manifest.py`

- [ ] **Step 1: Write failing manifest tests**

Create `tests/test_manifest.py`:

```python
import json

from pdf_extract.manifest import append_manifest_entry, is_page_complete, load_latest_manifest


def test_load_latest_manifest_uses_last_entry_per_page(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        "\n".join(
            [
                json.dumps({"page": 1, "status": "failed", "attempt": 1}),
                json.dumps({"page": 1, "status": "ok", "attempt": 2}),
                json.dumps({"page": 2, "status": "failed", "attempt": 1}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    latest = load_latest_manifest(manifest)

    assert latest[1]["status"] == "ok"
    assert latest[1]["attempt"] == 2
    assert latest[2]["status"] == "failed"


def test_append_manifest_entry_writes_json_line(tmp_path):
    manifest = tmp_path / "manifest.jsonl"

    append_manifest_entry(manifest, {"page": 3, "status": "ok"})

    assert json.loads(manifest.read_text(encoding="utf-8")) == {"page": 3, "status": "ok"}


def test_is_page_complete_requires_ok_manifest_and_bundle_files(tmp_path):
    page_dir = tmp_path / "pages" / "page_0001"
    page_dir.mkdir(parents=True)
    for name in ["page.png", "layout_det_res.png", "res.json", "output.docx", "output.md"]:
        (page_dir / name).write_bytes(b"x")

    assert is_page_complete(1, tmp_path, {1: {"status": "ok"}}, require_page_image=True)
    assert not is_page_complete(1, tmp_path, {1: {"status": "failed"}}, require_page_image=True)


def test_is_page_complete_can_skip_page_image_requirement(tmp_path):
    page_dir = tmp_path / "pages" / "page_0001"
    page_dir.mkdir(parents=True)
    for name in ["layout_det_res.png", "res.json", "output.docx", "output.md"]:
        (page_dir / name).write_bytes(b"x")

    assert is_page_complete(1, tmp_path, {1: {"status": "ok"}}, require_page_image=False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_manifest.py -v`
Expected: FAIL because `pdf_extract.manifest` does not exist yet.

- [ ] **Step 3: Implement manifest helpers**

Create `pdf_extract/manifest.py` with append-only JSONL loading and bundle checks.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_manifest.py -v`
Expected: PASS.

### Task 3: PaddleX-Compatible PDF Rendering

**Files:**
- Create: `pdf_extract/render.py`
- Create: `tests/test_render.py`

- [ ] **Step 1: Write failing renderer smoke test**

Create `tests/test_render.py`:

```python
from pdf_extract.render import page_dir_name, render_page_to_png


def test_page_dir_name_zero_pads():
    assert page_dir_name(7) == "page_0007"


def test_render_page_to_png_creates_png(tmp_path):
    pdf_path = tmp_path / "one_page.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 100 100]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000056 00000 n \n0000000111 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n181\n%%EOF\n"
    )
    out_path = tmp_path / "page.png"

    render_page_to_png(pdf_path, page_number=1, out_path=out_path)

    assert out_path.read_bytes().startswith(b"\x89PNG")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_render.py -v`
Expected: FAIL because `pdf_extract.render` does not exist yet.

- [ ] **Step 3: Implement renderer**

Create a renderer using `pypdfium2` with scale `2.0`, min scale `0.1`, max pixels `178_956_970`, and output conversion to RGB PNG.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_render.py -v`
Expected: PASS.

### Task 4: Save PaddleOCR Artifacts And Combine Outputs

**Files:**
- Create: `pdf_extract/paddle_output.py`
- Create: `pdf_extract/combine.py`
- Create: `tests/test_outputs.py`

- [ ] **Step 1: Write failing output tests**

Create `tests/test_outputs.py`:

```python
import json

from pdf_extract.combine import write_combined_outputs
from pdf_extract.paddle_output import atomic_write_bytes, atomic_write_text


def test_atomic_writes_create_files(tmp_path):
    atomic_write_text(tmp_path / "a.txt", "hello")
    atomic_write_bytes(tmp_path / "b.bin", b"world")

    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "hello"
    assert (tmp_path / "b.bin").read_bytes() == b"world"


def test_write_combined_outputs_uses_successful_pages(tmp_path):
    for page in [1, 2]:
        page_dir = tmp_path / "pages" / f"page_{page:04d}"
        page_dir.mkdir(parents=True)
        (page_dir / "output.md").write_text(f"page {page}", encoding="utf-8")
        (page_dir / "res.json").write_text(json.dumps({"page": page}), encoding="utf-8")

    write_combined_outputs(tmp_path, ok_pages=[1], failed_pages=[2])

    assert "# Page 1" in (tmp_path / "combined.md").read_text(encoding="utf-8")
    assert "page 1" in (tmp_path / "combined.md").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "combined.jsonl").read_text(encoding="utf-8")) == {"page": 1}
    assert (tmp_path / "failed_pages.txt").read_text(encoding="utf-8") == "2\n"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_outputs.py -v`
Expected: FAIL because output helpers do not exist yet.

- [ ] **Step 3: Implement output helpers**

Implement atomic write helpers, result bundle saving with PaddleOCR's `save_to_*` methods when available, and combined output generation.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_outputs.py -v`
Expected: PASS.

### Task 5: CLI Runner

**Files:**
- Create: `pdf_extract/cli.py`
- Create: `scripts/run_pdf_vl.py`

- [ ] **Step 1: Implement CLI orchestration**

Build `argparse` CLI with `input_pdf`, `--out`, `--pages`, `--resume`, `--no-resume`, `--force`, `--retries`, `--fail-fast`, `--timeout-sec`, `--server-url`, `--model-name`, `--layout-merge-bboxes-mode`, and `--no-save-page-image`.

- [ ] **Step 2: Wire PaddleOCR pipeline**

Load `PaddleOCRVL` once with the approved MLX backend defaults and pass each rendered `page.png` to `pipeline.predict()`.

- [ ] **Step 3: Save config, manifest, outputs, and progress**

Write `config.json`, append manifest attempts, update `tqdm`, and generate combined outputs at the end.

- [ ] **Step 4: Run CLI help**

Run: `python -m pdf_extract.cli --help`
Expected: command exits 0 and shows runner options.

### Task 6: Verification And Smoke Test

**Files:**
- Modify only if verification finds an issue.

- [ ] **Step 1: Run full unit suite**

Run: `pytest -v`
Expected: PASS.

- [ ] **Step 2: Smoke test import/light CLI**

Run: `python scripts/run_pdf_vl.py --help`
Expected: command exits 0.

- [ ] **Step 3: Real PaddleOCR smoke test if dependencies and MLX server are available**

Run: `python scripts/run_pdf_vl.py <input.pdf> --out runs/smoke_page1 --pages 1 --resume`
Expected: page bundle contains `page.png`, `layout_det_res.png`, `res.json`, `output.docx`, and `output.md`.

If no input PDF or MLX server is available, record that real OCR smoke testing is blocked and provide the exact command to run.

## Self-Review

- Spec coverage: CLI, page rendering, page bundle layout, manifest resume, atomic writes, failures, and combined outputs are covered.
- Placeholder scan: no `TBD`, `TODO`, or unspecified tests remain.
- Type consistency: page numbers are 1-based at the runner boundary; page folders use `page_NNNN`.
