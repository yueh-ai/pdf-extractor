# Two-Round Page Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add selective second-round PDF page verification, image-grounded prompt policy, and per-call token/cost accounting to the page reconciler.

**Architecture:** Keep the existing `PageReconciliationResult` and publisher boundary, but add optional `llm_calls` metadata to `decision.json`. `VisionReconciler` runs round one for every page and runs round two only when the normalized round-one result has `needs_human_review = true`, including the existing `winner = "uncertain"` override. The OpenAI client returns both structured payload and compact call metadata; local fake/dry-run clients can return the same wrapper or a legacy dict.

**Tech Stack:** Python dataclasses, pytest, OpenAI Responses API, existing local object-store and SQLite catalog.

---

## File Map

- Modify `pdf_extract/reconciled_store.py`: add optional `llm_calls` to `PageReconciliationResult`, persist it in `decision_payload`, and preserve it through validation.
- Modify `pdf_extract/reconciler.py`: add model-call wrapper types, prompt v5 text, round-two prompt builder, selective second-round routing, OpenAI usage/cost metadata extraction, and preservation of `llm_calls` through asset staging.
- Modify `scripts/run_reconcile.py`: update dry-run client to return a model-call wrapper so dry-run decisions also show one call.
- Modify `tests/test_reconciled_store.py`: cover `llm_calls` persistence.
- Modify `tests/test_reconciler.py`: cover prompt policy, two-round routing, round-two inputs, OpenAI metadata, token split fallback, and dry-run behavior.

Do not modify the SQLite schema for this feature. Detailed call accounting belongs in `decision.json`; the catalog remains compact.

---

### Task 1: Store `llm_calls` In Decision Artifacts

**Files:**
- Modify: `pdf_extract/reconciled_store.py`
- Test: `tests/test_reconciled_store.py`

- [ ] **Step 1: Write the failing store test**

Append this test to `tests/test_reconciled_store.py`:

```python
def test_page_result_decision_payload_includes_llm_calls():
    args = _result_args()
    args["llm_calls"] = [
        {
            "round": 1,
            "model": "gpt-5.4-mini",
            "prompt_version": "reconcile-page-v5",
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
        }
    ]

    result = PageReconciliationResult(**args)
    payload = result.decision_payload()

    assert payload["llm_calls"] == [
        {
            "round": 1,
            "model": "gpt-5.4-mini",
            "prompt_version": "reconcile-page-v5",
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
        }
    ]
    assert isinstance(result.llm_calls, tuple)
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
pytest tests/test_reconciled_store.py::test_page_result_decision_payload_includes_llm_calls -v
```

Expected: FAIL with `TypeError: PageReconciliationResult.__init__() got an unexpected keyword argument 'llm_calls'`.

- [ ] **Step 3: Implement optional `llm_calls` storage**

In `pdf_extract/reconciled_store.py`, change the import and dataclass:

```python
from dataclasses import dataclass, field
```

```python
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
    llm_calls: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
```

Extend `__post_init__` after the existing `source_refs` normalization:

```python
        object.__setattr__(
            self,
            "llm_calls",
            tuple(dict(call) for call in self.llm_calls),
        )
```

Extend `decision_payload()`:

```python
            "source_refs": dict(self.source_refs),
            "llm_calls": [dict(call) for call in self.llm_calls],
```

- [ ] **Step 4: Run the store tests**

Run:

```bash
pytest tests/test_reconciled_store.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_extract/reconciled_store.py tests/test_reconciled_store.py
git commit -m "Store reconciliation LLM call metadata"
```

---

### Task 2: Introduce Model Call Results And Preserve Metadata

**Files:**
- Modify: `pdf_extract/reconciler.py`
- Modify: `tests/test_reconciler.py`

- [ ] **Step 1: Write failing tests for client-result wrapping and asset staging preservation**

Add `ModelCallResult` to the import list in `tests/test_reconciler.py`:

```python
from pdf_extract.reconciler import (
    DEFAULT_RECONCILE_MODEL,
    DEFAULT_RECONCILE_PROMPT_VERSION,
    ModelCallResult,
    OpenAIResponsesVisionClient,
    PageReconcileInputs,
    VisionReconciler,
    build_reconcile_prompt,
    discover_reconcile_pages,
    load_page_inputs,
    run_reconciliation,
)
```

