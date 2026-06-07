# Page-First Reconciled Asset Store Design

## Purpose

Design the interface between a page reconciliation pipeline and a storage layer.
The pipeline is assumed to already produce final reconciled Markdown for each
page. This design focuses on publishing that result into a local fake-S3 object
store plus a simple SQLite catalog, so the same contract can later move to real
S3 and Oracle.

The first validation milestone is a three-page vertical slice for
`runs/Full_30015375000000`: produce three page results with artifacts, publish
them into fake S3 and SQLite, assemble them, and build a small viewer on top of
the stored outputs.

## Current Context

`runs/Full_30015375000000` already has document-layout extraction outputs:

- `union/combined.md`, `union/combined.jsonl`, and per-page artifacts.
- `small/combined.md`, `small/combined.jsonl`, and per-page artifacts.
- `page.png`, `layout_det_res.png`, `res.json`, `output.md`, `output.docx`,
  and `imgs/` assets under page directories.

For this run, both `small` and `union` have successful page outputs for pages
1-155. The repository already preserves PaddleOCR `imgs/` assets and rewrites
page-local image links when writing combined Markdown.

## Design Decision

Use page-first publishing.

Each reconciled page is published independently. Document assembly happens after
page publishing by reading published page rows in order. This matches the
existing extraction model, makes retries local to one page, and keeps provenance
clear.

## Boundaries

### Reconciliation Pipeline

The pipeline owns document interpretation. For each page, it produces a strict
`PageReconciliationResult`.

Example:

```json
{
  "document_id": "Full_30015375000000",
  "page": 2,
  "reconciled_markdown": "...",
  "winner": "mixed",
  "warnings": [],
  "needs_human_review": false,
  "model": "gpt-...",
  "prompt_version": "reconcile-page-v1",
  "source_refs": {
    "page_image": "runs/Full_30015375000000/union/pages/page_0002/page.png",
    "union_markdown": "runs/Full_30015375000000/union/pages/page_0002/output.md",
    "small_markdown": "runs/Full_30015375000000/small/pages/page_0002/output.md"
  }
}
```

The pipeline may include image references in `reconciled_markdown`. Those
references may use PaddleOCR-style paths such as `imgs/foo.jpg` or
`pages/page_0002/imgs/foo.jpg`.

### Asset-Store Publisher

The publisher owns storage, link rewriting, checksums, and SQLite catalog rows.
It does not decide what the page says.

Input:

- One `PageReconciliationResult`.
- A base path used to resolve local asset references.

Output:

```json
{
  "document_id": "Full_30015375000000",
  "page": 2,
  "status": "published",
  "markdown_key": "pdf-extract/reconciled/Full_30015375000000/pages/page_0002/output.md",
  "assets_key": "pdf-extract/reconciled/Full_30015375000000/pages/page_0002/assets.json",
  "decision_key": "pdf-extract/reconciled/Full_30015375000000/pages/page_0002/decision.json",
  "markdown_sha256": "...",
  "asset_count": 3
}
```

### Document Assembler

The assembler reads SQLite rows where `status = 'published'`, orders them by
page, reads each page's `output.md` from fake S3, and writes document-level
artifacts. It does not need a separate SQLite table in the first version.

## Fake S3 Layout

Use a local filesystem root while preserving S3-shaped keys.

```text
object_store/
  pdf-extract/
    reconciled/
      Full_30015375000000/
        pages/
          page_0002/
            output.md
            decision.json
            assets.json
            assets/
              seal.jpg
              diagram-1.png
        combined/
          combined.md
          manifest.json
```

Published Markdown should not point to local run paths. The publisher rewrites
image references to logical asset URIs:

```text
asset://pdf-extract/reconciled/Full_30015375000000/pages/page_0002/assets/seal.jpg
```

The object key remains usable when migrating from fake S3 to real S3.

## Page Artifacts

Each page publishes four artifact types:

- `output.md`: final Markdown with `asset://` links.
- `decision.json`: pipeline decision and provenance record.
- `assets.json`: page asset manifest.
- SQLite `pages` row: thin index/search/catalog record.

