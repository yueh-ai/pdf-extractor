# Page OCR Reconciliation Design

## Purpose

Design the page-level OCR reconciliation layer for the existing dual-mode PDF
extraction pipeline.

The reconciler produces the best possible Markdown representation of each page
by comparing:

- The rendered source page image, `page.png`.
- The default-layout OCR Markdown, `union/pages/page_XXXX/output.md`.
- The small-layout OCR Markdown, `small/pages/page_XXXX/output.md`.

The rendered page image is the authority. The two OCR Markdown files are drafts
and hints. The reconciler does not perform section extraction, cross-page
deduplication, wellbore fact reconciliation, or current-value selection.

## Current Context

The repository already has:

- Dual extraction runs under `runs/<document_id>/union/` and
  `runs/<document_id>/small/`.
- Per-page rendered images and Markdown outputs.
- A page-first publishing contract in `pdf_extract/reconciled_store.py`.
- A fake-S3 object-store layout under `object_store/`.
- A SQLite page catalog.
- A React reviewer manifest writer and split-view reviewer.

The current prototype in `pdf_extract/reconciled_prototype.py` fakes the
reconciliation decision by choosing one Markdown source. This design replaces
only that decision point. The existing publisher, assembler, and reviewer
contract remain the storage boundary.

## Design Decision

Use a vision-capable LLM for page-level OCR reconciliation.

For each page, send the model the rendered page image plus both OCR Markdown
drafts. The model returns the reconciled Markdown and the compact fields required
by `PageReconciliationResult`.

The primary product is `output.md`. `decision.json` remains a compact receipt,
not a verbose evidence packet. `res.json` is intentionally excluded from the v1
reconciliation contract.

## Non-Goals

- No section-level extraction.
- No wellbore-domain deduplication.
- No cross-page conflict resolution.
- No current-vs-proposed decision making.
- No verbose evidence JSON.
- No use of PaddleOCR `res.json` in v1.
- No change to the fake-S3 or SQLite publishing contract.

## Page Input Contract

Each page reconciliation receives:

```text
document_id
page
page_image_path
union_markdown_path
small_markdown_path
union_markdown
small_markdown
```

`page_image_path` should normally come from the `union` page directory because
both modes render the same source PDF page. If the union image is missing, the
implementation may fall back to the small-mode image and record the chosen path
in `source_refs.page_image`.

## Page Output Contract

The reconciler returns the existing `PageReconciliationResult` shape:

```text
PageReconciliationResult(
  document_id,
  page,
  reconciled_markdown,
  winner,
  warnings,
  needs_human_review,
  model,
  prompt_version,
  source_refs={
    page_image,
    union_markdown,
    small_markdown
  }
)
```

Valid `winner` values remain:

```text
union
small
mixed
uncertain
```

The publisher then writes:

```text
object_store/pdf-extract/reconciled/<document_id>/pages/page_XXXX/
  output.md
  decision.json
  assets.json
  assets/
```

## Decision Artifact Scope

`decision.json` should contain only compact provenance and review-routing data:

- `document_id`
- `page`
- `winner`
- `warnings`
- `needs_human_review`
- `model`
- `prompt_version`
- `source_refs.page_image`
- `source_refs.union_markdown`
- `source_refs.small_markdown`

It should not contain chain-of-thought, per-field evidence, section facts,
domain interpretations, or copied `res.json` content.

## Reconcile Flow

For each selected page:

1. Discover the union and small page directories.
2. Load `page.png`, `union/output.md`, and `small/output.md`.
3. Build a compact vision prompt:
   - Treat `page.png` as authoritative.
   - Use both OCR Markdown drafts as hints.
   - Preserve visible text, headings, tables, checkboxes, symbols, and image
     references.
   - Do not invent content that is not visible or supported by the drafts.
   - Produce clean Markdown suitable for human review and downstream text search.
   - Return only the structured fields needed for `PageReconciliationResult`.
4. Call the injected vision model client.
5. Validate the model response.
6. Publish the result through `ReconciledPagePublisher`.
7. Optionally assemble the reconciled document and write the reviewer manifest.

## Human Review Policy

Set `needs_human_review = true` when any of these conditions apply:

- The rendered page is unreadable or partially unreadable.
- The model cannot confidently resolve a union-vs-small disagreement.
- A table appears structurally incomplete.
- Important labels are visible but cannot be confidently transcribed.
- Image or asset references cannot be preserved or resolved.
- The model selects `winner = "uncertain"`.
- The model emits warnings that materially affect page correctness.

Warnings should be short, concrete strings. They are for reviewer routing and
debugging, not a detailed evidence log.

## Resume And Force Semantics

The reconciliation CLI should be restartable.

By default, reconciliation should process all pages for the document and skip
pages already published in the SQLite catalog with `status = "published"`.

Page selection behavior:

- If `--pages` is omitted, discover all pages that have both source OCR
  directories available.
- If `--pages` is provided, reconcile only that page selection.

Resume behavior:

- Default: skip already published pages.
- `--force`: rerun selected pages even when they are already published.
- Failed or missing pages may be retried on the next run.

This avoids repeated model calls during long document runs while preserving an
explicit way to regenerate pages after prompt, model, or source changes.

## Implementation Shape

Add a focused Python module:

```text
pdf_extract/reconciler.py
```

Suggested data object:

```python
@dataclass(frozen=True)
class PageReconcileInputs:
    document_id: str
    page: int
    page_image_path: Path
    union_markdown_path: Path
    small_markdown_path: Path
    union_markdown: str
    small_markdown: str
```

Suggested service:

```python
class VisionReconciler:
    def reconcile_page(self, inputs: PageReconcileInputs) -> PageReconciliationResult:
        ...
```

The model client should be injected so tests can use a deterministic fake
client. The first implementation can later wire the real client through
environment variables or CLI configuration without changing the reconciler's
core tests.

Add a CLI wrapper:

```text
scripts/run_reconcile.py
```

Example:

```bash
uv run python scripts/run_reconcile.py \
  --run-root runs/Full_30015375000000 \
  --object-store-root object_store \
  --sqlite-path reconciled_catalog.sqlite \
  --viewer-dir runs/Full_30015375000000/reconciled_viewer
```

Selected pages:

```bash
uv run python scripts/run_reconcile.py \
  --run-root runs/Full_30015375000000 \
  --pages 1,2,40
```

Forced rerun:

```bash
uv run python scripts/run_reconcile.py \
  --run-root runs/Full_30015375000000 \
  --pages 28 \
  --force
```

## Testing Strategy

Use fake model clients in tests. Do not call a real model from pytest.

Test coverage should include:

- Page input discovery for union and small page directories.
- Default all-page discovery.
- `--pages` filtering.
- Resume behavior that skips already published pages.
- `--force` behavior that reruns already published pages.
- Model response validation.
- Propagation of `warnings` and `needs_human_review`.
- Publishing integration with `ReconciledPagePublisher`.
- Generated artifacts remain `output.md`, `decision.json`, and `assets.json`.

The tests should use small synthetic page directories in `tmp_path`, not the
large checked-in run artifacts.

## Model Client Boundary

The exact real-model client should stay behind an interface. The first
implementation should use the smallest stable client wrapper that can send a
page image plus Markdown text and receive a structured response. Tests should
exercise the interface with fake clients rather than requiring network access or
model credentials.

The prompt version should start at:

```text
reconcile-page-v1
```