Add this fake client near `FakeVisionClient`:

```python
class MetadataVisionClient:
    model = "metadata-fake-model"

    def reconcile(self, *, image_path: Path, prompt: str) -> ModelCallResult:
        return ModelCallResult(
            payload={
                "reconciled_markdown": "# merged",
                "winner": "mixed",
                "warnings": [],
                "needs_human_review": False,
            },
            call_metadata={
                "response_id": "resp_test",
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            },
        )


class MetadataAssetVisionClient:
    model = "metadata-fake-model"

    def reconcile(self, *, image_path: Path, prompt: str) -> ModelCallResult:
        return ModelCallResult(
            payload={
                "reconciled_markdown": "![seal](imgs/seal.jpg)",
                "winner": "mixed",
                "warnings": [],
                "needs_human_review": False,
            },
            call_metadata={"response_id": "resp_test"},
        )
```

Append these tests:

```python
def test_vision_reconciler_records_llm_call_metadata(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 15, "union draft")
    write_page(run_root, "small", 15, "small draft")

    result = VisionReconciler(client=MetadataVisionClient()).reconcile_page(
        load_page_inputs(run_root, 15)
    )

    assert result.llm_calls == (
        {
            "round": 1,
            "model": "metadata-fake-model",
            "prompt_version": DEFAULT_RECONCILE_PROMPT_VERSION,
            "response_id": "resp_test",
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
        },
    )


def test_prepared_publish_preserves_llm_calls(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    union_page = write_page(run_root, "union", 16, "# union")
    small_page = write_page(run_root, "small", 16, "# small")
    (small_page / "imgs").mkdir()
    (small_page / "imgs" / "seal.jpg").write_bytes(b"jpeg")
    client = MetadataAssetVisionClient()

    result = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=None,
        client=client,
        pages=[16],
    )

    assert result["published_pages"] == [16]
    decision = json.loads(
        (
            tmp_path
            / "object_store"
            / "pdf-extract"
            / "reconciled"
            / "sample-doc"
            / "pages"
            / "page_0016"
            / "decision.json"
        ).read_text(encoding="utf-8")
    )
    assert decision["llm_calls"][0]["response_id"] == "resp_test"
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
pytest tests/test_reconciler.py::test_vision_reconciler_records_llm_call_metadata tests/test_reconciler.py::test_prepared_publish_preserves_llm_calls -v
```

Expected: FAIL because `ModelCallResult` does not exist.

- [ ] **Step 3: Add model-call wrapper types and normalization**

In `pdf_extract/reconciler.py`, change the dataclass import:

```python
from dataclasses import dataclass, field
```

Add this dataclass after `ModelReconcileResponse`:

```python
@dataclass(frozen=True)
class ModelCallResult:
    payload: Mapping[str, Any]
    call_metadata: Mapping[str, Any] = field(default_factory=dict)
```

Update the protocol return type:

```python
class VisionModelClient(Protocol):
    model: str

    def reconcile(self, *, image_path: Path, prompt: str) -> dict[str, Any] | ModelCallResult:
        ...
```

Add helpers before `VisionReconciler`:

```python
def _normalize_model_call(raw: dict[str, Any] | ModelCallResult) -> ModelCallResult:
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
        "round": round_number,
        "model": model,
        "prompt_version": prompt_version,
        **dict(call_metadata),
    }
```

Update `VisionReconciler.reconcile_page` to normalize one call:

```python
    def reconcile_page(self, inputs: PageReconcileInputs) -> PageReconciliationResult:
        prompt = build_reconcile_prompt(inputs)
        raw_call = _normalize_model_call(
            self.client.reconcile(image_path=inputs.page_image_path, prompt=prompt)
        )
        response = ModelReconcileResponse.from_payload(raw_call.payload)
        needs_human_review = response.needs_human_review or response.winner == "uncertain"
        return PageReconciliationResult(
            document_id=inputs.document_id,
            page=inputs.page,
            reconciled_markdown=response.reconciled_markdown,
            winner=response.winner,
            warnings=response.warnings,
            needs_human_review=needs_human_review,
            model=self.client.model,
            prompt_version=self.prompt_version,
            source_refs={
                "page_image": inputs.page_image_path.as_posix(),
                "union_markdown": inputs.union_markdown_path.as_posix(),
                "small_markdown": inputs.small_markdown_path.as_posix(),
            },
            llm_calls=(
                _llm_call_record(
                    round_number=1,
                    model=self.client.model,
                    prompt_version=self.prompt_version,
                    call_metadata=raw_call.call_metadata,
                ),
            ),
        )
```

