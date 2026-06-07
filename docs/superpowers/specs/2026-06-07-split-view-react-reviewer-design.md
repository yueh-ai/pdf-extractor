# Split-View React Reviewer Design

## Purpose

Build a read-only reviewer for reconciled page artifacts. A reviewer should be
able to compare the rendered source PDF page image against the reconciled
Markdown output for the same page, inspect metadata, and fall back to raw
Markdown whenever rendering is incomplete or broken.

The reviewer is a validation surface for the existing page-first fake-S3 plus
SQLite prototype. It does not edit Markdown, change reconciliation decisions, or
write review state.

## Current Context

The current prototype publishes page artifacts through
`pdf_extract/reconciled_store.py`:

- `output.md` with `asset://` image links.
- `decision.json` with source provenance, including `source_refs.page_image`.
- `assets.json` with `asset_uri`, `object_key`, source path, content type, byte
  size, and checksum.
- A thin SQLite `pages` row with status, warning count, asset count, Markdown
  text, and artifact keys.

`pdf_extract/reconciled_prototype.py` currently writes a static HTML page that
escapes Markdown into a `<pre>`. This design replaces that viewer surface with a
small React app while preserving the storage contract.

The real page 40 sample includes the hard rendering cases:

- Raw HTML tables emitted by PaddleOCR.
- Raw HTML `<div>` and `<img>` blocks.
- Published `asset://...` image URLs.
- Inline LaTeX-style math such as `$ 60.02^{\circ} $`.
- Very wide tables and long OCR text runs.

## Design Decision

Use a lightweight Vite + React app for the reviewer.

Python remains responsible for publishing and cataloging page artifacts. The
bridge between Python and React is a generated `viewer-manifest.json` placed
next to the built reviewer app. React loads the manifest, renders page navigation
and page metadata, and displays one selected page at a time in a split view.

The reviewer should be served through a local static server rooted at the repo,
or through a Vite dev server configured to expose the same repo-root assets. It
is no longer constrained to be a single hand-written HTML file.

## Non-Goals

- No Markdown editing.
- No save or write-back path.
- No LLM reconciliation changes.
- No storage contract change for page artifacts.
- No real S3, Oracle, authentication, or hosted web service.
- No attempt to make OCR HTML safe for arbitrary untrusted public input.

## Reviewer Manifest

The manifest is the frontend's only data entry point. It denormalizes the small
amount of data needed by the viewer so the React app does not need SQLite access.

Example shape:

```json
{
  "document_id": "Full_30015375000000",
  "generated_at": "2026-06-07T00:00:00Z",
  "pages": [
    {
      "page": 40,
      "status": "published",
      "needs_human_review": false,
      "warning_count": 0,
      "asset_count": 3,
      "markdown_key": "pdf-extract/reconciled/Full_30015375000000/pages/page_0040/output.md",
      "decision_key": "pdf-extract/reconciled/Full_30015375000000/pages/page_0040/decision.json",
      "assets_key": "pdf-extract/reconciled/Full_30015375000000/pages/page_0040/assets.json",
      "markdown_path": "object_store/pdf-extract/reconciled/Full_30015375000000/pages/page_0040/output.md",
      "markdown_url": "/object_store/pdf-extract/reconciled/Full_30015375000000/pages/page_0040/output.md",
      "source_page_image_path": "runs/Full_30015375000000/union/pages/page_0040/page.png",
      "source_page_image_url": "/runs/Full_30015375000000/union/pages/page_0040/page.png",
      "markdown_text": "...",
      "decision": {
        "winner": "union",
        "warnings": [],
        "model": "prototype-no-llm",
        "prompt_version": "prototype-page-v1",
        "source_refs": {
          "page_image": "runs/Full_30015375000000/union/pages/page_0040/page.png"
        }
      },
      "assets": [
        {
          "asset_uri": "asset://pdf-extract/reconciled/Full_30015375000000/pages/page_0040/assets/example.jpg",
          "object_key": "pdf-extract/reconciled/Full_30015375000000/pages/page_0040/assets/example.jpg",
          "local_path": "object_store/pdf-extract/reconciled/Full_30015375000000/pages/page_0040/assets/example.jpg",
          "local_url": "/object_store/pdf-extract/reconciled/Full_30015375000000/pages/page_0040/assets/example.jpg",
          "source_path": "runs/Full_30015375000000/union/pages/page_0040/imgs/example.jpg",
          "description": "example",
          "content_type": "image/jpeg",
          "sha256": "...",
          "byte_size": 12345
        }
      ]
    }
  ]
}
```

