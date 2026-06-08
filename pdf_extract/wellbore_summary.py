from __future__ import annotations

import json
import re
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
STATUS_HINTS: tuple[str, ...] = (
    "actual",
    "proposed",
    "historical",
    "uncertain",
    "unknown",
)
CONFIDENCE_LEVELS: tuple[str, ...] = ("high", "medium", "low")
DEFAULT_FACT_SCOUT_MODEL = "gpt-5.4-mini"
FACT_SCOUT_PROMPT_VERSION = "wellbore-fact-scout-v1"
REDUCER_PROMPT_VERSION = "wellbore-current-reducer-v1"
_SOURCE_ID_RE = re.compile(r"^page_(\d{4,})$")


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

    def create_json(self, *, prompt: str, response_format: dict[str, Any]) -> Mapping[str, Any]:
        ...

    def create_text(self, *, prompt: str) -> str:
        ...


def source_id_for_page(page: int) -> str:
    if page < 1:
        raise ValueError("page must be >= 1")
    return f"page_{page:04d}"


def page_number_from_source_id(source_id: str) -> int:
    match = _SOURCE_ID_RE.match(source_id)
    if not match:
        raise ValueError(f"Invalid source_id: {source_id}")
    page = int(match.group(1))
    if page < 1:
        raise ValueError(f"Invalid source_id: {source_id}")
    return page


def _page_number_from_page_dir(path: Path) -> int | None:
    try:
        return page_number_from_source_id(path.name)
    except ValueError:
        return None


def discover_reconciled_summary_pages(
    object_store_root: Path,
    document_id: str,
) -> tuple[ReconciledSummaryPage, ...]:
    pages_root = object_store_root / "pdf-extract" / "reconciled" / document_id / "pages"
    if not pages_root.is_dir():
        raise FileNotFoundError(f"Missing reconciled pages directory: {pages_root}")

    pages: list[ReconciledSummaryPage] = []
    for page_dir in pages_root.iterdir():
        page = _page_number_from_page_dir(page_dir)
        if page is None:
            continue
        output_path = page_dir / "output.md"
        if not output_path.is_file():
            continue

        decision_path = page_dir / "decision.json"
        needs_human_review = False
        if decision_path.is_file():
            decision = json.loads(decision_path.read_text(encoding="utf-8"))
            if isinstance(decision, Mapping):
                needs_human_review = decision.get("needs_human_review") is True

        pages.append(
            ReconciledSummaryPage(
                document_id=document_id,
                page=page,
                source_id=source_id_for_page(page),
                markdown_key=output_path.relative_to(object_store_root).as_posix(),
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
                            "section": {
                                "type": "string",
                                "enum": list(SUMMARY_SECTIONS),
                            },
                            "field": {"type": "string"},
                            "value": {"type": "string"},
                            "source_page_ids": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "string",
                                    "enum": source_id_enum,
                                },
                            },
                            "source_context": {"type": "string"},
                            "source_snippet": {"type": "string"},
                            "status_hint": {
                                "type": "string",
                                "enum": list(STATUS_HINTS),
                            },
                            "confidence": {
                                "type": "string",
                                "enum": list(CONFIDENCE_LEVELS),
                            },
                            "notes": {"type": "string"},
                        },
                    },
                },
                "warnings": {
                    "type": "array",
                    "items": {"type": "string"},
                },
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
    if not isinstance(payload, Mapping):
        raise ValueError("fact must be an object")

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
    outside_manifest = [
        source_id for source_id in source_page_ids if source_id not in allowed_source_ids
    ]
    if outside_manifest:
        raise ValueError(
            f"source_page_ids outside batch source manifest: {outside_manifest}"
        )

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
    if not isinstance(raw_warnings, list) or not all(
        isinstance(item, str) for item in raw_warnings
    ):
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