In `_prepare_result_for_publish`, preserve `llm_calls` when creating `prepared_result`:

```python
        llm_calls=result.llm_calls,
```

- [ ] **Step 4: Run reconciler tests**

Run:

```bash
pytest tests/test_reconciler.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_extract/reconciler.py tests/test_reconciler.py
git commit -m "Preserve reconciliation model call metadata"
```

---

### Task 3: Add V5 Round-One Prompt Policy

**Files:**
- Modify: `pdf_extract/reconciler.py`
- Modify: `tests/test_reconciler.py`

- [ ] **Step 1: Write failing prompt-policy tests**

Append this test to `tests/test_reconciler.py`:

```python
def test_build_reconcile_prompt_names_high_risk_and_ambiguity_policy(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 17, "union draft")
    write_page(run_root, "small", 17, "small draft")

    prompt = build_reconcile_prompt(load_page_inputs(run_root, 17))

    assert "Narrow high-risk structures" in prompt
    assert "casing, tubing, cement, formation tops" in prompt
    assert "directional survey, directional targets, and coordinate tables" in prompt
    assert "latitude, longitude, +N/-S offsets, +E/-W offsets" in prompt
    assert "Checkbox groups where the checked or unchecked state changes meaning" in prompt
    assert "Handwritten or crossed-out corrections" in prompt
    assert "Material ambiguity" in prompt
    assert "Do not set needs_human_review=true merely because" in prompt
    assert "warnings are audit notes" in prompt
```

Change `test_vision_reconciler_returns_page_result_and_uses_prompt_version` so the expected prompt version remains the constant, not a literal:

```python
    assert result.prompt_version == DEFAULT_RECONCILE_PROMPT_VERSION
```

- [ ] **Step 2: Run the failing prompt test**

Run:

```bash
pytest tests/test_reconciler.py::test_build_reconcile_prompt_names_high_risk_and_ambiguity_policy -v
```

Expected: FAIL because the v4 prompt does not include the narrowed policy language.

- [ ] **Step 3: Update prompt version and prompt text**

In `pdf_extract/reconciler.py`, change:

```python
DEFAULT_RECONCILE_PROMPT_VERSION = "reconcile-page-v5"
```

In `build_reconcile_prompt`, replace the current final review-warning bullets:

```python
        "- Set needs_human_review to true if the page is unreadable, materially "
        "ambiguous, or structurally incomplete.\n"
        "- Keep warnings short and concrete.\n\n"
```

with:

```python
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
```

- [ ] **Step 4: Run focused prompt tests**

Run:

```bash
pytest tests/test_reconciler.py::test_build_reconcile_prompt_is_general_and_uses_image_as_authority tests/test_reconciler.py::test_build_reconcile_prompt_preserves_complex_html_tables tests/test_reconciler.py::test_build_reconcile_prompt_names_high_risk_and_ambiguity_policy tests/test_reconciler.py::test_vision_reconciler_returns_page_result_and_uses_prompt_version -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_extract/reconciler.py tests/test_reconciler.py
git commit -m "Update reconciliation prompt review policy"
```

---

### Task 4: Add Selective Round-Two Verification

**Files:**
- Modify: `pdf_extract/reconciler.py`
- Modify: `tests/test_reconciler.py`

- [ ] **Step 1: Write failing two-round tests**

Add this fake client to `tests/test_reconciler.py`:

```python
class SequencedVisionClient:
    model = "sequenced-fake-model"

    def __init__(self, responses: list[dict[str, object]]):
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def reconcile(self, *, image_path: Path, prompt: str) -> dict[str, object]:
        self.calls.append({"image_path": image_path, "prompt": prompt})
        if not self.responses:
            raise AssertionError("No fake response queued")
        return self.responses.pop(0)
```

Append these tests:

```python
def test_round_one_false_does_not_run_round_two(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 18, "union draft")
    write_page(run_root, "small", 18, "small draft")
    client = SequencedVisionClient(
        [
            {
                "reconciled_markdown": "# round one",
                "winner": "mixed",
                "warnings": ["audit only"],
                "needs_human_review": False,
            }
        ]
    )

    result = VisionReconciler(client=client).reconcile_page(load_page_inputs(run_root, 18))

    assert result.reconciled_markdown == "# round one"
    assert result.needs_human_review is False
    assert len(client.calls) == 1
    assert result.llm_calls[0]["round"] == 1


def test_round_one_true_runs_round_two_and_publishes_round_two_result(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 19, "union draft")
    write_page(run_root, "small", 19, "small draft")
    client = SequencedVisionClient(
        [
            {
                "reconciled_markdown": "# round one bad date 7/1/10",
                "winner": "mixed",
                "warnings": ["date uncertain"],
                "needs_human_review": True,
            },
            {
                "reconciled_markdown": "# round two fixed date 7/11/10",
                "winner": "mixed",
                "warnings": [],
                "needs_human_review": False,
            },
        ]
    )

    result = VisionReconciler(client=client).reconcile_page(load_page_inputs(run_root, 19))

    assert result.reconciled_markdown == "# round two fixed date 7/11/10"
    assert result.needs_human_review is False
    assert len(client.calls) == 2
    assert result.llm_calls[0]["round"] == 1
    assert result.llm_calls[1]["round"] == 2
    round_two_prompt = client.calls[1]["prompt"]
    assert "# round one bad date 7/1/10" in round_two_prompt
    assert "Union OCR draft Markdown" not in round_two_prompt
    assert "Small OCR draft Markdown" not in round_two_prompt


def test_round_two_true_leaves_final_page_for_human_review(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 20, "union draft")
    write_page(run_root, "small", 20, "small draft")
    client = SequencedVisionClient(
        [
            {
                "reconciled_markdown": "# round one",
                "winner": "mixed",
                "warnings": ["table uncertain"],
                "needs_human_review": True,
            },
            {
                "reconciled_markdown": "# round two still uncertain",
                "winner": "uncertain",
                "warnings": ["table alignment unresolved"],
                "needs_human_review": False,
            },
        ]
    )

    result = VisionReconciler(client=client).reconcile_page(load_page_inputs(run_root, 20))

    assert result.reconciled_markdown == "# round two still uncertain"
    assert result.winner == "uncertain"
    assert result.needs_human_review is True
    assert result.warnings == ("table alignment unresolved",)


def test_uncertain_round_one_winner_runs_round_two(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 21, "union draft")
    write_page(run_root, "small", 21, "small draft")
    client = SequencedVisionClient(
        [
            {
                "reconciled_markdown": "# round one uncertain",
                "winner": "uncertain",
                "warnings": [],
                "needs_human_review": False,
            },
            {
                "reconciled_markdown": "# round two accepted",
                "winner": "mixed",
                "warnings": [],
                "needs_human_review": False,
            },
        ]
    )

    result = VisionReconciler(client=client).reconcile_page(load_page_inputs(run_root, 21))

    assert len(client.calls) == 2
    assert result.reconciled_markdown == "# round two accepted"
    assert result.needs_human_review is False
```

- [ ] **Step 2: Run the failing two-round tests**

Run:

```bash
pytest tests/test_reconciler.py::test_round_one_false_does_not_run_round_two tests/test_reconciler.py::test_round_one_true_runs_round_two_and_publishes_round_two_result tests/test_reconciler.py::test_round_two_true_leaves_final_page_for_human_review tests/test_reconciler.py::test_uncertain_round_one_winner_runs_round_two -v
```

Expected: FAIL because `VisionReconciler` only calls the model once.

- [ ] **Step 3: Add round-two prompt builder**

In `pdf_extract/reconciler.py`, add this function after `build_reconcile_prompt`:

