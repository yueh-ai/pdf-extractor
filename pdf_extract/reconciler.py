from __future__ import annotations

import base64
import json
import mimetypes
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from .reconciled_store import (
    PUBLISHED,
    LocalObjectStore,
    PageCatalog,
    PageReconciliationResult,
    ReconciledPagePublisher,
    assemble_document,
    iter_markdown_image_refs,
    resolve_asset_path,
    rewrite_markdown_image_refs,
    sha256_text,
)
from .reconciled_viewer import write_viewer_manifest
from .render import page_dir_name


DEFAULT_RECONCILE_MODEL = "gpt-5.4-mini"
DEFAULT_RECONCILE_PROMPT_VERSION = "reconcile-page-v5"
DEFAULT_IMAGE_DETAIL = "high"
OPENAI_PRICING_CAPTURED_AT = "2026-06-08"
OPENAI_PRICING_SOURCE = "https://openai.com/api/pricing/"
OPENAI_MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-5.4-mini": {
        "input_per_1m": 0.75,
        "cached_input_per_1m": 0.075,
        "output_per_1m": 4.5,
    }
}

VALID_WINNERS = {"union", "small", "mixed", "uncertain"}

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
            "winner": {"type": "string", "enum": sorted(VALID_WINNERS)},
            "warnings": {"type": "array", "items": {"type": "string"}},
            "needs_human_review": {"type": "boolean"},
        },
    },
}


@dataclass(frozen=True)
class PageReconcileInputs:
    document_id: str
    page: int
    page_image_path: Path
    union_markdown_path: Path
    small_markdown_path: Path
    union_markdown: str
    small_markdown: str


@dataclass(frozen=True)
class ModelReconcileResponse:
    reconciled_markdown: str
    winner: str
    warnings: tuple[str, ...]
    needs_human_review: bool

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ModelReconcileResponse":
        required = (
            "reconciled_markdown",
            "winner",
            "warnings",
            "needs_human_review",
        )
        missing = [field for field in required if field not in payload]
        if missing:
            raise ValueError(f"Model response missing required fields: {', '.join(missing)}")

        reconciled_markdown = payload["reconciled_markdown"]
        winner = payload["winner"]
        warnings = payload["warnings"]
        needs_human_review = payload["needs_human_review"]

        if not isinstance(reconciled_markdown, str):
            raise ValueError("Model response field reconciled_markdown must be a string")
        if winner not in VALID_WINNERS:
            raise ValueError(f"Model response field winner must be one of {sorted(VALID_WINNERS)}")
        if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
            raise ValueError("Model response field warnings must be a list[str]")
        if not isinstance(needs_human_review, bool):
            raise ValueError("Model response field needs_human_review must be a bool")

        return cls(
            reconciled_markdown=reconciled_markdown,
            winner=winner,
            warnings=tuple(warnings),
            needs_human_review=needs_human_review,
        )


@dataclass(frozen=True)
class ModelCallResult:
    payload: Mapping[str, Any]
    call_metadata: Mapping[str, Any] = field(default_factory=dict)


class VisionModelClient(Protocol):
    model: str

    def reconcile(self, *, image_path: Path, prompt: str) -> dict[str, Any] | ModelCallResult:
        ...


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

    union_image_path = union_page_dir / "page.png"
    small_image_path = small_page_dir / "page.png"
    if union_image_path.is_file():
        page_image_path = union_image_path
    elif small_image_path.is_file():
        page_image_path = small_image_path
    else:
        raise FileNotFoundError(f"Missing page image: {union_image_path} or {small_image_path}")

    return PageReconcileInputs(
        document_id=run_root.name,
        page=page,
        page_image_path=page_image_path,
        union_markdown_path=union_markdown_path,
        small_markdown_path=small_markdown_path,
        union_markdown=union_markdown_path.read_text(encoding="utf-8"),
        small_markdown=small_markdown_path.read_text(encoding="utf-8"),
    )


