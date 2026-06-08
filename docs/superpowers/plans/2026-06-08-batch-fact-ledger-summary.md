# Batch Fact Ledger Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Markdown-only batch fact ledger pipeline that turns reconciled page Markdown into `fact_ledger.jsonl` and `combined_summary_current.md`.

**Architecture:** Add one focused summary module that owns page discovery, 10-page overlapping batches, source-ID grounded prompts, fact validation, ledger writing, simple dedupe, reducer prompting, and orchestration. Add one CLI wrapper for OpenAI and dry-run execution. Tests use deterministic fake model clients and temporary reconciled object-store pages.

**Tech Stack:** Python 3.10+, standard library dataclasses/json/pathlib/re, existing `openai` dependency, `pytest`.

---

## File Map

- Create `pdf_extract/wellbore_summary.py`
  - Owns dataclasses, constants, response schemas, source-page discovery, batch construction, prompt building, fact validation, fact ledger JSONL writing, dedupe helpers, reducer prompt building, OpenAI text client, and `run_wellbore_summary`.
- Create `scripts/run_wellbore_summary.py`
  - CLI wrapper around `run_wellbore_summary`.
  - Supports `--document-id`, `--object-store-root`, `--out-dir`, `--provider`, and `--model`.
  - Loads `OPENAI_API_KEY` from repo `.env` using the same small pattern as `scripts/run_reconcile.py`.
- Create `tests/test_wellbore_summary.py`
  - Unit and integration-style tests for batches, source IDs, schema validation, prompts, ledger writing, dedupe, reducer prompt, orchestration, and CLI helper functions.
- Modify `README.md`
  - Add a short usage section for the summary CLI after page reconciliation.
- Do not modify page reconciliation behavior.
- Do not add LlamaIndex, Haystack, embeddings, retrieval, or image inputs.

## Public Interfaces To Build

The implementation should expose these names from `pdf_extract.wellbore_summary`:

```python
SUMMARY_SECTIONS: tuple[str, ...]
STATUS_HINTS: tuple[str, ...]
CONFIDENCE_LEVELS: tuple[str, ...]
DEFAULT_FACT_SCOUT_MODEL: str
FACT_SCOUT_PROMPT_VERSION: str
REDUCER_PROMPT_VERSION: str

@dataclass(frozen=True)
class ReconciledSummaryPage:
    document_id: str
    page: int
    source_id: str
    markdown_key: str
    markdown: str
    needs_human_review: bool

@dataclass(frozen=True)
class SummaryBatch:
    document_id: str
    batch_id: str
    pages: tuple[ReconciledSummaryPage, ...]

@dataclass(frozen=True)
class CandidateFact:
    section: str
    field: str
    value: str
    source_page_ids: tuple[str, ...]
    source_context: str
    source_snippet: str
    status_hint: str
    confidence: str
    notes: str

@dataclass(frozen=True)
class BatchFactResult:
    document_id: str
    batch_id: str
    batch_pages: tuple[int, ...]
    model: str
    prompt_version: str
    facts: tuple[CandidateFact, ...]
    warnings: tuple[str, ...]

class TextModelClient(Protocol):
    model: str
    def create_json(self, *, prompt: str, response_format: dict[str, Any]) -> Mapping[str, Any]: ...
    def create_text(self, *, prompt: str) -> str: ...
```

---

### Task 1: Define Summary Data Objects And Validation

**Files:**
- Create: `pdf_extract/wellbore_summary.py`
- Create: `tests/test_wellbore_summary.py`

- [ ] **Step 1: Write failing tests for candidate fact validation**

Add this to `tests/test_wellbore_summary.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf_extract.wellbore_summary import (
    BatchFactResult,
    CandidateFact,
    build_fact_scout_response_format,
    parse_batch_fact_result,
    source_id_for_page,
)


def valid_payload() -> dict:
    return {
        "facts": [
            {
                "section": "casing_and_tubing_strings",
                "field": "production_casing",
                "value": "5-1/2 inch casing set at 10,490 ft",
                "source_page_ids": ["page_0028"],
                "source_context": "C-105 completion report casing table",
                "source_snippet": "5-1/2 ... 10,490",
                "status_hint": "actual",
                "confidence": "high",
                "notes": "Completion table supports the production casing setting depth.",
            }
        ],
        "warnings": [],
    }


def test_source_id_for_page_formats_four_digits():
    assert source_id_for_page(1) == "page_0001"
    assert source_id_for_page(28) == "page_0028"


def test_parse_batch_fact_result_accepts_valid_payload():
    result = parse_batch_fact_result(
        payload=valid_payload(),
        document_id="Full_30015375000000",
        batch_id="pages_0028_0037",
        batch_pages=(28, 29, 30),
        allowed_source_ids=("page_0028", "page_0029", "page_0030"),
        model="fake-model",
        prompt_version="wellbore-fact-scout-v1",
    )

    assert isinstance(result, BatchFactResult)
    assert result.batch_pages == (28, 29, 30)
    assert result.facts[0].source_page_ids == ("page_0028",)
    assert result.facts[0].status_hint == "actual"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("section", "bad_section", "Unsupported section"),
        ("status_hint", "current", "Unsupported status_hint"),
        ("confidence", "certain", "Unsupported confidence"),
    ],
)
def test_parse_batch_fact_result_rejects_invalid_enums(field, value, message):
    payload = valid_payload()
    payload["facts"][0][field] = value

    with pytest.raises(ValueError, match=message):
        parse_batch_fact_result(
            payload=payload,
            document_id="doc",
            batch_id="pages_0028_0037",
            batch_pages=(28,),
            allowed_source_ids=("page_0028",),
            model="fake-model",
            prompt_version="wellbore-fact-scout-v1",
        )


def test_parse_batch_fact_result_rejects_numeric_page_citation():
    payload = valid_payload()
    payload["facts"][0]["source_page_ids"] = [28]

    with pytest.raises(ValueError, match="source_page_ids must be strings"):
        parse_batch_fact_result(
            payload=payload,
            document_id="doc",
            batch_id="pages_0028_0037",
            batch_pages=(28,),
            allowed_source_ids=("page_0028",),
            model="fake-model",
            prompt_version="wellbore-fact-scout-v1",
        )


def test_parse_batch_fact_result_rejects_source_outside_manifest():
    payload = valid_payload()
    payload["facts"][0]["source_page_ids"] = ["page_9999"]

    with pytest.raises(ValueError, match="outside batch source manifest"):
        parse_batch_fact_result(
            payload=payload,
            document_id="doc",
            batch_id="pages_0028_0037",
            batch_pages=(28,),
            allowed_source_ids=("page_0028",),
            model="fake-model",
            prompt_version="wellbore-fact-scout-v1",
        )


def test_parse_batch_fact_result_requires_source_snippet():
    payload = valid_payload()
    payload["facts"][0]["source_snippet"] = ""

    with pytest.raises(ValueError, match="source_snippet is required"):
        parse_batch_fact_result(
            payload=payload,
            document_id="doc",
            batch_id="pages_0028_0037",
            batch_pages=(28,),
            allowed_source_ids=("page_0028",),
            model="fake-model",
            prompt_version="wellbore-fact-scout-v1",
        )


def test_build_fact_scout_response_format_limits_source_ids_to_batch():
    schema = build_fact_scout_response_format(("page_0028", "page_0029"))
    facts = schema["schema"]["properties"]["facts"]["items"]["properties"]

    assert facts["source_page_ids"]["items"]["enum"] == ["page_0028", "page_0029"]
    assert schema["schema"]["additionalProperties"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pdf_extract.wellbore_summary'`.