```python
def build_verify_prompt(inputs: PageReconcileInputs, round_one_markdown: str) -> str:
    return (
        "You are verifying a candidate Markdown extraction for a single PDF page.\n\n"
        "Use the page image as the authoritative source of truth. Treat the "
        "candidate Markdown as a fallible draft.\n\n"
        "Goals:\n"
        "- Compare the candidate Markdown directly against the PDF page image.\n"
        "- Correct factual, structural, table, checkbox, date, email, coordinate, "
        "location, and omission errors visible in the page image.\n"
        "- Preserve readable Markdown and the existing table policy: use GFM pipe "
        "tables for simple rectangular data and raw HTML <table> only for merged, "
        "nested, or irregular visible tables.\n"
        "- Do not introduce content that is not visible in the image or already "
        "faithfully represented in the candidate Markdown.\n"
        "- Set needs_human_review=false only when the corrected Markdown is faithful "
        "to the page and no material ambiguity remains.\n"
        "- Set needs_human_review=true when important values, table alignment, "
        "checkbox state, coordinates, dates, names, emails, or visible material text "
        "remain unresolved after verification.\n"
        "- Use winner=mixed when corrections were made. Use winner=uncertain only "
        "when unresolved material ambiguity remains.\n"
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
```

- [ ] **Step 4: Refactor `VisionReconciler` to call rounds**

In `VisionReconciler`, add a helper:

```python
    def _run_model_round(
        self,
        *,
        inputs: PageReconcileInputs,
        prompt: str,
        round_number: int,
    ) -> tuple[ModelReconcileResponse, dict[str, Any]]:
        raw_call = _normalize_model_call(
            self.client.reconcile(image_path=inputs.page_image_path, prompt=prompt)
        )
        response = ModelReconcileResponse.from_payload(raw_call.payload)
        response = ModelReconcileResponse(
            reconciled_markdown=response.reconciled_markdown,
            winner=response.winner,
            warnings=response.warnings,
            needs_human_review=response.needs_human_review or response.winner == "uncertain",
        )
        call_record = _llm_call_record(
            round_number=round_number,
            model=self.client.model,
            prompt_version=self.prompt_version,
            call_metadata=raw_call.call_metadata,
        )
        return response, call_record
```

Replace `reconcile_page` with:

```python
    def reconcile_page(self, inputs: PageReconcileInputs) -> PageReconciliationResult:
        round_one, round_one_call = self._run_model_round(
            inputs=inputs,
            prompt=build_reconcile_prompt(inputs),
            round_number=1,
        )
        final_response = round_one
        llm_calls: list[dict[str, Any]] = [round_one_call]

        if round_one.needs_human_review:
            round_two, round_two_call = self._run_model_round(
                inputs=inputs,
                prompt=build_verify_prompt(inputs, round_one.reconciled_markdown),
                round_number=2,
            )
            final_response = round_two
            llm_calls.append(round_two_call)

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
```

- [ ] **Step 5: Run reconciler tests**

Run:

```bash
pytest tests/test_reconciler.py -v
```

Expected: PASS. If `test_uncertain_winner_forces_human_review` now fails because it expected one queued response, update that test to use `SequencedVisionClient` with a round-two response or assert the final result after round two.

- [ ] **Step 6: Commit**

```bash
git add pdf_extract/reconciler.py tests/test_reconciler.py
git commit -m "Add selective second-round page verification"
```

---

### Task 5: Add OpenAI Usage, Token Split, And Cost Metadata

**Files:**
- Modify: `pdf_extract/reconciler.py`
- Modify: `tests/test_reconciler.py`

- [ ] **Step 1: Write fake SDK support for usage and input-token counts**

Replace the current fake OpenAI classes in `tests/test_reconciler.py` with:

```python
class FakeInputTokensAPI:
    def __init__(self, counts: list[int] | None = None, *, fail: bool = False):
        self.counts = list(counts or [])
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("input token preflight failed")
        if not self.counts:
            raise AssertionError("No fake input token count queued")
        return SimpleNamespace(input_tokens=self.counts.pop(0))


class FakeResponsesAPI:
    def __init__(
        self,
        payload: dict,
        *,
        usage: object | None = None,
        input_token_counts: list[int] | None = None,
        input_tokens_fail: bool = False,
    ):
        self.payload = payload
        self.usage = usage
        self.calls: list[dict[str, object]] = []
        self.input_tokens = FakeInputTokensAPI(input_token_counts, fail=input_tokens_fail)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            id="resp_test",
            output_text=json.dumps(self.payload),
            usage=self.usage,
        )


class FakeOpenAISDK:
    def __init__(
        self,
        payload: dict,
        *,
        usage: object | None = None,
        input_token_counts: list[int] | None = None,
        input_tokens_fail: bool = False,
    ):
        self.responses = FakeResponsesAPI(
            payload,
            usage=usage,
            input_token_counts=input_token_counts,
            input_tokens_fail=input_tokens_fail,
        )
```

