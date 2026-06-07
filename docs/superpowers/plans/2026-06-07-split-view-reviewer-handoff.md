# Split-View Reconciled Reviewer Handoff

## Goal

Improve the current static reconciled viewer so a reviewer can compare each
published page against the source PDF page image:

- Left side: rendered source PDF page image.
- Right side: rendered reconciled Markdown.
- Supporting metadata: status, warnings, asset count, decision path, and asset
  manifest details.

This should be implemented in a new session on top of the current
page-first fake-S3 + SQLite prototype.

## Current State

The current prototype is implemented and merged on `main`.

Important files:

- `pdf_extract/reconciled_store.py`
  - Publishes page artifacts into fake S3.
  - Writes `output.md`, `decision.json`, `assets.json`.
  - Stores a thin SQLite `pages` row.
  - Assembles published pages into `combined/combined.md`.
- `pdf_extract/reconciled_prototype.py`
  - Builds three prototype page results from `runs/Full_30015375000000`.
  - Writes `runs/Full_30015375000000/reconciled_viewer/index.html`.
  - Current viewer renders Markdown as escaped text inside `<pre>`.
- `scripts/run_reconciled_store_prototype.py`
  - CLI entry point for publishing pages and writing the viewer.
- `tests/test_reconciled_store.py`
- `tests/test_reconciled_prototype.py`

Generated local review artifacts currently exist but are intentionally
untracked:

- `object_store/`
- `reconciled_catalog.sqlite`
- `runs/Full_30015375000000/reconciled_viewer/`

The current prototype pages are:

- Page 1: published, 0 assets.
- Page 2: published, 0 assets.
- Page 40: published, 3 image assets.

Page 40 is the useful image-bearing test page.

## Existing Artifact Contract

SQLite has one thin row per page:

- `document_id`
- `page`
- `status`
- `markdown_key`
- `assets_key`
- `decision_key`
- `needs_human_review`
- `warning_count`
- `asset_count`
- `markdown_sha256`
- `markdown_text`
- `error_message`
- `published_at`

Do not add page image paths to SQLite for this viewer unless a later design
requires it. The page image path is already available in `decision.json`.

`decision.json` contains the pipeline/source provenance:

```json
{
  "document_id": "Full_30015375000000",
  "page": 40,
  "winner": "union",
  "warnings": [],
  "needs_human_review": false,
  "model": "prototype-no-llm",
  "prompt_version": "prototype-page-v1",
  "source_refs": {
    "page_image": "runs/Full_30015375000000/union/pages/page_0040/page.png",
    "union_markdown": "runs/Full_30015375000000/union/pages/page_0040/output.md",
    "small_markdown": "runs/Full_30015375000000/small/pages/page_0040/output.md",
    "asset_base_dir": "runs/Full_30015375000000/union/pages/page_0040"
  }
}
```

`assets.json` uses this contract:

```json
{
  "document_id": "Full_30015375000000",
  "page": 40,
  "assets": [
    {
      "source_path": ".../runs/Full_30015375000000/union/pages/page_0040/imgs/example.jpg",
      "asset_uri": "asset://pdf-extract/reconciled/Full_30015375000000/pages/page_0040/assets/example.jpg",
      "object_key": "pdf-extract/reconciled/Full_30015375000000/pages/page_0040/assets/example.jpg",
      "description": "example",
      "content_type": "image/jpeg",
      "sha256": "...",
      "byte_size": 12345
    }
  ]
}
```

## Proposed Viewer Behavior

The viewer should be page-oriented.

For each page section:

- Show a sticky or fixed-height split layout.
- Left pane:
  - Render the source PDF page image from `decision.source_refs.page_image`.
  - Use `object-fit: contain`.
  - Provide the source image path in small metadata text.
- Right pane:
  - Render the page Markdown as document content, not escaped source text.
  - Rewritten `asset://...` image references should display if possible.
  - For asset images, convert `asset://<object_key>` to a relative or absolute
    local file path under the fake-S3 root.
- Metadata row:
  - Page number.
  - Status.
  - Warning count.
  - Asset count.
  - Decision key.

The page list at the top should remain, but it can be compact. It should link
to page sections.

## Rendering Strategy

Keep the next implementation conservative.

Avoid adding a large frontend framework. The current repo has no frontend build
system, and the viewer is only a local validation tool.

Recommended approach:

1. Keep generating a static `index.html` from Python.
2. Add a small Markdown-to-HTML renderer in `pdf_extract/reconciled_prototype.py`
   or a new focused helper module.
3. Support the subset needed by current PaddleOCR Markdown:
   - headings beginning with `#`, `##`, etc.
   - blank-line paragraph breaks.
   - raw HTML blocks already present in OCR output, especially `<table>`,
     `<div>`, and `<img>`.
4. Before injecting HTML into the viewer, rewrite asset links:
   - `asset://pdf-extract/.../assets/foo.jpg`
   - to a file path that the generated HTML can load from `object_store/`.

The current OCR Markdown already contains raw HTML tables and image tags. The
right pane does not need a full CommonMark implementation for the first pass.

If using raw HTML from Markdown, document that this viewer is a local developer
tool and should not be exposed as a web service without sanitization.

## Path Handling

The viewer generator has access to:

- `LocalObjectStore.root`
- SQLite `assets_key`, `decision_key`, `markdown_key`
- page `decision.json`
- page `assets.json`

For source PDF page image:

1. Read `decision.json` from fake S3 via `decision_key`.
2. Extract `source_refs.page_image`.
3. Resolve it relative to the repo root if it is relative.
4. Use a browser-loadable path in the generated HTML.

For asset images:

1. Read `assets.json`.
2. Build a mapping from `asset_uri` to local object-store file path using
   `object_key`.
3. Rewrite `src="asset://..."` occurrences before rendering Markdown.

For local browser review, absolute filesystem paths are acceptable in generated
HTML. If this later becomes a server-backed viewer, replace them with HTTP URLs
served by the app.

## Suggested Layout

Use a restrained, work-focused layout:

```text
------------------------------------------------------------
Document: Full_30015375000000
Pages: [1] [2] [40]
------------------------------------------------------------
Page 40 | published | warnings 0 | assets 3
------------------------------------------------------------
| Source PDF page image          | Rendered Markdown        |
|                                | tables, text, images     |
|                                |                          |
------------------------------------------------------------
Assets
- asset URI, source path, content type, size, sha
Decision
- decision key
```

CSS guidance:

- Use a two-column CSS grid on desktop.
- Stack panes vertically on narrow screens.
- Keep each pane scrollable if content is tall.
- Use `max-height: 85vh` for the image pane and `object-fit: contain`.
- Avoid cards inside cards. Use simple full-width sections and borders.

## Tests To Add

Update `tests/test_reconciled_prototype.py` or add a focused viewer test.

Minimum assertions:

- The viewer HTML includes an `<img>` for the source page image.
- Page 40 renders a split-view section with both source image and Markdown pane.
- `asset://` links in Markdown are rewritten to loadable local file paths.
- The viewer still lists assets with `asset_uri`, `content_type`, `byte_size`,
  and `sha256`.
- Pages 1, 2, and 40 still appear in order.

Use synthetic `tmp_path` page directories like the current prototype test. Add a
fake page image and one fake asset image so the test does not depend on the
large checked-in run.

## Manual Verification

After implementation:

```bash
uv run pytest tests/test_reconciled_store.py tests/test_reconciled_prototype.py -q
uv run pytest -q
```

Then regenerate the real prototype:

```bash
uv run python scripts/run_reconciled_store_prototype.py \
  --run-root runs/Full_30015375000000 \
  --object-store-root object_store \
  --sqlite-path reconciled_catalog.sqlite \
  --viewer-dir runs/Full_30015375000000/reconciled_viewer \
  --pages 1,2,40
```

Review:

```text
runs/Full_30015375000000/reconciled_viewer/index.html
```

Expected:

- Page 1 and page 2 show source page images and rendered text/tables.
- Page 40 shows source page image and rendered Markdown with three image
  references resolved from fake S3.
- Page 40 asset metadata lists three image assets.

## Open Design Questions

These are safe to decide during implementation:

- Should the rendered Markdown pane preserve raw OCR HTML exactly, or should it
  normalize tables later?
- Should image assets render inline in the Markdown pane, or should the first
  pass show them as links plus metadata?
- Should the viewer copy source page images into fake S3, or continue reading
  them from the original run directory through `decision.json`?

Recommendation for the first pass: do not copy source page images into fake S3.
Use `decision.json` and keep the storage contract unchanged.

## Non-Goals

- Do not implement LLM reconciliation.
- Do not add real S3 or Oracle.
- Do not build a web server unless static HTML cannot meet the review need.
- Do not replace the page-first storage contract.