- [ ] **Step 3: Create minimal validation implementation**

Create `pdf_extract/wellbore_summary.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence


SUMMARY_SECTIONS: tuple[str, ...] = (
    "well_identity",
    "elevations",
    "operation_timeline",
    "hole_sections",
    "casing_and_tubing_strings",
    "downhole_items_and_reference_depths",
    "cement_jobs",
    "plugs",
    "perforations_and_treatments",
    "directional_and_lateral_details",
    "formation_tops",
)
STATUS_HINTS: tuple[str, ...] = ("actual", "proposed", "historical", "uncertain", "unknown")
CONFIDENCE_LEVELS: tuple[str, ...] = ("high", "medium", "low")
DEFAULT_FACT_SCOUT_MODEL = "gpt-5.4-mini"
FACT_SCOUT_PROMPT_VERSION = "wellbore-fact-scout-v1"
REDUCER_PROMPT_VERSION = "wellbore-current-reducer-v1"


@dataclass(frozen=True)
class ReconciledSummaryPage:
    document_id: str
    page: int
    source_id: str
    markdown_key: str
    markdown: str
    needs_human_review: bool = False


@dataclass(frozen=True)
class SummaryBatch:
    document_id: str
    batch_id: str
    pages: tuple[ReconciledSummaryPage, ...]


@dataclass(frozen=True)
class CandidateFact:
    section: str
    field: str
    value: str
    source_page_ids: tuple[str, ...]
    source_context: str
    source_snippet: str
    status_hint: str
    confidence: str
    notes: str


@dataclass(frozen=True)
class BatchFactResult:
    document_id: str
    batch_id: str
    batch_pages: tuple[int, ...]
    model: str
    prompt_version: str
    facts: tuple[CandidateFact, ...]
    warnings: tuple[str, ...]


class TextModelClient(Protocol):
    model: str

    def create_json(self, *, prompt: str, response_format: dict[str, Any]) -> Mapping[str, Any]:
        ...

    def create_text(self, *, prompt: str) -> str:
        ...


def source_id_for_page(page: int) -> str:
    if page < 1:
        raise ValueError("page must be >= 1")
    return f"page_{page:04d}"


def build_fact_scout_response_format(source_ids: Sequence[str]) -> dict[str, Any]:
    source_id_enum = list(source_ids)
    return {
        "type": "json_schema",
        "name": "wellbore_batch_fact_result",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["facts", "warnings"],
            "properties": {
                "facts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "section",
                            "field",
                            "value",
                            "source_page_ids",
                            "source_context",
                            "source_snippet",
                            "status_hint",
                            "confidence",
                            "notes",
                        ],
                        "properties": {
                            "section": {"type": "string", "enum": list(SUMMARY_SECTIONS)},
                            "field": {"type": "string"},
                            "value": {"type": "string"},
                            "source_page_ids": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"type": "string", "enum": source_id_enum},
                            },
                            "source_context": {"type": "string"},
                            "source_snippet": {"type": "string"},
                            "status_hint": {"type": "string", "enum": list(STATUS_HINTS)},
                            "confidence": {"type": "string", "enum": list(CONFIDENCE_LEVELS)},
                            "notes": {"type": "string"},
                        },
                    },
                },
                "warnings": {"type": "array", "items": {"type": "string"}},
            },
        },
    }


def _require_string(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    if not value.strip():
        raise ValueError(f"{field} is required")
    return value


def _candidate_fact_from_payload(
    payload: Mapping[str, Any],
    *,
    allowed_source_ids: set[str],
) -> CandidateFact:
    section = _require_string(payload, "section")
    if section not in SUMMARY_SECTIONS:
        raise ValueError(f"Unsupported section: {section}")
    status_hint = _require_string(payload, "status_hint")
    if status_hint not in STATUS_HINTS:
        raise ValueError(f"Unsupported status_hint: {status_hint}")
    confidence = _require_string(payload, "confidence")
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError(f"Unsupported confidence: {confidence}")

    raw_source_ids = payload.get("source_page_ids")
    if not isinstance(raw_source_ids, list) or not raw_source_ids:
        raise ValueError("source_page_ids must be a non-empty list")
    if not all(isinstance(item, str) for item in raw_source_ids):
        raise ValueError("source_page_ids must be strings")
    source_page_ids = tuple(dict.fromkeys(raw_source_ids))
    outside = [item for item in source_page_ids if item not in allowed_source_ids]
    if outside:
        raise ValueError(f"source_page_ids outside batch source manifest: {outside}")

    return CandidateFact(
        section=section,
        field=_require_string(payload, "field"),
        value=_require_string(payload, "value"),
        source_page_ids=source_page_ids,
        source_context=_require_string(payload, "source_context"),
        source_snippet=_require_string(payload, "source_snippet"),
        status_hint=status_hint,
        confidence=confidence,
        notes=_require_string(payload, "notes"),
    )


def parse_batch_fact_result(
    *,
    payload: Mapping[str, Any],
    document_id: str,
    batch_id: str,
    batch_pages: Sequence[int],
    allowed_source_ids: Sequence[str],
    model: str,
    prompt_version: str,
) -> BatchFactResult:
    raw_facts = payload.get("facts")
    if not isinstance(raw_facts, list):
        raise ValueError("facts must be a list")
    raw_warnings = payload.get("warnings")
    if not isinstance(raw_warnings, list) or not all(isinstance(item, str) for item in raw_warnings):
        raise ValueError("warnings must be a list[str]")

    allowed = set(allowed_source_ids)
    facts = tuple(
        _candidate_fact_from_payload(fact, allowed_source_ids=allowed)
        for fact in raw_facts
    )
    return BatchFactResult(
        document_id=document_id,
        batch_id=batch_id,
        batch_pages=tuple(batch_pages),
        model=model,
        prompt_version=prompt_version,
        facts=facts,
        warnings=tuple(raw_warnings),
    )
```