`assets.json` is the per-page source of asset details. It keeps page artifacts
self-contained and avoids normalizing asset rows into SQLite for the first
version.

Example:

```json
{
  "document_id": "Full_30015375000000",
  "page": 2,
  "assets": [
    {
      "asset_uri": "asset://pdf-extract/reconciled/Full_30015375000000/pages/page_0002/assets/seal.jpg",
      "object_key": "pdf-extract/reconciled/Full_30015375000000/pages/page_0002/assets/seal.jpg",
      "source_path": "runs/Full_30015375000000/small/pages/page_0002/imgs/img_in_seal_box.jpg",
      "description": "Surveyor seal/signature crop",
      "content_type": "image/jpeg",
      "sha256": "...",
      "byte_size": 12345
    }
  ]
}
```

Only assets referenced by the final Markdown are copied into the published page.
The source OCR run directories remain the broader provenance store.

## SQLite Schema

SQLite is a thin catalog and search surface. Rich detail lives in object-store
artifacts.

```sql
CREATE TABLE pages (
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
);
```

Fields intentionally excluded from SQLite because they live in `decision.json`:

- `winner`
- `model`
- `prompt_version`
- detailed warnings
- detailed source refs

This keeps local SQLite close to the future Oracle role: lookup, filtering,
assembly, and quick text search.

## Publish Flow

For each page:

1. Validate the `PageReconciliationResult`.
2. Resolve image references in `reconciled_markdown`.
3. Copy referenced images into fake S3 under the page's `assets/` prefix.
4. Rewrite Markdown image links to `asset://` URIs.
5. Write `output.md`, `decision.json`, and `assets.json`.
6. Upsert the SQLite `pages` row.
7. Return a `PublishedPage` receipt.

Publishing is idempotent. Re-running the same document/page overwrites the same
fake-S3 keys and upserts the same SQLite row.

## Assembly Flow

For a document:

1. Query `pages` for `status = 'published'`, ordered by `page`.
2. Read each page `output.md` from fake S3.
3. Join pages into `combined.md` with page headers.
4. Write `combined/combined.md`.
5. Write `combined/manifest.json` with included pages, missing pages, hashes,
   and generated timestamp.

Assembly status can live in `combined/manifest.json` for the first version. A
separate SQLite `assemblies` table can be added later if version history becomes
important.

## Viewer Slice

The first prototype should exercise the design with three pages from
`Full_30015375000000`.

The prototype should:

- Produce or fake three `PageReconciliationResult` objects.
- Publish them through the asset-store interface.
- Store artifacts in fake S3.
- Store catalog rows in SQLite.
- Assemble a three-page `combined.md`.
- Provide a small viewer that reads from SQLite and fake S3.

The viewer should show:

- Page list and status.
- Final published Markdown.
- Linked assets from `assets.json`.
- Human-review and warning counts from SQLite.
- A direct link or path to `decision.json` for debugging.

This viewer is a validation tool, not a production UI.

## Error Handling

If a referenced image cannot be resolved, the publisher should:

- Mark the page as `publish_failed`.
- Write `error_message` in SQLite.
- Avoid writing a misleading `published` row.

It should not silently remove missing image links.

If a page has no referenced images, publishing should still succeed and write an
empty `assets.json`.

Assembly should include only published pages by default and list missing or
failed pages in `combined/manifest.json`.

## Testing

Test coverage should include:

- Publishing a page with no images.
- Publishing a page with PaddleOCR-style `imgs/...` links.
- Publishing a page with `pages/page_0002/imgs/...` links.
- Missing referenced asset marks the page as `publish_failed`.
- Re-publishing the same page is idempotent.
- SQLite row contains only thin catalog fields.
- `decision.json` contains pipeline provenance.
- `assets.json` contains asset details.
- Assembly joins published pages and reports unpublished pages.
- Viewer can load the three-page prototype from SQLite and fake S3.

## Non-Goals

This design does not implement the LLM reconciliation prompt, model choice, or
faithfulness scoring logic. It only defines the contract that such a pipeline
must satisfy before publishing.

This design does not require real S3 or Oracle. The object keys and SQLite rows
are intentionally shaped so they can migrate later.