The first implementation will include `markdown_text` directly to avoid extra
fetches. It will also include `markdown_path` for transparency and future
lazy-loading.

Paths in the manifest must separate original provenance paths from browser URLs.
For the first local-only pass, the Python manifest writer emits repo-root
relative URLs such as `/runs/.../page.png` and `/object_store/.../asset.jpg`.
The app displays original filesystem paths as metadata but uses browser URLs for
`src` and `fetch` values.

## React App Structure

Place the frontend under a focused root such as `reviewer/`:

```text
reviewer/
  package.json
  index.html
  src/
    App.tsx
    manifest.ts
    assetResolver.ts
    MarkdownPane.tsx
    SourcePagePane.tsx
    PageSidebar.tsx
    MetadataPanel.tsx
    ErrorBoundary.tsx
    styles.css
```

Important components:

- `App`: loads `viewer-manifest.json`, tracks selected page and Markdown view
  mode.
- `PageSidebar`: compact page list with status, warnings, and asset count.
- `SourcePagePane`: displays `source_page_image_path` using `object-fit:
  contain` and exposes the path in small metadata text.
- `MarkdownPane`: provides `Rendered` and `Raw Markdown` tabs for the selected
  page.
- `RenderedMarkdown`: wraps the `react-markdown` pipeline.
- `AssetImage`: resolves `asset://` and local image references, then renders an
  image with a broken-image fallback.
- `ReviewTable`: wraps rendered tables in a horizontally scrollable container.
- `MetadataPanel`: shows decision key, assets key, source refs, and asset
  details.
- `ErrorBoundary`: catches rendering failures and keeps raw Markdown available.

## Markdown Render Pipeline

Use the unified/remark/rehype ecosystem through `react-markdown`.

Conceptual component:

```tsx
<Markdown
  remarkPlugins={[remarkGfm, remarkMath]}
  rehypePlugins={[rehypeRaw, rehypeMathjax]}
  components={{
    img: AssetImage,
    table: ReviewTable,
    a: ReviewLink,
  }}
>
  {markdown}
</Markdown>
```

Pipeline stages:

1. Markdown text enters `react-markdown`.
2. `remark-gfm` runs in the Markdown stage. It recognizes GitHub-flavored
   Markdown syntax such as pipe tables when OCR emits them as Markdown.
3. `remark-math` runs in the Markdown stage. It recognizes inline and block math
   such as `$...$` and `$$...$$`.
4. The pipeline converts Markdown syntax nodes into an HTML syntax tree.
5. `rehype-raw` runs in the HTML stage. It parses PaddleOCR raw HTML tables,
   divs, and images into real HTML nodes instead of escaping them as text.
6. `rehype-mathjax` runs in the HTML stage. It renders math nodes produced by
   `remark-math` into browser-displayable formula markup.
7. `react-markdown` renders React elements, using custom components for images,
   tables, and links.

Prefer MathJax over KaTeX for the first pass because OCR math may be malformed or
broader than the KaTeX-supported subset. This reviewer values tolerant rendering
over maximum render speed.

The app should document that `rehype-raw` is acceptable because this is a local
developer/reviewer tool reading artifacts from our own pipeline. It must not be
exposed as a public web service without revisiting sanitization.

## Asset Resolution

Build an asset map per page:

```text
asset_uri -> browser-loadable local_url
object_key -> browser-loadable local_url
source_path -> browser-loadable source URL when available
```

`AssetImage` uses that map for all image nodes, whether they came from Markdown
image syntax or raw HTML `<img>` tags. Resolution order:

1. Exact `asset_uri` match.
2. Exact `object_key` match.
3. Exact `source_path` match.
4. Existing browser-loadable absolute or relative URL.
5. Broken-image fallback with the unresolved source displayed.