- [ ] **Step 4: Run validation tests**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py -v
```

Expected: PASS for the Task 1 tests.

- [ ] **Step 5: Commit Task 1**

```bash
git add pdf_extract/wellbore_summary.py tests/test_wellbore_summary.py
git commit -m "Add wellbore summary fact schema"
```

---

### Task 2: Discover Reconciled Pages And Build Overlapping Batches

**Files:**
- Modify: `pdf_extract/wellbore_summary.py`
- Modify: `tests/test_wellbore_summary.py`

- [ ] **Step 1: Write failing tests for page loading and batching**

Append to `tests/test_wellbore_summary.py`:

```python
from pdf_extract.wellbore_summary import (
    build_summary_batches,
    discover_reconciled_summary_pages,
    page_number_from_source_id,
    ReconciledSummaryPage,
    SummaryBatch,
)


def write_reconciled_page(root: Path, document_id: str, page: int, markdown: str, *, review: bool = False):
    page_dir = root / "pdf-extract" / "reconciled" / document_id / "pages" / f"page_{page:04d}"
    page_dir.mkdir(parents=True)
    (page_dir / "output.md").write_text(markdown, encoding="utf-8")
    (page_dir / "decision.json").write_text(
        json.dumps({"needs_human_review": review}) + "\n",
        encoding="utf-8",
    )


def test_page_number_from_source_id_parses_source_id():
    assert page_number_from_source_id("page_0028") == 28
    with pytest.raises(ValueError, match="Invalid source_id"):
        page_number_from_source_id("28")


def test_discover_reconciled_summary_pages_reads_sorted_pages(tmp_path):
    root = tmp_path / "object_store"
    write_reconciled_page(root, "doc", 2, "second page", review=True)
    write_reconciled_page(root, "doc", 1, "first page")

    pages = discover_reconciled_summary_pages(
        object_store_root=root,
        document_id="doc",
    )

    assert [page.page for page in pages] == [1, 2]
    assert pages[0].source_id == "page_0001"
    assert pages[0].markdown_key == "pdf-extract/reconciled/doc/pages/page_0001/output.md"
    assert pages[1].needs_human_review is True
    assert pages[1].markdown == "second page"


def test_build_summary_batches_uses_ten_pages_with_one_overlap():
    pages = tuple(
        ReconciledSummaryPage(
            document_id="doc",
            page=page,
            source_id=source_id_for_page(page),
            markdown_key=f"key-{page}",
            markdown=f"page {page}",
        )
        for page in range(1, 22)
    )

    batches = build_summary_batches(pages, batch_size=10, overlap=1)

    assert [batch.batch_id for batch in batches] == [
        "pages_0001_0010",
        "pages_0010_0019",
        "pages_0019_0021",
    ]
    assert [[page.page for page in batch.pages] for batch in batches] == [
        list(range(1, 11)),
        list(range(10, 20)),
        [19, 20, 21],
    ]


def test_build_summary_batches_rejects_overlap_not_less_than_batch_size():
    pages = (
        ReconciledSummaryPage(
            document_id="doc",
            page=1,
            source_id="page_0001",
            markdown_key="key",
            markdown="text",
        ),
    )

    with pytest.raises(ValueError, match="overlap must be smaller"):
        build_summary_batches(pages, batch_size=10, overlap=10)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py -v
```

Expected: FAIL with `ImportError` for `discover_reconciled_summary_pages`, `build_summary_batches`, or `page_number_from_source_id`.

- [ ] **Step 3: Implement page discovery and batching**

Add imports and functions to `pdf_extract/wellbore_summary.py`:

```python
import json
import re


_SOURCE_ID_RE = re.compile(r"^page_(\d{4,})$")


def page_number_from_source_id(source_id: str) -> int:
    match = _SOURCE_ID_RE.match(source_id)
    if not match:
        raise ValueError(f"Invalid source_id: {source_id}")
    return int(match.group(1))


def _page_number_from_page_dir(path: Path) -> int | None:
    try:
        return page_number_from_source_id(path.name)
    except ValueError:
        return None


def discover_reconciled_summary_pages(
    *,
    object_store_root: Path,
    document_id: str,
) -> tuple[ReconciledSummaryPage, ...]:
    pages_root = object_store_root / "pdf-extract" / "reconciled" / document_id / "pages"
    if not pages_root.is_dir():
        raise FileNotFoundError(f"Missing reconciled pages directory: {pages_root}")

    pages: list[ReconciledSummaryPage] = []
    for page_dir in sorted(pages_root.iterdir()):
        page = _page_number_from_page_dir(page_dir)
        if page is None:
            continue
        output_path = page_dir / "output.md"
        if not output_path.is_file():
            continue
        decision_path = page_dir / "decision.json"
        needs_human_review = False
        if decision_path.is_file():
            try:
                decision = json.loads(decision_path.read_text(encoding="utf-8"))
                needs_human_review = bool(decision.get("needs_human_review", False))
            except json.JSONDecodeError:
                needs_human_review = False
        markdown_key = output_path.relative_to(object_store_root).as_posix()
        pages.append(
            ReconciledSummaryPage(
                document_id=document_id,
                page=page,
                source_id=source_id_for_page(page),
                markdown_key=markdown_key,
                markdown=output_path.read_text(encoding="utf-8"),
                needs_human_review=needs_human_review,
            )
        )
    return tuple(sorted(pages, key=lambda item: item.page))


def build_summary_batches(
    pages: Sequence[ReconciledSummaryPage],
    *,
    batch_size: int = 10,
    overlap: int = 1,
) -> tuple[SummaryBatch, ...]:
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap >= batch_size:
        raise ValueError("overlap must be smaller than batch_size")
    ordered = tuple(sorted(pages, key=lambda item: item.page))
    if not ordered:
        return ()

    step = batch_size - overlap
    batches: list[SummaryBatch] = []
    start = 0
    while start < len(ordered):
        batch_pages = ordered[start : start + batch_size]
        first_page = batch_pages[0].page
        last_page = batch_pages[-1].page
        batches.append(
            SummaryBatch(
                document_id=batch_pages[0].document_id,
                batch_id=f"pages_{first_page:04d}_{last_page:04d}",
                pages=tuple(batch_pages),
            )
        )
        if start + batch_size >= len(ordered):
            break
        start += step
    return tuple(batches)