def build_reconcile_prompt(inputs: PageReconcileInputs) -> str:
    return (
        "You are reconciling OCR drafts for a single PDF page.\n\n"
        "Use the page image as the authoritative source of truth. Treat the two "
        "Markdown drafts as fallible hints.\n\n"
        "Goals:\n"
        "- Produce clean Markdown for this one page only.\n"
        "- Preserve visible text, headings, lists, tables, checkbox states, symbols, "
        "footnotes, and image references when they are supported by the page.\n"
        "- Table rules:\n"
        "  - Prefer GFM pipe tables for simple rectangular data tables.\n"
        "  - Every GFM table row must have the same number of cells as the separator row.\n"
        "  - Use raw HTML <table> markup only when the visible table needs structure "
        "that GFM cannot represent, such as merged cells, nested headers, rowspan, "
        "colspan, or irregular form layout.\n"
        "  - If an OCR draft contains raw HTML but the visible table is simple and "
        "rectangular, convert it to a clean GFM pipe table.\n"
        "  - If an OCR draft contains a GFM pipe table but the visible table has "
        "merged or irregular cells, convert it to raw HTML <table>.\n"
        "  - If either OCR draft contains a raw HTML <table> for a real merged or "
        "irregular table, preserve raw HTML <table> markup in reconciled_markdown.\n"
        "  - Do not preserve OCR table markup blindly. The page image decides whether "
        "something is a real table.\n"
        "- Chart, plot, and graphic rules:\n"
        "  - Do not convert charts, plots, graph grids, map grids, logos, stamps, "
        "signatures, or decorative/axis marks into tables.\n"
        "  - If OCR drafts contain long repeated-character runs, such as "
        "\"0000000000\", \"||||||||\", \"--------\", or similar noise, remove them "
        "unless the page image clearly shows those characters as real text.\n"
        "  - For chart or plot regions, preserve meaningful visible labels when "
        "readable, and keep supported image references instead of inventing tabular "
        "data from the graphic.\n"
        "  - If a chart/plot region is hard to read, add a warning and set "
        "needs_human_review=true.\n"
        "- Keep relative image references only when they are present in the drafts "
        "and still match visible image content on the page.\n"
        "- Do not invent content that is not visible in the image or reasonably "
        "supported by the drafts.\n"
        "- Review routing policy:\n"
        "  - Set needs_human_review=true in round one when this page should not "
        "be accepted without verification.\n"
        "  - Narrow high-risk structures: dense technical numeric tables including "
        "casing, tubing, cement, formation tops, lithology, directional survey, "
        "directional targets, and coordinate tables.\n"
        "  - Narrow high-risk structures also include well and land location "
        "descriptions: latitude, longitude, +N/-S offsets, +E/-W offsets, "
        "section-township-range, surface hole location, and bottom-hole location.\n"
        "  - Checkbox groups where the checked or unchecked state changes meaning "
        "are high-risk.\n"
        "  - Handwritten or crossed-out corrections that change typed values are "
        "high-risk.\n"
        "  - Maps, plots, or diagrams with meaningful labels, markers, paths, "
        "depths, measured values, or coordinate-like information are high-risk.\n"
        "  - Material ambiguity: important numbers, dates, names, emails, API "
        "numbers, locations, or table cells cannot be confidently read from the "
        "page image; OCR drafts disagree on a material value and the image does "
        "not clearly resolve it; table row, column, header, or merged-cell "
        "alignment is uncertain; visible material text appears omitted, truncated, "
        "or structurally misplaced; or checkbox state cannot be confidently "
        "determined.\n"
        "  - Do not set needs_human_review=true merely because the page contains "
        "ordinary headers, stamps, signatures, simple prose, simple clearly-readable "
        "dates, decorative graphics, or low-value metadata.\n"
        "  - Keep warnings short and concrete; warnings are audit notes, not a "
        "routing signal.\n\n"
        "Return only the structured fields requested by the schema.\n\n"
        f"Document ID: {inputs.document_id}\n"
        f"Page: {inputs.page}\n\n"
        "Union OCR draft Markdown:\n"
        "```markdown\n"
        f"{inputs.union_markdown}\n"
        "```\n\n"
        "Small OCR draft Markdown:\n"
        "```markdown\n"
        f"{inputs.small_markdown}\n"
        "```"
    )