- [ ] **Step 2: Write failing OpenAI metadata tests**

Append these tests:

```python
def test_openai_responses_vision_client_returns_usage_and_token_split_metadata(tmp_path):
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    usage = SimpleNamespace(
        input_tokens=1200,
        input_tokens_details=SimpleNamespace(cached_tokens=100),
        output_tokens=300,
        output_tokens_details=SimpleNamespace(reasoning_tokens=40),
        total_tokens=1500,
    )
    fake_sdk = FakeOpenAISDK(
        {
            "reconciled_markdown": "# merged",
            "winner": "mixed",
            "warnings": [],
            "needs_human_review": False,
        },
        usage=usage,
        input_token_counts=[1200, 200],
    )
    client = OpenAIResponsesVisionClient(model="gpt-5.4-mini", sdk_client=fake_sdk)

    response = client.reconcile(image_path=image_path, prompt="reconcile this page")

    assert isinstance(response, ModelCallResult)
    assert response.payload["winner"] == "mixed"
    assert response.call_metadata["response_id"] == "resp_test"
    assert response.call_metadata["input_tokens"] == 1200
    assert response.call_metadata["cached_input_tokens"] == 100
    assert response.call_metadata["output_tokens"] == 300
    assert response.call_metadata["reasoning_tokens"] == 40
    assert response.call_metadata["total_tokens"] == 1500
    assert response.call_metadata["input_text_tokens_derived"] == 200
    assert response.call_metadata["input_image_tokens_derived"] == 1000
    assert response.call_metadata["input_split_method"] == "responses.input_tokens_delta"
    assert response.call_metadata["image_count"] == 1
    assert response.call_metadata["image_detail"] == "high"
    assert response.call_metadata["estimated_cost_usd"] > 0
    assert response.call_metadata["pricing"]["captured_at"] == "2026-06-08"


def test_openai_responses_vision_client_keeps_content_when_token_preflight_fails(tmp_path):
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    usage = {
        "input_tokens": 1200,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens": 300,
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": 1500,
    }
    fake_sdk = FakeOpenAISDK(
        {
            "reconciled_markdown": "# merged",
            "winner": "mixed",
            "warnings": [],
            "needs_human_review": False,
        },
        usage=usage,
        input_tokens_fail=True,
    )
    client = OpenAIResponsesVisionClient(model="gpt-5.4-mini", sdk_client=fake_sdk)

    response = client.reconcile(image_path=image_path, prompt="reconcile this page")

    assert response.payload["reconciled_markdown"] == "# merged"
    assert response.call_metadata["input_text_tokens_derived"] is None
    assert response.call_metadata["input_image_tokens_derived"] is None
    assert response.call_metadata["input_split_method"] == "unavailable"
    assert "input token preflight failed" in response.call_metadata["accounting_warning"]
```

- [ ] **Step 3: Run the failing OpenAI tests**

Run:

```bash
pytest tests/test_reconciler.py::test_openai_responses_vision_client_returns_usage_and_token_split_metadata tests/test_reconciler.py::test_openai_responses_vision_client_keeps_content_when_token_preflight_fails -v
```

Expected: FAIL because the OpenAI client currently returns only a dict payload.

- [ ] **Step 4: Add pricing and metadata helpers**

In `pdf_extract/reconciler.py`, add constants near the default model:

```python
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
```

Add these helpers before `OpenAIResponsesVisionClient`:

```python
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
```

- [ ] **Step 5: Refactor OpenAI request construction and preflight counting**

In `OpenAIResponsesVisionClient`, add helper methods:

```python
    def _input_payload(self, *, image_path: Path, prompt: str, include_image: bool) -> list[dict[str, Any]]:
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
```

Replace `reconcile()` with:

```python
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
```

- [ ] **Step 6: Update existing OpenAI test expectations**

In `test_openai_responses_vision_client_sends_image_and_json_schema`, replace:

```python
    assert response["winner"] == "mixed"
```

with:

```python
    assert response.payload["winner"] == "mixed"
```

Update the image detail assertion:

```python
    assert image_item["detail"] == "high"
```

The fake SDK for this existing test must pass token counts:

```python
    fake_sdk = FakeOpenAISDK(
        {
            "reconciled_markdown": "# merged",
            "winner": "mixed",
            "warnings": ["table uncertain"],
            "needs_human_review": True,
        },
        input_token_counts=[100, 20],
    )
```

- [ ] **Step 7: Run OpenAI client tests**

Run:

```bash
pytest tests/test_reconciler.py::test_openai_responses_vision_client_sends_image_and_json_schema tests/test_reconciler.py::test_openai_responses_vision_client_returns_usage_and_token_split_metadata tests/test_reconciler.py::test_openai_responses_vision_client_keeps_content_when_token_preflight_fails -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add pdf_extract/reconciler.py tests/test_reconciler.py
git commit -m "Record OpenAI reconciliation token accounting"
```

---

### Task 6: Add Dry-Run Call Metadata And End-To-End Decision Tests

**Files:**
- Modify: `scripts/run_reconcile.py`
- Modify: `tests/test_reconciler.py`

- [ ] **Step 1: Write failing dry-run and decision tests**

Append this test to `tests/test_reconciler.py`:

```python
def test_dry_run_client_returns_call_metadata():
    helpers = load_run_reconcile_script()
    client = helpers["create_client"](provider="dry-run", model=None)

    response = client.reconcile(image_path=Path("page.png"), prompt="prompt")

    assert isinstance(response, ModelCallResult)
    assert response.payload["winner"] == "uncertain"
    assert response.call_metadata["response_id"] == "dry-run"
    assert response.call_metadata["input_tokens"] is None
    assert response.call_metadata["output_tokens"] is None
```

Append this end-to-end test:

```python
def test_run_reconciliation_decision_records_two_llm_calls(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 22, "union draft")
    write_page(run_root, "small", 22, "small draft")
    client = SequencedVisionClient(
        [
            {
                "reconciled_markdown": "# round one",
                "winner": "mixed",
                "warnings": ["verify table"],
                "needs_human_review": True,
            },
            {
                "reconciled_markdown": "# round two",
                "winner": "mixed",
                "warnings": [],
                "needs_human_review": False,
            },
        ]
    )

    result = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=None,
        client=client,
        pages=[22],
    )

    assert result["published_pages"] == [22]
    decision = json.loads(
        (
            tmp_path
            / "object_store"
            / "pdf-extract"
            / "reconciled"
            / "sample-doc"
            / "pages"
            / "page_0022"
            / "decision.json"
        ).read_text(encoding="utf-8")
    )
    assert [call["round"] for call in decision["llm_calls"]] == [1, 2]
    assert decision["needs_human_review"] is False
    assert decision["warnings"] == []
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
pytest tests/test_reconciler.py::test_dry_run_client_returns_call_metadata tests/test_reconciler.py::test_run_reconciliation_decision_records_two_llm_calls -v
```

Expected: dry-run metadata test FAIL because dry-run returns a dict.

- [ ] **Step 3: Update dry-run client**

In `scripts/run_reconcile.py`, import `ModelCallResult`:

```python
from pdf_extract.reconciler import (
    DEFAULT_RECONCILE_MODEL,
    ModelCallResult,
    OpenAIResponsesVisionClient,
    run_reconciliation,
)
```

Change `DryRunVisionClient.reconcile`:

```python
    def reconcile(self, *, image_path: Path, prompt: str) -> ModelCallResult:
        return ModelCallResult(
            payload={
                "reconciled_markdown": "<!-- dry-run reconciliation did not call a vision model -->\n",
                "winner": "uncertain",
                "warnings": ["dry-run client did not call a vision model"],
                "needs_human_review": True,
            },
            call_metadata={
                "response_id": "dry-run",
                "input_tokens": None,
                "cached_input_tokens": None,
                "output_tokens": None,
                "reasoning_tokens": None,
                "total_tokens": None,
                "input_text_tokens_derived": None,
                "input_image_tokens_derived": None,
                "input_split_method": "unavailable",
                "image_count": 1,
                "image_detail": "high",
                "estimated_cost_usd": 0.0,
            },
        )
```