```

- [ ] **Step 4: Run batching tests**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py -v
```

Expected: PASS for Task 1 and Task 2 tests.

- [ ] **Step 5: Commit Task 2**

```bash
git add pdf_extract/wellbore_summary.py tests/test_wellbore_summary.py
git commit -m "Add reconciled summary page batching"
```

---

### Task 3: Build Source-ID Grounded Fact Scout Prompt

**Files:**
- Modify: `pdf_extract/wellbore_summary.py`
- Modify: `tests/test_wellbore_summary.py`

- [ ] **Step 1: Write failing prompt tests**

Append to `tests/test_wellbore_summary.py`:

```python
from pdf_extract.wellbore_summary import build_fact_scout_prompt


def test_build_fact_scout_prompt_uses_source_manifest_and_boundaries():
    batch = SummaryBatch(
        document_id="doc",
        batch_id="pages_0028_0029",
        pages=(
            ReconciledSummaryPage(
                document_id="doc",
                page=28,
                source_id="page_0028",
                markdown_key="key-28",
                markdown="C-105 casing table",
            ),
            ReconciledSummaryPage(
                document_id="doc",
                page=29,
                source_id="page_0029",
                markdown_key="key-29",
                markdown="Formation tops table",
            ),
        ),
    )

    prompt = build_fact_scout_prompt(batch)

    assert "Source manifest:" in prompt
    assert "- source_id: page_0028" in prompt
    assert "===== BEGIN SOURCE page_0028 =====" in prompt
    assert "===== END SOURCE page_0029 =====" in prompt
    assert "Do not cite page numbers printed inside the PDF/form/Markdown." in prompt
    assert "source_page_ids" in prompt
    assert "C-105 casing table" in prompt
    assert "Formation tops table" in prompt
```

- [ ] **Step 2: Run prompt test to verify it fails**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py::test_build_fact_scout_prompt_uses_source_manifest_and_boundaries -v
```

Expected: FAIL with `ImportError` for `build_fact_scout_prompt`.

- [ ] **Step 3: Implement fact scout prompt builder**

Add this to `pdf_extract/wellbore_summary.py`:

```python
FACT_SCOUT_INSTRUCTIONS = """You are extracting wellbore-diagram/current-data candidate facts from reconciled PDF Markdown.

You receive a batch of PDF page sources. Each source has a system-provided source_id such as `page_0028`. Use source IDs for citations. Use only the provided Markdown. Do not use outside knowledge. Do not guess.

Important source citation rule:
- Every fact must cite source_page_ids from the provided source manifest.
- Use source_id values exactly, such as page_0028.
- Do not cite the page's position inside this batch.
- Do not cite page numbers printed inside the PDF/form/Markdown.
- Do not invent source IDs.
- If one fact is supported by multiple sources in this batch, include all supporting source IDs.

Your job is not to write the final summary. Your job is to collect candidate facts that may help fill a current wellbore data summary.

Target sections:
- well_identity
- elevations
- operation_timeline
- hole_sections
- casing_and_tubing_strings
- downhole_items_and_reference_depths
- cement_jobs
- plugs
- perforations_and_treatments
- directional_and_lateral_details
- formation_tops

Extract facts about:
- well name, API, operator, location, county/state, coordinates, spud/completion dates
- GL/GR/KB/RKB/elevation datum values
- drilling/completion timeline events
- hole sizes and intervals
- casing/tubing strings, weights, grades, connections, setting depths
- TD, PBTD, KOP, TOC, DV tool, float collar, casing shoes, packers, plugs
- cement jobs, volumes, classes/blends, top/bottom depths, returns/circulation
- perforation depths, treatment intervals, acid/frac/squeeze/cement treatments
- directional/lateral MD/TVD ranges, azimuth/direction, pilot-hole details
- formation tops

Common source contexts you may see:
- APD / C-101 permit or application: often proposed well plan, proposed casing, proposed cement, proposed TD, proposed location.
- C-102 plat: location, SHL/BHL, section-township-range, county, coordinates, lease/well name.
- C-103 subsequent report / sundry notice: actual operations, casing set, cement jobs, plugs, drilling progress, TD, rig release, changes.
- C-104 request for allowable / authorization to transport: completion status, producing interval, first production, operator/well identity.
- C-105 well completion report: final TD/PBTD, casing/tubing, cement, formations, perforations, dates, elevations.
- C-105 continuation / attachment: perforation lists, treatment stages, casing/cement details.
- Directional plan: proposed KOP, planned MD/TVD, planned lateral, planned azimuth, target details.
- Directional survey / final survey: actual survey stations, MD/TVD, inclination, azimuth, closure, BHL, lateral direction.
- Formation tops table: formation names and top depths.
- Operator change / C-145 / transfer material: later/current operator, OGRID, effective dates.
- C-129 or production/transport forms: operator identity, API, well status, production/admin data.
- Wellbore diagram / schematic: visual summary of casing, cement, plugs, perforations, TD/PBTD, formation tops.
- Daily completion/workover narrative: tubing, packer, acid/frac/perforation stages, plugs, DV tool, cleanup.
- Unknown form/table/header: use this when the source type is not clear.

Use these labels inside source_context when they fit. Do not invent a form name when the provided source does not make it clear.

For each fact, return:
- section
- field
- value
- source_page_ids
- source_context
- source_snippet
- status_hint
- confidence
- notes

Rules:
- source_page_ids must contain one or more source_id values from the source manifest.
- source_snippet is required. Keep it short: enough to recognize the source evidence, not a long copy.
- source_context should describe the form/table/narrative context when clear. If unclear, use a generic context such as operation narrative, completion table, directional survey table, formation tops table, proposed plan, or unknown form.
- status_hint must be one of: actual, proposed, historical, uncertain, unknown.
- confidence must be one of: high, medium, low.
- Mark APD, permit plans, drilling plans, directional plans, revised plans, and contingency designs as proposed unless the source clearly reports actual execution.
- Mark completion reports, subsequent reports, actual operation narratives, final survey/control records, and operator-change/current operator records as actual when they report executed/current facts.
- Mark superseded real values as historical when the batch itself makes that clear.
- Use uncertain when the value is ambiguous, malformed, contradicted, or low-confidence.
- Preserve proposed values as facts; the later reducer will decide whether they belong in the current summary.
- Do not deduplicate aggressively inside the batch. If two facts differ in value, context, status, datum, or source ID, keep both.
- Do not invent missing values.
- If a source contains no relevant wellbore facts, return no facts for that source.
"""