def build_verify_prompt(inputs: PageReconcileInputs, round_one_markdown: str) -> str:
    return (
        "You are a verifier and finalizer for a single PDF page reconciliation.\n\n"
        "Use the page image as the authoritative source of truth. Treat the candidate "
        "Markdown as fallible.\n\n"
        "Goals:\n"
        "- Produce final clean Markdown for this one page only.\n"
        "- Correct factual, structural, table, checkbox, date, email, coordinate, "
        "location, and omission errors when the page image supports the correction.\n"
        "- Preserve visible text, headings, lists, tables, checkbox states, symbols, "
        "footnotes, and image references when they are supported by the page.\n"
        "- Table rules:\n"
        "  - Prefer GFM pipe tables for simple rectangular data tables.\n"
        "  - Every GFM table row must have the same number of cells as the separator row.\n"
        "  - Use raw HTML <table> markup only when the visible table needs structure "
        "that GFM cannot represent, such as merged cells, nested headers, rowspan, "
        "colspan, or irregular form layout.\n"
        "  - If the candidate contains raw HTML but the visible table is simple and "
        "rectangular, convert it to a clean GFM pipe table.\n"
        "  - If the candidate contains a GFM pipe table but the visible table has "
        "merged or irregular cells, convert it to raw HTML <table>.\n"
        "  - Preserve raw HTML <table> markup when the page image shows a real merged "
        "or irregular table.\n"
        "  - Do not preserve table markup blindly. The page image decides whether "
        "something is a real table.\n"
        "- Do not invent content that is not visible in the image or reasonably "
        "supported by the candidate.\n"
        "- Set needs_human_review=false only when the final Markdown is faithful to "
        "the page image and no material ambiguity remains.\n"
        "- Set needs_human_review=true when any unresolved material ambiguity remains.\n"
        "- Set winner=mixed when you make corrections to the candidate Markdown.\n"
        "- Set winner=uncertain only when unresolved ambiguity remains after "
        "verification.\n"
        "- Keep warnings short and concrete; warnings are audit notes, not a routing "
        "signal.\n\n"
        "Return only the structured fields requested by the schema.\n\n"
        f"Document ID: {inputs.document_id}\n"
        f"Page: {inputs.page}\n\n"
        "Candidate round-one Markdown:\n"
        "```markdown\n"
        f"{round_one_markdown}\n"
        "```"
    )


def _normalize_model_call(raw: Mapping[str, Any] | ModelCallResult) -> ModelCallResult:
    if isinstance(raw, ModelCallResult):
        return raw
    return ModelCallResult(payload=raw)


def _llm_call_record(
    *,
    round_number: int,
    model: str,
    prompt_version: str,
    call_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        **dict(call_metadata),
        "round": round_number,
        "model": model,
        "prompt_version": prompt_version,
    }


class VisionReconciler:
    def __init__(
        self,
        *,
        client: VisionModelClient,
        prompt_version: str = DEFAULT_RECONCILE_PROMPT_VERSION,
    ):
        self.client = client
        self.prompt_version = prompt_version

    def _run_model_round(
        self,
        inputs: PageReconcileInputs,
        prompt: str,
        round_number: int,
    ) -> tuple[ModelReconcileResponse, dict[str, Any]]:
        raw_call = _normalize_model_call(
            self.client.reconcile(image_path=inputs.page_image_path, prompt=prompt)
        )
        response = ModelReconcileResponse.from_payload(raw_call.payload)
        if response.winner == "uncertain" and not response.needs_human_review:
            response = ModelReconcileResponse(
                reconciled_markdown=response.reconciled_markdown,
                winner=response.winner,
                warnings=response.warnings,
                needs_human_review=True,
            )
        call_record = _llm_call_record(
            round_number=round_number,
            model=self.client.model,
            prompt_version=self.prompt_version,
            call_metadata=raw_call.call_metadata,
        )
        return response, call_record

    def reconcile_page(self, inputs: PageReconcileInputs) -> PageReconciliationResult:
        round_one, round_one_call = self._run_model_round(
            inputs,
            build_reconcile_prompt(inputs),
            1,
        )
        llm_calls = [round_one_call]
        final_response = round_one
        if round_one.needs_human_review:
            round_two, round_two_call = self._run_model_round(
                inputs,
                build_verify_prompt(inputs, round_one.reconciled_markdown),
                2,
            )
            llm_calls.append(round_two_call)
            final_response = round_two

        return PageReconciliationResult(
            document_id=inputs.document_id,
            page=inputs.page,
            reconciled_markdown=final_response.reconciled_markdown,
            winner=final_response.winner,
            warnings=final_response.warnings,
            needs_human_review=final_response.needs_human_review,
            model=self.client.model,
            prompt_version=self.prompt_version,
            source_refs={
                "page_image": inputs.page_image_path.as_posix(),
                "union_markdown": inputs.union_markdown_path.as_posix(),
                "small_markdown": inputs.small_markdown_path.as_posix(),
            },
            llm_calls=llm_calls,
        )