- [ ] **Step 4: Run full Python test suite**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_reconcile.py tests/test_reconciler.py
git commit -m "Add dry-run reconciliation call metadata"
```

---

### Task 7: Final Verification And Manual Smoke Run

**Files:**
- Modify: `scripts/run_reconcile.py`
- Modify: `tests/test_reconciler.py`
- Modify only if verification reveals a bug:
  - `pdf_extract/reconciler.py`
  - `pdf_extract/reconciled_store.py`
  - `tests/test_reconciler.py`
  - `tests/test_reconciled_store.py`

- [ ] **Step 1: Run all tests**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 2: Add a no-assemble CLI smoke option**

In `scripts/run_reconcile.py`, add the argument:

```python
    parser.add_argument(
        "--no-assemble",
        action="store_true",
        help="Skip combined document assembly after page reconciliation.",
    )
```

Pass it to `run_reconciliation`:

```python
        assemble=not args.no_assemble,
```

Then add this focused CLI test to `tests/test_reconciler.py`:

```python
def test_cli_parser_supports_no_assemble():
    helpers = load_run_reconcile_script()
    parser = helpers["create_arg_parser"]()

    args = parser.parse_args(["--provider", "dry-run", "--no-assemble"])

    assert args.no_assemble is True
```

Run:

```bash
pytest tests/test_reconciler.py::test_cli_parser_supports_no_assemble -v
```

Expected: PASS.

- [ ] **Step 3: Run a dry-run reconciliation smoke test on one page**

Run:

```bash
python scripts/run_reconcile.py \
  --provider dry-run \
  --run-root runs/Full_30015375000000 \
  --object-store-root object_store_smoke_two_round \
  --sqlite-path reconciled_smoke_two_round.sqlite \
  --pages 1 \
  --force \
  --no-assemble
```

Expected: command exits 0 and prints JSON with `"published_pages": [1]`.

- [ ] **Step 4: Inspect smoke decision metadata**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path

decision = json.loads(Path(
    "object_store_smoke_two_round/pdf-extract/reconciled/Full_30015375000000/pages/page_0001/decision.json"
).read_text(encoding="utf-8"))

print(json.dumps({
    "needs_human_review": decision["needs_human_review"],
    "call_count": len(decision["llm_calls"]),
    "rounds": [call["round"] for call in decision["llm_calls"]],
    "input_split_methods": [call.get("input_split_method") for call in decision["llm_calls"]],
}, indent=2))
PY
```

Expected output:

```json
{
  "needs_human_review": true,
  "call_count": 2,
  "rounds": [
    1,
    2
  ],
  "input_split_methods": [
    "unavailable",
    "unavailable"
  ]
}
```

Dry-run returns `winner = "uncertain"`, so it intentionally triggers round two and remains marked for human review.

- [ ] **Step 5: Clean smoke artifacts**

Run:

```bash
rm -rf object_store_smoke_two_round reconciled_smoke_two_round.sqlite
```

Expected: command exits 0.

- [ ] **Step 6: Run final status**

Run:

```bash
git status --short
```

Expected: only intended source/test changes are present, plus pre-existing unrelated workspace changes from before this plan if they still exist.

- [ ] **Step 7: Commit final verification adjustments**

```bash
git add scripts/run_reconcile.py tests/test_reconciler.py
git commit -m "Add reconciliation no-assemble smoke option"
```

---

## Self-Review

- Spec coverage:
  - Selective round two is implemented in Task 4.
  - `needs_human_review` remains the only routing signal in Task 4.
  - Warnings do not route because Task 4 checks only normalized `needs_human_review`.
  - Narrow high-risk and ambiguity prompt policy is implemented in Task 3.
  - Round two receives only page image plus round-one Markdown in Task 4.
  - `llm_calls` in `decision.json` is implemented in Tasks 1, 2, 5, and 6.
  - Token/cost metadata and nullable token split fallback are implemented in Task 5.
  - SQLite remains unchanged by design.
  - Failure behavior is preserved: invalid model responses still raise before publish; round two failure is not swallowed.
- Placeholder scan: no `TBD`, `TODO`, `implement later`, or unspecified test steps remain.
- Type consistency:
  - `ModelCallResult.payload` is the structured response mapping.
  - `ModelCallResult.call_metadata` is the compact call-accounting mapping.
  - `PageReconciliationResult.llm_calls` is a sequence of mappings and serializes to a JSON list.
  - `prompt_version` remains attached by `VisionReconciler`, not by the provider client.