def build_fact_scout_prompt(batch: SummaryBatch) -> str:
    manifest = "\n".join(f"- source_id: {page.source_id}" for page in batch.pages)
    page_blocks = []
    for page in batch.pages:
        page_blocks.append(
            "\n".join(
                [
                    f"===== BEGIN SOURCE {page.source_id} =====",
                    page.markdown,
                    f"===== END SOURCE {page.source_id} =====",
                ]
            )
        )
    return (
        FACT_SCOUT_INSTRUCTIONS
        + "\n\n"
        + f"Document ID: {batch.document_id}\n"
        + f"Batch ID: {batch.batch_id}\n\n"
        + "Source manifest:\n"
        + manifest
        + "\n\n"
        + "\n\n".join(page_blocks)
    )
```

- [ ] **Step 4: Run prompt test**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py::test_build_fact_scout_prompt_uses_source_manifest_and_boundaries -v
```

Expected: PASS.

- [ ] **Step 5: Run all summary tests and commit**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py -v
```

Expected: PASS.

Commit:

```bash
git add pdf_extract/wellbore_summary.py tests/test_wellbore_summary.py
git commit -m "Add wellbore fact scout prompt"
```

---

### Task 4: Run Batch Fact Scout And Write Fact Ledger

**Files:**
- Modify: `pdf_extract/wellbore_summary.py`
- Modify: `tests/test_wellbore_summary.py`

- [ ] **Step 1: Write failing tests for batch scout and ledger writing**

Append to `tests/test_wellbore_summary.py`:

```python
from pdf_extract.wellbore_summary import run_fact_scout_batches, write_fact_ledger


class FakeTextClient:
    model = "fake-text-model"

    def __init__(self, json_responses: list[dict] | None = None, text_response: str = ""):
        self.json_responses = list(json_responses or [])
        self.text_response = text_response
        self.json_calls: list[dict] = []
        self.text_calls: list[dict] = []

    def create_json(self, *, prompt: str, response_format: dict):
        self.json_calls.append({"prompt": prompt, "response_format": response_format})
        if not self.json_responses:
            raise AssertionError("Unexpected create_json call")
        return self.json_responses.pop(0)

    def create_text(self, *, prompt: str) -> str:
        self.text_calls.append({"prompt": prompt})
        return self.text_response


def test_run_fact_scout_batches_calls_client_with_batch_schema():
    page = ReconciledSummaryPage(
        document_id="doc",
        page=28,
        source_id="page_0028",
        markdown_key="key",
        markdown="5-1/2 casing",
    )
    batch = SummaryBatch(document_id="doc", batch_id="pages_0028_0028", pages=(page,))
    client = FakeTextClient(json_responses=[valid_payload()])

    results = run_fact_scout_batches((batch,), client=client)

    assert len(results) == 1
    assert results[0].facts[0].field == "production_casing"
    assert client.json_calls[0]["response_format"]["schema"]["properties"]["facts"]["items"]["properties"]["source_page_ids"]["items"]["enum"] == ["page_0028"]
    assert "===== BEGIN SOURCE page_0028 =====" in client.json_calls[0]["prompt"]