This component is preferred over text-only pre-render replacement because it
centralizes broken-image handling and lets Markdown images and raw HTML images
share one path.

## Raw Markdown Fallback

The Markdown pane has two explicit tabs:

- `Rendered`: default rendered view.
- `Raw Markdown`: monospace source view with preserved whitespace and copyable
  text.

If rendering throws, `ErrorBoundary` should show a render error summary and keep
the raw tab available. The selected page should remain usable and the sidebar
should still allow moving to other pages.

Recoverable problems, such as an unresolved image or a math expression that
renders as source text, should appear as inline warnings rather than crashing the
page.

## Layout

Use the approved split-view layout:

- Compact document header with document id and page navigation context.
- Left sidebar with page list and per-page status signals.
- Main page area with selected page metadata.
- Two-pane comparison:
  - Left: source PDF page image, constrained with `object-fit: contain`.
  - Right: Markdown pane with `Rendered` and `Raw Markdown` tabs.
- Asset and decision metadata below the panes.

Desktop layout uses a two-column grid for the comparison panes. Narrow screens
stack the source image above the Markdown pane. Wide tables in the Markdown pane
scroll horizontally inside the pane instead of widening the whole app.

## Serving And Paths

The initial reviewer is local-only and should be served from the repository
root. This lets the app load:

- Source page images from `/runs/...`.
- Published Markdown and assets from `/object_store/...`.
- The generated manifest from the reviewer output path.

The manifest writer keeps both values when useful:

- `source_page_image_path`: original path from `decision.json`, shown to users.
- `source_page_image_url`: repo-root-relative browser URL, used by `<img>`.
- `local_path`: original or object-store path for asset metadata.
- `local_url`: repo-root-relative browser URL, used by `AssetImage`.

If this later becomes a hosted app, only this path translation layer should need
to change.

## Python Integration

Add a focused manifest writer in `pdf_extract/reconciled_viewer.py`, rather
than continuing to grow `reconciled_prototype.py`.

Responsibilities:

1. Read page rows from `PageCatalog`.
2. Read `decision.json` and `assets.json` through `LocalObjectStore`.
3. Resolve `source_refs.page_image`.
4. Resolve each asset `object_key` to both a local path and a repo-root-relative
   browser URL under the object-store root.
5. Include page metadata and Markdown text.
6. Write `viewer-manifest.json` to the reviewer output directory.

The existing prototype command can gain a mode or replacement function that
publishes the three test pages, writes the manifest, and points the user to the
React reviewer.

## Testing

Python tests:

- Manifest includes pages 1, 2, and 40 in order.
- Manifest includes source page image paths from `decision.json`.
- Page 40 includes asset records with `asset_uri`, `object_key`, `local_path`,
  content type, byte size, and checksum.
- Manifest preserves `markdown_text` with `asset://` links.

Frontend tests:

- `MarkdownPane` renders raw HTML tables.
- `MarkdownPane` renders GFM pipe tables.
- Math input renders through the configured math plugin or remains visible with
  a warning.
- `AssetImage` resolves `asset://` links from the page asset map.
- Broken image sources show a useful fallback instead of a blank pane.
- Raw Markdown tab always displays the original source.
- Render errors are caught and do not break page navigation.

Manual verification:

- Generate the three-page prototype for pages 1, 2, and 40.
- Start the React reviewer locally.
- Verify page 1 and page 2 show source images and rendered text.
- Verify page 40 shows source image, rendered raw HTML tables, math, and three
  resolved image assets.
- Toggle page 40 between `Rendered` and `Raw Markdown`.

## References

- `react-markdown`: CommonMark rendering with remark/rehype plugin support,
  https://github.com/remarkjs/react-markdown
- `remark-gfm`: GitHub-flavored Markdown tables and related extensions,
  https://github.com/remarkjs/remark-gfm
- `remark-math`: Markdown math syntax recognition,
  https://github.com/remarkjs/remark-math
- `rehype-raw`: raw HTML parsing for trusted Markdown,
  https://github.com/rehypejs/rehype-raw
- `rehype-mathjax`: math rendering in the HTML stage,
  https://github.com/remarkjs/remark-math