def image_data_url(image_path: Path) -> str:
    content_type = mimetypes.guess_type(image_path.as_posix())[0] or "image/png"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def _get_attr_or_key(value: Any, key: str, default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _usage_metadata(usage: Any) -> dict[str, int | None]:
    input_details = _get_attr_or_key(usage, "input_tokens_details", {})
    output_details = _get_attr_or_key(usage, "output_tokens_details", {})
    return {
        "input_tokens": _get_attr_or_key(usage, "input_tokens"),
        "cached_input_tokens": _get_attr_or_key(input_details, "cached_tokens", 0),
        "output_tokens": _get_attr_or_key(usage, "output_tokens"),
        "reasoning_tokens": _get_attr_or_key(output_details, "reasoning_tokens", 0),
        "total_tokens": _get_attr_or_key(usage, "total_tokens"),
    }


def _pricing_for_model(model: str) -> dict[str, Any] | None:
    rates = OPENAI_MODEL_PRICING.get(model)
    if rates is None:
        return None
    return {
        **rates,
        "currency": "USD",
        "source": OPENAI_PRICING_SOURCE,
        "captured_at": OPENAI_PRICING_CAPTURED_AT,
    }


def _estimated_cost_usd(*, model: str, usage: Mapping[str, int | None]) -> float | None:
    pricing = _pricing_for_model(model)
    if pricing is None:
        return None
    input_tokens = usage.get("input_tokens")
    cached_input_tokens = usage.get("cached_input_tokens") or 0
    output_tokens = usage.get("output_tokens")
    if input_tokens is None or output_tokens is None:
        return None
    uncached_input_tokens = max(input_tokens - cached_input_tokens, 0)
    return (
        uncached_input_tokens / 1_000_000 * pricing["input_per_1m"]
        + cached_input_tokens / 1_000_000 * pricing["cached_input_per_1m"]
        + output_tokens / 1_000_000 * pricing["output_per_1m"]
    )


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

    def _input_payload(
        self,
        *,
        image_path: Path,
        prompt: str,
        include_image: bool,
    ) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
        if include_image:
            content.append(
                {
                    "type": "input_image",
                    "image_url": image_data_url(image_path),
                    "detail": DEFAULT_IMAGE_DETAIL,
                }
            )
        return [{"role": "user", "content": content}]

    def _count_input_tokens(self, *, input_payload: list[dict[str, Any]]) -> int:
        input_tokens_api = getattr(self._client.responses, "input_tokens", None)
        if input_tokens_api is None:
            input_tokens_api = getattr(self._client.responses, "inputTokens", None)
        create = getattr(input_tokens_api, "create")
        result = create(model=self.model, input=input_payload)
        return int(_get_attr_or_key(result, "input_tokens"))

    def _token_split_metadata(
        self,
        *,
        image_path: Path,
        prompt: str,
        full_input: list[dict[str, Any]],
    ) -> dict[str, Any]:
        try:
            full_tokens = self._count_input_tokens(input_payload=full_input)
            text_tokens = self._count_input_tokens(
                input_payload=self._input_payload(
                    image_path=image_path,
                    prompt=prompt,
                    include_image=False,
                )
            )
            return {
                "input_text_tokens_derived": text_tokens,
                "input_image_tokens_derived": max(full_tokens - text_tokens, 0),
                "input_split_method": "responses.input_tokens_delta",
            }
        except Exception as exc:
            return {
                "input_text_tokens_derived": None,
                "input_image_tokens_derived": None,
                "input_split_method": "unavailable",
                "accounting_warning": str(exc),
            }

    def reconcile(self, *, image_path: Path, prompt: str) -> ModelCallResult:
        full_input = self._input_payload(image_path=image_path, prompt=prompt, include_image=True)
        response = self._client.responses.create(
            model=self.model,
            input=full_input,
            text={"format": RECONCILE_RESPONSE_FORMAT},
        )
        usage_metadata = _usage_metadata(getattr(response, "usage", None))
        token_split = self._token_split_metadata(
            image_path=image_path,
            prompt=prompt,
            full_input=full_input,
        )
        pricing = _pricing_for_model(self.model)
        call_metadata: dict[str, Any] = {
            "response_id": getattr(response, "id", None),
            **usage_metadata,
            **token_split,
            "image_count": 1,
            "image_detail": DEFAULT_IMAGE_DETAIL,
            "estimated_cost_usd": _estimated_cost_usd(model=self.model, usage=usage_metadata),
        }
        if pricing is not None:
            call_metadata["pricing"] = pricing
        return ModelCallResult(
            payload=json.loads(response.output_text),
            call_metadata=call_metadata,
        )


def _published_page_set(
    *,
    catalog: PageCatalog,
    store: LocalObjectStore,
    document_id: str,
    ignored_models: set[str] | None = None,
) -> set[int]:
    ignored_models = ignored_models or set()
    pages: set[int] = set()
    for row in catalog.list_pages(document_id, status=PUBLISHED):
        if row["decision_key"] and ignored_models:
            try:
                decision = json.loads(store.read_text(row["decision_key"]))
            except (OSError, json.JSONDecodeError):
                continue
            if decision.get("model") in ignored_models:
                continue
        pages.add(int(row["page"]))
    return pages


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


def _asset_base_dir_for(inputs: PageReconcileInputs, result: PageReconciliationResult) -> Path:
    union_page_dir = inputs.union_markdown_path.parent
    small_page_dir = inputs.small_markdown_path.parent
    refs = iter_markdown_image_refs(result.reconciled_markdown)
    if not refs:
        return small_page_dir if result.winner == "small" else union_page_dir

    ordered_candidates = (
        [small_page_dir, union_page_dir]
        if result.winner == "small"
        else [union_page_dir, small_page_dir]
    )
    for candidate in ordered_candidates:
        try:
            if all(resolve_asset_path(ref, candidate).exists() for ref in refs):
                return candidate
        except FileNotFoundError:
            continue
    return ordered_candidates[0]


def _prepare_result_for_publish(
    inputs: PageReconcileInputs,
    result: PageReconciliationResult,
) -> tuple[PageReconciliationResult, Path]:
    refs = iter_markdown_image_refs(result.reconciled_markdown)
    if not refs:
        return result, _asset_base_dir_for(inputs, result)

    union_page_dir = inputs.union_markdown_path.parent
    small_page_dir = inputs.small_markdown_path.parent
    ordered_candidates = (
        [small_page_dir, union_page_dir]
        if result.winner == "small"
        else [union_page_dir, small_page_dir]
    )
    replacements: dict[str, str] = {}
    prepared_dir = inputs.union_markdown_path.parent / ".reconcile_assets" / "publish"
    if prepared_dir.exists():
        shutil.rmtree(prepared_dir)
    prepared_imgs_dir = prepared_dir / "imgs"
    for ref in refs:
        for candidate in ordered_candidates:
            try:
                source_path = resolve_asset_path(ref, candidate)
            except FileNotFoundError:
                continue
            if source_path.exists():
                prepared_imgs_dir.mkdir(parents=True, exist_ok=True)
                prepared_path = prepared_imgs_dir / source_path.name
                if prepared_path.exists() and prepared_path.read_bytes() != source_path.read_bytes():
                    suffix = source_path.suffix
                    stem = source_path.stem
                    source_hash = sha256_text(source_path.as_posix())[:8]
                    prepared_path = prepared_imgs_dir / f"{stem}_{source_hash}{suffix}"
                shutil.copy2(source_path, prepared_path)
                replacements[ref] = f"imgs/{prepared_path.name}"
                break

    if not replacements:
        return result, _asset_base_dir_for(inputs, result)

    prepared_markdown = rewrite_markdown_image_refs(result.reconciled_markdown, replacements)
    prepared_result = PageReconciliationResult(
        document_id=result.document_id,
        page=result.page,
        reconciled_markdown=prepared_markdown,
        winner=result.winner,
        warnings=result.warnings,
        needs_human_review=result.needs_human_review,
        model=result.model,
        prompt_version=result.prompt_version,
        source_refs=result.source_refs,
        llm_calls=result.llm_calls,
    )
    return prepared_result, prepared_dir


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
    reconciler = VisionReconciler(client=client)

    ignored_models = set() if client.model == "dry-run-no-llm" else {"dry-run-no-llm"}
    published_before = _published_page_set(
        catalog=catalog,
        store=store,
        document_id=run_root.name,
        ignored_models=ignored_models,
    )
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
        publish_result, asset_base_dir = _prepare_result_for_publish(inputs, result)
        try:
            published = publisher.publish(publish_result, asset_base_dir=asset_base_dir)
        finally:
            staging_root = inputs.union_markdown_path.parent / ".reconcile_assets"
            if asset_base_dir == staging_root / "publish":
                shutil.rmtree(staging_root, ignore_errors=True)
        processed_pages.append(page)
        if published.status == PUBLISHED:
            published_pages.append(page)
        else:
            failed_pages.append(page)

    assembly_result: dict[str, Any] | None = None
    if assemble:
        assembly_result = assemble_document(
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
        "assembly": assembly_result,
        "viewer_manifest_path": viewer_manifest_path,
    }