def test_write_fact_ledger_writes_one_json_object_per_batch(tmp_path):
    result = parse_batch_fact_result(
        payload=valid_payload(),
        document_id="doc",
        batch_id="pages_0028_0028",
        batch_pages=(28,),
        allowed_source_ids=("page_0028",),
        model="fake-model",
        prompt_version="wellbore-fact-scout-v1",
    )
    path = tmp_path / "fact_ledger.jsonl"

    write_fact_ledger(path, (result,))

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["batch_id"] == "pages_0028_0028"
    assert rows[0]["facts"][0]["source_page_ids"] == ["page_0028"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py::test_run_fact_scout_batches_calls_client_with_batch_schema tests/test_wellbore_summary.py::test_write_fact_ledger_writes_one_json_object_per_batch -v
```

Expected: FAIL with `ImportError` for `run_fact_scout_batches` and `write_fact_ledger`.

- [ ] **Step 3: Implement batch runner and ledger writer**

Add to `pdf_extract/wellbore_summary.py`:

```python
def run_fact_scout_batches(
    batches: Sequence[SummaryBatch],
    *,
    client: TextModelClient,
) -> tuple[BatchFactResult, ...]:
    results: list[BatchFactResult] = []
    for batch in batches:
        source_ids = tuple(page.source_id for page in batch.pages)
        payload = client.create_json(
            prompt=build_fact_scout_prompt(batch),
            response_format=build_fact_scout_response_format(source_ids),
        )
        results.append(
            parse_batch_fact_result(
                payload=payload,
                document_id=batch.document_id,
                batch_id=batch.batch_id,
                batch_pages=tuple(page.page for page in batch.pages),
                allowed_source_ids=source_ids,
                model=client.model,
                prompt_version=FACT_SCOUT_PROMPT_VERSION,
            )
        )
    return tuple(results)


def _fact_to_dict(fact: CandidateFact) -> dict[str, Any]:
    return {
        "section": fact.section,
        "field": fact.field,
        "value": fact.value,
        "source_page_ids": list(fact.source_page_ids),
        "source_context": fact.source_context,
        "source_snippet": fact.source_snippet,
        "status_hint": fact.status_hint,
        "confidence": fact.confidence,
        "notes": fact.notes,
    }


def batch_result_to_dict(result: BatchFactResult) -> dict[str, Any]:
    return {
        "document_id": result.document_id,
        "batch_id": result.batch_id,
        "batch_pages": list(result.batch_pages),
        "model": result.model,
        "prompt_version": result.prompt_version,
        "facts": [_fact_to_dict(fact) for fact in result.facts],
        "warnings": list(result.warnings),
    }


def write_fact_ledger(path: Path, results: Sequence[BatchFactResult]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(batch_result_to_dict(result), ensure_ascii=False, sort_keys=True)
        for result in results
    ]
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path
```

- [ ] **Step 4: Run batch runner tests**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add pdf_extract/wellbore_summary.py tests/test_wellbore_summary.py
git commit -m "Add fact scout batch runner"
```

---

### Task 5: Add Dedupe, Source Display Mapping, And Reducer Prompt

**Files:**
- Modify: `pdf_extract/wellbore_summary.py`
- Modify: `tests/test_wellbore_summary.py`

- [ ] **Step 1: Write failing reducer helper tests**

Append to `tests/test_wellbore_summary.py`:

```python
from pdf_extract.wellbore_summary import (
    build_reducer_prompt,
    dedupe_candidate_facts,
    display_pages_for_fact,
)


def make_fact(**overrides) -> CandidateFact:
    data = {
        "section": "elevations",
        "field": "ground_level_elevation",
        "value": "3172'GR",
        "source_page_ids": ("page_0010",),
        "source_context": "C-103 subsequent report header",
        "source_snippet": "3172'GR",
        "status_hint": "actual",
        "confidence": "high",
        "notes": "Repeated GR elevation.",
    }
    data.update(overrides)
    return CandidateFact(**data)


def test_display_pages_for_fact_maps_source_ids_to_numbers():
    fact = make_fact(source_page_ids=("page_0028", "page_0030"))

    assert display_pages_for_fact(fact) == "28, 30"


def test_dedupe_candidate_facts_merges_duplicate_overlap_pages():
    first = make_fact(source_page_ids=("page_0010",), notes="First copy.")
    second = make_fact(source_page_ids=("page_0010", "page_0011"), notes="Second copy.")

    merged = dedupe_candidate_facts((first, second))

    assert len(merged) == 1
    assert merged[0].source_page_ids == ("page_0010", "page_0011")
    assert "First copy." in merged[0].notes
    assert "Second copy." in merged[0].notes


def test_dedupe_candidate_facts_keeps_different_status_separate():
    actual = make_fact(status_hint="actual")
    proposed = make_fact(status_hint="proposed")

    merged = dedupe_candidate_facts((actual, proposed))

    assert len(merged) == 2


def test_build_reducer_prompt_contains_display_pages_not_source_ids():
    facts = (make_fact(source_page_ids=("page_0028",)),)

    prompt = build_reducer_prompt(facts, document_id="doc")

    assert "Source PDF Page" in prompt
    assert "Display source pages: 28" in prompt
    assert "page_0028" in prompt
    assert "Do not mention batches, prompts, fact IDs, or model behavior." in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py::test_display_pages_for_fact_maps_source_ids_to_numbers tests/test_wellbore_summary.py::test_dedupe_candidate_facts_merges_duplicate_overlap_pages tests/test_wellbore_summary.py::test_build_reducer_prompt_contains_display_pages_not_source_ids -v
```

Expected: FAIL with missing helper imports.

- [ ] **Step 3: Implement dedupe and reducer prompt**

Add to `pdf_extract/wellbore_summary.py`:

```python
def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().replace(",", ""))


def _dedupe_key(fact: CandidateFact) -> tuple[str, str, str, str, str]:
    return (
        fact.section,
        _normalize_text(fact.field),
        _normalize_text(fact.value),
        fact.status_hint,
        _normalize_text(fact.source_context),
    )


def dedupe_candidate_facts(facts: Sequence[CandidateFact]) -> tuple[CandidateFact, ...]:
    merged: dict[tuple[str, str, str, str, str], CandidateFact] = {}
    for fact in facts:
        key = _dedupe_key(fact)
        existing = merged.get(key)
        if existing is None:
            merged[key] = fact
            continue
        source_page_ids = tuple(sorted(set(existing.source_page_ids) | set(fact.source_page_ids)))
        snippets = tuple(dict.fromkeys((existing.source_snippet, fact.source_snippet)))
        notes = tuple(dict.fromkeys((existing.notes, fact.notes)))
        merged[key] = CandidateFact(
            section=existing.section,
            field=existing.field,
            value=existing.value,
            source_page_ids=source_page_ids,
            source_context=existing.source_context,
            source_snippet=" | ".join(snippets),
            status_hint=existing.status_hint,
            confidence=existing.confidence if existing.confidence == "high" else fact.confidence,
            notes=" | ".join(notes),
        )
    return tuple(merged.values())


def display_pages_for_fact(fact: CandidateFact) -> str:
    pages = sorted(page_number_from_source_id(source_id) for source_id in fact.source_page_ids)
    return ", ".join(str(page) for page in pages)


REDUCER_INSTRUCTIONS = """You are creating a current wellbore data summary from extracted candidate facts.

Use only the provided fact ledger. Do not use outside knowledge. Do not guess.

Write a Markdown report shaped like:

### Well Identity
| Field | Value | Source PDF Page | Notes |

### Elevations
...

Use these sections:
- Well Identity
- Elevations
- Operation Timeline
- Hole Sections
- Casing And Tubing Strings
- Downhole Items And Reference Depths
- Cement Jobs
- Plugs
- Perforations And Treatments
- Directional And Lateral Details
- Formation Tops
- Consolidated Conflicts And Uncertain Data

Current-value rules:
- Prefer actual facts over proposed facts.
- Use proposed facts only when no actual/current fact exists, and clearly label them as proposed.
- Preserve important proposed-vs-actual differences in conflicts/uncertain data when they explain why a value was not selected.
- Collapse repeated duplicate values into one row with combined source pages.
- Keep same-looking values separate when they have different datum, context, status, or meaning.
- Later/current operator-change facts can supersede earlier operator facts.
- Completion reports and actual operation reports generally beat APD/proposed plan values.
- Survey report "Date Completed" values should not become well completion dates unless the fact specifically says it is the well completion/ready-to-produce date.
- If facts conflict and no clear current value can be selected, keep the conflict in Consolidated Conflicts And Uncertain Data.
- Every selected value must cite source PDF page(s).
- Notes should explain why the value was selected, merged, or kept separate.
- Do not include raw fact IDs.
- Do not mention batches, prompts, fact IDs, or model behavior.
"""


def build_reducer_prompt(facts: Sequence[CandidateFact], *, document_id: str) -> str:
    lines = [REDUCER_INSTRUCTIONS, "", f"Document ID: {document_id}", "", "Candidate facts:"]
    for index, fact in enumerate(facts, start=1):
        lines.extend(
            [
                f"{index}. section: {fact.section}",
                f"   field: {fact.field}",
                f"   value: {fact.value}",
                f"   source_page_ids: {', '.join(fact.source_page_ids)}",
                f"   Display source pages: {display_pages_for_fact(fact)}",
                f"   source_context: {fact.source_context}",
                f"   source_snippet: {fact.source_snippet}",
                f"   status_hint: {fact.status_hint}",
                f"   confidence: {fact.confidence}",
                f"   notes: {fact.notes}",
            ]
        )
    return "\n".join(lines)
```

- [ ] **Step 4: Run reducer helper tests**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```bash
git add pdf_extract/wellbore_summary.py tests/test_wellbore_summary.py
git commit -m "Add wellbore summary reducer prompt"
```

---

### Task 6: Add OpenAI Text Client And Summary Orchestrator

**Files:**
- Modify: `pdf_extract/wellbore_summary.py`
- Modify: `tests/test_wellbore_summary.py`

- [ ] **Step 1: Write failing orchestrator tests**

Append to `tests/test_wellbore_summary.py`:

```python
from pdf_extract.wellbore_summary import OpenAIResponsesTextClient, run_wellbore_summary


def test_run_wellbore_summary_writes_ledger_and_summary(tmp_path):
    object_store = tmp_path / "object_store"
    write_reconciled_page(object_store, "doc", 1, "C-105 completion report 5-1/2 casing")
    write_reconciled_page(object_store, "doc", 2, "Formation tops table")
    client = FakeTextClient(
        json_responses=[
            {
                "facts": [
                    {
                        "section": "casing_and_tubing_strings",
                        "field": "production_casing",
                        "value": "5-1/2 casing set at 10,490 ft",
                        "source_page_ids": ["page_0001"],
                        "source_context": "C-105 completion report casing table",
                        "source_snippet": "5-1/2 casing ... 10,490",
                        "status_hint": "actual",
                        "confidence": "high",
                        "notes": "Actual completion casing.",
                    }
                ],
                "warnings": [],
            }
        ],
        text_response="### Casing And Tubing Strings\n\n| Diameter | Setting Depth | Source PDF Page | Notes |\n| --- | --- | --- | --- |\n| 5-1/2 in | 10,490 ft | 1 | Actual completion casing. |\n",
    )

    result = run_wellbore_summary(
        object_store_root=object_store,
        document_id="doc",
        out_dir=tmp_path / "summary",
        client=client,
    )

    assert Path(result["fact_ledger_path"]).is_file()
    assert Path(result["summary_path"]).read_text(encoding="utf-8").startswith("### Casing")
    assert result["batch_count"] == 1
    assert result["fact_count"] == 1
    assert len(client.json_calls) == 1
    assert len(client.text_calls) == 1


def test_openai_responses_text_client_uses_json_schema_and_text_calls():
    class FakeResponses:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            if "text" in kwargs:
                return type("Response", (), {"output_text": json.dumps({"facts": [], "warnings": []})})()
            return type("Response", (), {"output_text": "### Summary\n"})()

    class FakeSDK:
        def __init__(self):
            self.responses = FakeResponses()

    sdk = FakeSDK()
    client = OpenAIResponsesTextClient(model="fake-openai", sdk_client=sdk)

    payload = client.create_json(prompt="extract", response_format=build_fact_scout_response_format(("page_0001",)))
    text = client.create_text(prompt="reduce")

    assert payload == {"facts": [], "warnings": []}
    assert text == "### Summary\n"
    assert sdk.responses.calls[0]["text"]["format"]["name"] == "wellbore_batch_fact_result"
    assert sdk.responses.calls[1]["input"][0]["content"][0]["text"] == "reduce"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py::test_run_wellbore_summary_writes_ledger_and_summary tests/test_wellbore_summary.py::test_openai_responses_text_client_uses_json_schema_and_text_calls -v
```

Expected: FAIL with missing `run_wellbore_summary` and `OpenAIResponsesTextClient`.

- [ ] **Step 3: Implement client and orchestrator**

Add to `pdf_extract/wellbore_summary.py`:

```python
class OpenAIResponsesTextClient:
    def __init__(
        self,
        *,
        model: str = DEFAULT_FACT_SCOUT_MODEL,
        api_key_env: str = "OPENAI_API_KEY",
        sdk_client: Any | None = None,
    ):
        self.model = model
        if sdk_client is not None:
            self._client = sdk_client
            return
        import os

        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise RuntimeError(f"{api_key_env} is required for OpenAI summary extraction")
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)

    def create_json(self, *, prompt: str, response_format: dict[str, Any]) -> Mapping[str, Any]:
        response = self._client.responses.create(
            model=self.model,
            input=[{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            text={"format": response_format},
        )
        return json.loads(response.output_text)

    def create_text(self, *, prompt: str) -> str:
        response = self._client.responses.create(
            model=self.model,
            input=[{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        )
        return response.output_text


def run_wellbore_summary(
    *,
    object_store_root: Path,
    document_id: str,
    out_dir: Path,
    client: TextModelClient,
    batch_size: int = 10,
    overlap: int = 1,
) -> dict[str, Any]:
    pages = discover_reconciled_summary_pages(
        object_store_root=object_store_root,
        document_id=document_id,
    )
    batches = build_summary_batches(pages, batch_size=batch_size, overlap=overlap)
    batch_results = run_fact_scout_batches(batches, client=client)
    ledger_path = write_fact_ledger(out_dir / "fact_ledger.jsonl", batch_results)

    facts = dedupe_candidate_facts(
        tuple(fact for result in batch_results for fact in result.facts)
    )
    summary_markdown = client.create_text(
        prompt=build_reducer_prompt(facts, document_id=document_id)
    )
    summary_path = out_dir / "combined_summary_current.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary_markdown, encoding="utf-8")

    return {
        "document_id": document_id,
        "page_count": len(pages),
        "batch_count": len(batches),
        "fact_count": len(facts),
        "fact_ledger_path": ledger_path.as_posix(),
        "summary_path": summary_path.as_posix(),
    }
```

- [ ] **Step 4: Run orchestrator tests**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 6**

```bash
git add pdf_extract/wellbore_summary.py tests/test_wellbore_summary.py
git commit -m "Add wellbore summary orchestrator"
```

---

### Task 7: Add CLI Wrapper

**Files:**
- Create: `scripts/run_wellbore_summary.py`
- Modify: `tests/test_wellbore_summary.py`

- [ ] **Step 1: Write failing CLI script tests**

Append to `tests/test_wellbore_summary.py`:

```python
import runpy


def load_run_wellbore_summary_script() -> dict[str, object]:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_wellbore_summary.py"
    return runpy.run_path(str(script_path), run_name="run_wellbore_summary_test")


def test_run_wellbore_summary_parse_args_defaults():
    script = load_run_wellbore_summary_script()
    parser = script["create_arg_parser"]()

    args = parser.parse_args(["--document-id", "doc"])

    assert args.document_id == "doc"
    assert args.object_store_root == Path("object_store")
    assert args.out_dir == Path("summary_runs/doc")
    assert args.provider == "openai"


def test_run_wellbore_summary_dry_run_client_returns_empty_summary():
    script = load_run_wellbore_summary_script()
    client = script["create_client"](provider="dry-run", model="fake")

    assert client.model == "dry-run-no-llm"
    assert client.create_json(prompt="anything", response_format={}) == {"facts": [], "warnings": ["dry-run summary client did not call a model"]}
    assert client.create_text(prompt="anything").startswith("<!-- dry-run reducer")
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py::test_run_wellbore_summary_parse_args_defaults tests/test_wellbore_summary.py::test_run_wellbore_summary_dry_run_client_returns_empty_summary -v
```

Expected: FAIL with `FileNotFoundError` for `scripts/run_wellbore_summary.py`.

- [ ] **Step 3: Create CLI wrapper**

Create `scripts/run_wellbore_summary.py`:

```python
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from pdf_extract.wellbore_summary import (
    DEFAULT_FACT_SCOUT_MODEL,
    OpenAIResponsesTextClient,
    run_wellbore_summary,
)


class DryRunSummaryClient:
    model = "dry-run-no-llm"

    def create_json(self, *, prompt: str, response_format: dict[str, Any]) -> dict[str, Any]:
        return {
            "facts": [],
            "warnings": ["dry-run summary client did not call a model"],
        }

    def create_text(self, *, prompt: str) -> str:
        return "<!-- dry-run reducer did not call a model -->\n"


def load_openai_api_key_from_repo_env(repo_root: Path) -> bool:
    if os.environ.get("OPENAI_API_KEY"):
        return False
    env_path = repo_root / ".env"
    if not env_path.is_file():
        return False
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "OPENAI_API_KEY":
            continue
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if value:
            os.environ["OPENAI_API_KEY"] = value
            return True
    return False


def create_client(*, provider: str, model: str | None):
    if provider == "dry-run":
        return DryRunSummaryClient()
    if provider == "openai":
        return OpenAIResponsesTextClient(
            model=model or os.environ.get("OPENAI_SUMMARY_MODEL", DEFAULT_FACT_SCOUT_MODEL)
        )
    raise ValueError(f"Unsupported provider: {provider}")


def create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a current wellbore data summary from reconciled page Markdown."
    )
    parser.add_argument("--document-id", required=True, help="Document ID under the reconciled object store.")
    parser.add_argument(
        "--object-store-root",
        type=Path,
        default=Path("object_store"),
        help="Local object-store root containing pdf-extract/reconciled/<document-id>.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to summary_runs/<document-id>.",
    )
    parser.add_argument(
        "--provider",
        choices=("openai", "dry-run"),
        default="openai",
        help="Use dry-run to validate file flow without model calls.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENAI_SUMMARY_MODEL", DEFAULT_FACT_SCOUT_MODEL),
        help="OpenAI model for fact scouting and reduction.",
    )
    parser.add_argument("--batch-size", type=int, default=10, help="Pages per fact-scout batch.")
    parser.add_argument("--overlap", type=int, default=1, help="Pages repeated between adjacent batches.")
    return parser


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    load_openai_api_key_from_repo_env(repo_root)
    parser = create_arg_parser()
    args = parser.parse_args()
    out_dir = args.out_dir or Path("summary_runs") / args.document_id
    result = run_wellbore_summary(
        object_store_root=args.object_store_root,
        document_id=args.document_id,
        out_dir=out_dir,
        client=create_client(provider=args.provider, model=args.model),
        batch_size=args.batch_size,
        overlap=args.overlap,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 7**

```bash
git add scripts/run_wellbore_summary.py tests/test_wellbore_summary.py
git commit -m "Add wellbore summary CLI"
```

---

### Task 8: Add README Usage And Run Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add README usage section**

Insert this section after the existing "Page OCR Reconciliation" section:

```markdown
## Wellbore Current Summary

After page reconciliation has published reconciled page Markdown, generate a
current wellbore data summary from the reconciled Markdown:

```bash
uv run python scripts/run_wellbore_summary.py \
  --document-id Full_30015375000000 \
  --object-store-root object_store \
  --out-dir summary_runs/Full_30015375000000 \
  --provider openai
```

The summary pipeline writes:

```text
summary_runs/<document_id>/
  fact_ledger.jsonl
  combined_summary_current.md
```

For local file-flow validation without model calls:

```bash
uv run python scripts/run_wellbore_summary.py \
  --document-id Full_30015375000000 \
  --object-store-root object_store \
  --out-dir summary_runs/Full_30015375000000_dry_run \
  --provider dry-run
```

V1 uses reconciled Markdown only. It does not send PDF page images to the model.
Fact citations use internal source IDs such as `page_0028`; the renderer maps
those IDs back to display page numbers in `combined_summary_current.md`.
```
```

- [ ] **Step 2: Run targeted summary tests**

Run:

```bash
uv run --with pytest python -m pytest tests/test_wellbore_summary.py -v
```

Expected: all tests PASS.

- [ ] **Step 3: Run full test suite**

Run:

```bash
uv run --with pytest python -m pytest -v
```

Expected: all tests PASS.

- [ ] **Step 4: Run dry-run CLI against available reconciled sample if present**

Run:

```bash
uv run python scripts/run_wellbore_summary.py \
  --document-id Full_30015375000000 \
  --object-store-root object_store_eval_20_html_tables_strict \
  --out-dir /tmp/pdf-extract-summary-dry-run \
  --provider dry-run
```

Expected:

```text
{
  "document_id": "Full_30015375000000",
  "page_count": 20,
  "batch_count": 3,
  "fact_count": 0,
  "fact_ledger_path": "/tmp/pdf-extract-summary-dry-run/fact_ledger.jsonl",
  "summary_path": "/tmp/pdf-extract-summary-dry-run/combined_summary_current.md"
}
```

If that object-store directory is absent in the executor's workspace, skip this command and record: `Skipped sample dry-run because object_store_eval_20_html_tables_strict was absent.`

- [ ] **Step 5: Commit Task 8**

```bash
git add README.md
git commit -m "Document wellbore summary pipeline"
```

---

## Final Verification Checklist

- [ ] `uv run --with pytest python -m pytest tests/test_wellbore_summary.py -v` passes.
- [ ] `uv run --with pytest python -m pytest -v` passes.
- [ ] Dry-run CLI writes `fact_ledger.jsonl` and `combined_summary_current.md` when sample reconciled pages exist.
- [ ] No page-image input is sent by the summary pipeline.
- [ ] Fact scout schema uses `source_page_ids` with a per-batch enum.
- [ ] Final summary rendering maps source IDs to display page numbers through code-owned parsing.
