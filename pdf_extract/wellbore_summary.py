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


FACT_SCOUT_INSTRUCTIONS = """You are extracting wellbore-diagram/current-data candidate facts from reconciled PDF Markdown.

You receive a batch of PDF page sources. Each source has a system-provided source_id such as `page_0028`. Use source IDs for citations. Use only the provided Markdown. Do not use outside knowledge. Do not guess.

Important source citation rule:
- Every fact must cite source_page_ids from the provided source manifest.
- Use source IDs exactly; use source_id values such as page_0028.
- Do not cite batch positions or the page's position inside this batch.
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


def display_pages_for_fact(fact: CandidateFact) -> str:
    pages = sorted(
        page_number_from_source_id(source_id)
        for source_id in fact.source_page_ids
    )
    return ", ".join(str(page) for page in pages)


def _page_number_from_page_dir(path: Path) -> int | None:
    try:
        return page_number_from_source_id(path.name)
    except ValueError:
        return None


def _needs_human_review_from_decision(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        decision = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    if not isinstance(decision, Mapping):
        return False
    return decision.get("needs_human_review") is True


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
        needs_human_review = _needs_human_review_from_decision(decision_path)

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


def build_fact_scout_prompt(batch: SummaryBatch) -> str:
    manifest = "\n".join(f"- source_id: {page.source_id}" for page in batch.pages)
    source_blocks = []
    for page in batch.pages:
        source_blocks.append(
            "\n".join(
                (
                    f"===== BEGIN SOURCE {page.source_id} =====",
                    page.markdown,
                    f"===== END SOURCE {page.source_id} =====",
                )
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
        + "\n\n".join(source_blocks)
    )


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


def run_fact_scout_batches(
    batches: Sequence[SummaryBatch],
    *,
    client: TextModelClient,
) -> tuple[BatchFactResult, ...]:
    return tuple(_run_fact_scout_batch(batch, client=client) for batch in batches)


def _run_fact_scout_batch(
    batch: SummaryBatch,
    *,
    client: TextModelClient,
) -> BatchFactResult:
    source_ids = tuple(page.source_id for page in batch.pages)
    payload = client.create_json(
        prompt=build_fact_scout_prompt(batch),
        response_format=build_fact_scout_response_format(source_ids),
    )
    return parse_batch_fact_result(
        payload=payload,
        document_id=batch.document_id,
        batch_id=batch.batch_id,
        batch_pages=tuple(page.page for page in batch.pages),
        allowed_source_ids=source_ids,
        model=client.model,
        prompt_version=FACT_SCOUT_PROMPT_VERSION,
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().replace(",", ""))


def _format_decimal(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _normalize_api_number(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if len(digits) == 14 and digits.endswith("0000"):
        digits = digits[:10]
    if len(digits) == 10:
        return f"api:{digits}"
    if len(digits) == 14:
        return f"api:{digits}"
    return None


def _normalize_date(value: str) -> str | None:
    text = value.strip()
    iso_match = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if iso_match:
        year, month, day = (int(part) for part in iso_match.groups())
    else:
        slash_match = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})", text)
        if not slash_match:
            return None
        month, day = (int(part) for part in slash_match.groups()[:2])
        raw_year = slash_match.group(3)
        year = int(raw_year)
        if len(raw_year) == 2:
            year += 2000 if year <= 68 else 1900

    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"date:{year:04d}-{month:02d}-{day:02d}"


def _normalize_depth(value: str) -> str | None:
    text = value.strip().lower().replace(",", "")
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:'|ft|feet)", text)
    if not match:
        return None
    return f"depth:{_format_decimal(float(match.group(1)))}"


def _normalize_size(value: str) -> str | None:
    text = value.strip().lower()
    mixed_match = re.fullmatch(
        r"(\d+)\s*[- ]\s*(\d+)\s*/\s*(\d+)\s*(?:\"|in|inch|inches)?",
        text,
    )
    if mixed_match:
        whole, numerator, denominator = (int(part) for part in mixed_match.groups())
        if denominator == 0:
            return None
        return f"size:{_format_decimal(whole + numerator / denominator)}"

    decimal_match = re.fullmatch(
        r"(\d+(?:\.\d+)?)\s*(?:\"|in|inch|inches)?",
        text,
    )
    if decimal_match:
        return f"size:{_format_decimal(float(decimal_match.group(1)))}"
    return None


def _normalize_value(field: str, value: str) -> str:
    normalized_field = _normalize_text(field)
    if "api" in normalized_field:
        normalized_api = _normalize_api_number(value)
        if normalized_api is not None:
            return normalized_api

    if "date" in normalized_field:
        normalized_date = _normalize_date(value)
        if normalized_date is not None:
            return normalized_date

    if "depth" in normalized_field:
        normalized_depth = _normalize_depth(value)
        if normalized_depth is not None:
            return normalized_depth

    if "size" in normalized_field or "diameter" in normalized_field:
        normalized_size = _normalize_size(value)
        if normalized_size is not None:
            return normalized_size

    return _normalize_text(value)


def _dedupe_key(fact: CandidateFact) -> tuple[str, str, str, str, str]:
    return (
        fact.section,
        _normalize_text(fact.field),
        _normalize_value(fact.field, fact.value),
        fact.status_hint,
        _normalize_text(fact.source_context),
    )


def _join_unique(values: Sequence[str]) -> str:
    return " | ".join(dict.fromkeys(values))


def _highest_confidence(first: str, second: str) -> str:
    rank = {"low": 0, "medium": 1, "high": 2}
    return first if rank[first] >= rank[second] else second


def dedupe_candidate_facts(
    facts: Sequence[CandidateFact],
) -> tuple[CandidateFact, ...]:
    merged: dict[tuple[str, str, str, str, str], CandidateFact] = {}
    for fact in facts:
        key = _dedupe_key(fact)
        existing = merged.get(key)
        if existing is None:
            merged[key] = fact
            continue

        merged[key] = CandidateFact(
            section=existing.section,
            field=existing.field,
            value=existing.value,
            source_page_ids=tuple(
                sorted(
                    set(existing.source_page_ids) | set(fact.source_page_ids),
                    key=page_number_from_source_id,
                )
            ),
            source_context=existing.source_context,
            source_snippet=_join_unique(
                (existing.source_snippet, fact.source_snippet)
            ),
            status_hint=existing.status_hint,
            confidence=_highest_confidence(existing.confidence, fact.confidence),
            notes=_join_unique((existing.notes, fact.notes)),
        )
    return tuple(merged.values())


def build_reducer_prompt(
    facts: Sequence[CandidateFact],
    *,
    document_id: str,
) -> str:
    lines = [
        REDUCER_INSTRUCTIONS,
        "",
        f"Document ID: {document_id}",
        "",
        "Candidate facts:",
    ]
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


def write_fact_ledger(
    path: Path,
    results: Sequence[BatchFactResult],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps(batch_result_to_dict(result), ensure_ascii=False, sort_keys=True)
        for result in results
    ]
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
    return path


class OpenAIResponsesTextClient:
    def __init__(
        self,
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
            raise RuntimeError(
                f"{api_key_env} is required for OpenAI summary extraction"
            )

        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)

    def create_json(
        self,
        *,
        prompt: str,
        response_format: dict[str, Any],
    ) -> Mapping[str, Any]:
        response = self._client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                }
            ],
            text={"format": response_format},
        )
        return json.loads(response.output_text)

    def create_text(self, *, prompt: str) -> str:
        response = self._client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                }
            ],
        )
        return response.output_text


def run_wellbore_summary(
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
    batches = build_summary_batches(
        pages,
        batch_size=batch_size,
        overlap=overlap,
    )
    batch_results: list[BatchFactResult] = []
    failed_batches: list[dict[str, str]] = []
    for batch in batches:
        try:
            batch_results.append(_run_fact_scout_batch(batch, client=client))
        except ValueError as error:
            failed_batches.append(
                {
                    "batch_id": batch.batch_id,
                    "error": str(error),
                }
            )
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
        "failed_batches": failed_batches,
        "fact_ledger_path": ledger_path.as_posix(),
        "summary_path": summary_path.as_posix(),
    }
