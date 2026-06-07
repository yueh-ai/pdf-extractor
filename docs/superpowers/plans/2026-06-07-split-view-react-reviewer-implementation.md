# Split-View React Reviewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only React reviewer that compares source page images with rendered reconciled Markdown, including raw HTML tables, math, image assets, and a raw Markdown fallback.

**Architecture:** Keep Python responsible for publishing artifacts and generating a `viewer-manifest.json`. Add a focused Vite + React app under `reviewer/` that reads the manifest, renders one selected page at a time, and resolves `asset://` image links through page asset metadata. Serve the built app from the repository root so `/runs/...` and `/object_store/...` URLs are browser-loadable.

**Tech Stack:** Python 3.10+, pytest, Vite 8, React 19, TypeScript, Vitest, React Testing Library, `react-markdown`, `remark-gfm`, `remark-math`, `rehype-raw`, `rehype-mathjax`.

---

## File Structure

- Create `pdf_extract/reconciled_viewer.py`: manifest writer and path-to-browser-url helpers.
- Modify `pdf_extract/reconciled_prototype.py`: replace the old static HTML viewer call with manifest generation.
- Modify `scripts/run_reconciled_store_prototype.py`: keep CLI shape, clarify output is a React reviewer manifest.
- Create `tests/test_reconciled_viewer.py`: focused Python manifest tests.
- Modify `tests/test_reconciled_prototype.py`: assert `viewer-manifest.json` is generated.
- Create `reviewer/`: Vite + React app.
- Create `reviewer/src/manifest.ts`: manifest types and loader.
- Create `reviewer/src/assetResolver.ts`: asset URL mapping.
- Create `reviewer/src/MarkdownPane.tsx`: rendered/raw Markdown pane.
- Create `reviewer/src/ErrorBoundary.tsx`: render failure isolation.
- Create `reviewer/src/PageSidebar.tsx`, `SourcePagePane.tsx`, `MetadataPanel.tsx`, `App.tsx`: read-only layout.
- Create frontend tests under `reviewer/src/*.test.tsx`.

## Task 1: Python Viewer Manifest Writer

**Files:**
- Create: `pdf_extract/reconciled_viewer.py`
- Create: `tests/test_reconciled_viewer.py`

- [ ] **Step 1: Write failing manifest tests**

Create `tests/test_reconciled_viewer.py`:

```python
import json

from pdf_extract.reconciled_store import (
    LocalObjectStore,
    PageCatalog,
    PageReconciliationResult,
    ReconciledPagePublisher,
)
from pdf_extract.reconciled_viewer import repo_url_for_path, write_viewer_manifest


def make_result(markdown: str, page: int = 40) -> PageReconciliationResult:
    return PageReconciliationResult(
        document_id="Full_30015375000000",
        page=page,
        reconciled_markdown=markdown,
        winner="union",
        warnings=["check render"],
        needs_human_review=True,
        model="prototype-no-llm",
        prompt_version="prototype-page-v1",
        source_refs={
            "page_image": f"runs/Full_30015375000000/union/pages/page_{page:04d}/page.png",
            "union_markdown": f"runs/Full_30015375000000/union/pages/page_{page:04d}/output.md",
            "small_markdown": f"runs/Full_30015375000000/small/pages/page_{page:04d}/output.md",
        },
    )


def test_repo_url_for_path_requires_path_inside_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inside = repo_root / "runs" / "doc" / "page.png"
    inside.parent.mkdir(parents=True)
    inside.write_bytes(b"png")

    assert repo_url_for_path(inside, repo_root=repo_root) == "/runs/doc/page.png"


def test_write_viewer_manifest_includes_page_image_markdown_and_asset_urls(tmp_path):
    repo_root = tmp_path / "repo"
    run_page = repo_root / "runs" / "Full_30015375000000" / "union" / "pages" / "page_0040"
    (run_page / "imgs").mkdir(parents=True)
    (run_page / "page.png").write_bytes(b"png")
    (run_page / "imgs" / "seal.jpg").write_bytes(b"jpeg")

    store = LocalObjectStore(repo_root / "object_store")
    catalog = PageCatalog(repo_root / "catalog.sqlite")
    publisher = ReconciledPagePublisher(store=store, catalog=catalog)
    publisher.publish(
        make_result('<table><tr><td>A</td></tr></table><img src="imgs/seal.jpg" />'),
        asset_base_dir=run_page,
    )

    manifest_path = write_viewer_manifest(
        catalog=catalog,
        store=store,
        document_id="Full_30015375000000",
        viewer_dir=repo_root / "runs" / "Full_30015375000000" / "reconciled_viewer",
        repo_root=repo_root,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["document_id"] == "Full_30015375000000"
    assert manifest["pages"][0]["page"] == 40
    assert manifest["pages"][0]["status"] == "published"
    assert manifest["pages"][0]["needs_human_review"] is True
    assert manifest["pages"][0]["warning_count"] == 1
    assert manifest["pages"][0]["source_page_image_path"].endswith("page_0040/page.png")
    assert manifest["pages"][0]["source_page_image_url"] == "/runs/Full_30015375000000/union/pages/page_0040/page.png"
    assert manifest["pages"][0]["markdown_url"].startswith("/object_store/")
    assert "asset://pdf-extract/reconciled" in manifest["pages"][0]["markdown_text"]
    asset = manifest["pages"][0]["assets"][0]
    assert asset["asset_uri"].startswith("asset://pdf-extract/reconciled/")
    assert asset["object_key"].endswith("/assets/seal.jpg")
    assert asset["local_path"].endswith("object_store/pdf-extract/reconciled/Full_30015375000000/pages/page_0040/assets/seal.jpg")
    assert asset["local_url"] == "/object_store/pdf-extract/reconciled/Full_30015375000000/pages/page_0040/assets/seal.jpg"
    assert asset["content_type"] == "image/jpeg"
    assert asset["byte_size"] == 4
    assert asset["sha256"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_reconciled_viewer.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'pdf_extract.reconciled_viewer'`.

- [ ] **Step 3: Implement manifest writer**

Create `pdf_extract/reconciled_viewer.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .reconciled_store import LocalObjectStore, PageCatalog, utc_now_iso


def repo_url_for_path(path: Path | str, *, repo_root: Path) -> str:
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = repo_root / resolved
    relative = resolved.resolve().relative_to(repo_root.resolve())
    return "/" + relative.as_posix()


def object_key_local_path(store: LocalObjectStore, object_key: str) -> Path:
    return store.path_for_key(object_key)


def _read_json(store: LocalObjectStore, key: str | None) -> dict[str, Any]:
    if not key:
        return {}
    return json.loads(store.read_text(key))


def _asset_with_urls(asset: dict[str, Any], *, store: LocalObjectStore, repo_root: Path) -> dict[str, Any]:
    object_key = asset["object_key"]
    local_path = object_key_local_path(store, object_key)
    enriched = dict(asset)
    enriched["local_path"] = local_path.as_posix()
    enriched["local_url"] = repo_url_for_path(local_path, repo_root=repo_root)
    return enriched


def build_viewer_manifest(
    *,
    catalog: PageCatalog,
    store: LocalObjectStore,
    document_id: str,
    repo_root: Path,
) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    for row in catalog.list_pages(document_id):
        decision = _read_json(store, row["decision_key"])
        assets_payload = _read_json(store, row["assets_key"])
        markdown_path = object_key_local_path(store, row["markdown_key"]) if row["markdown_key"] else None
        page_image_path = decision.get("source_refs", {}).get("page_image", "")
        page_payload = {
            "page": int(row["page"]),
            "status": row["status"],
            "needs_human_review": bool(row["needs_human_review"]),
            "warning_count": int(row["warning_count"]),
            "asset_count": int(row["asset_count"]),
            "markdown_key": row["markdown_key"],
            "decision_key": row["decision_key"],
            "assets_key": row["assets_key"],
            "markdown_path": markdown_path.as_posix() if markdown_path else None,
            "markdown_url": repo_url_for_path(markdown_path, repo_root=repo_root) if markdown_path else None,
            "source_page_image_path": page_image_path,
            "source_page_image_url": repo_url_for_path(page_image_path, repo_root=repo_root) if page_image_path else None,
            "markdown_sha256": row["markdown_sha256"],
            "markdown_text": row["markdown_text"] or "",
            "error_message": row["error_message"],
            "decision": decision,
            "assets": [
                _asset_with_urls(asset, store=store, repo_root=repo_root)
                for asset in assets_payload.get("assets", [])
            ],
        }
        pages.append(page_payload)
    return {
        "document_id": document_id,
        "generated_at": utc_now_iso(),
        "pages": pages,
    }


def write_viewer_manifest(
    *,
    catalog: PageCatalog,
    store: LocalObjectStore,
    document_id: str,
    viewer_dir: Path,
    repo_root: Path,
) -> Path:
    viewer_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_viewer_manifest(
        catalog=catalog,
        store=store,
        document_id=document_id,
        repo_root=repo_root,
    )
    manifest_path = viewer_dir / "viewer-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/test_reconciled_viewer.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf_extract/reconciled_viewer.py tests/test_reconciled_viewer.py
git commit -m "Add reconciled viewer manifest writer"
```

## Task 2: Wire Prototype To Manifest Generation

**Files:**
- Modify: `pdf_extract/reconciled_prototype.py`
- Modify: `tests/test_reconciled_prototype.py`
- Modify: `scripts/run_reconciled_store_prototype.py`

- [ ] **Step 1: Update failing prototype test**

In `tests/test_reconciled_prototype.py`, replace the old HTML assertions at the end of
`test_three_page_prototype_publishes_assembles_and_writes_viewer` with:

```python
    assert (tmp_path / "viewer" / "viewer-manifest.json").is_file()
    assert result["viewer_manifest_path"].endswith("viewer/viewer-manifest.json")

    viewer_manifest = json.loads((tmp_path / "viewer" / "viewer-manifest.json").read_text(encoding="utf-8"))
    assert [page["page"] for page in viewer_manifest["pages"]] == [1, 2, 40]
    page_40 = viewer_manifest["pages"][2]
    assert page_40["source_page_image_url"].endswith("/runs/Full_30015375000000/union/pages/page_0040/page.png")
    assert page_40["assets"][0]["asset_uri"] == (
        "asset://pdf-extract/reconciled/Full_30015375000000/pages/page_0040/assets/seal.jpg"
    )
    assert page_40["assets"][0]["local_url"].endswith(
        "/object_store/pdf-extract/reconciled/Full_30015375000000/pages/page_0040/assets/seal.jpg"
    )
    assert "Description:" not in json.dumps(viewer_manifest)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_reconciled_prototype.py -q
```

Expected: FAIL because `viewer-manifest.json` and `viewer_manifest_path` are not produced yet.

- [ ] **Step 3: Update prototype implementation**

In `pdf_extract/reconciled_prototype.py`, remove imports of `html` and `json`, delete `write_static_viewer`, import `write_viewer_manifest`, and update `run_three_page_prototype`:

```python
from .reconciled_viewer import write_viewer_manifest
```

Replace the viewer call near the end with:

```python
    repo_root = run_root.resolve().parent.parent
    viewer_manifest_path = write_viewer_manifest(
        catalog=catalog,
        store=store,
        document_id=run_root.name,
        viewer_dir=viewer_dir,
        repo_root=repo_root,
    )
    return {
        "document_id": run_root.name,
        "published_pages": published_pages,
        "assembly": assembly,
        "viewer_manifest_path": viewer_manifest_path.as_posix(),
        "viewer_url_path": f"/{viewer_manifest_path.resolve().relative_to(repo_root.resolve()).as_posix()}",
    }
```

- [ ] **Step 4: Clarify CLI output**

In `scripts/run_reconciled_store_prototype.py`, change the parser description to:

```python
parser = argparse.ArgumentParser(description="Publish reconciled prototype pages and write a React reviewer manifest.")
```

Change the `--viewer-dir` help text to:

```python
help="Directory for viewer-manifest.json.",
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run pytest tests/test_reconciled_viewer.py tests/test_reconciled_prototype.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pdf_extract/reconciled_prototype.py scripts/run_reconciled_store_prototype.py tests/test_reconciled_prototype.py
git commit -m "Write React reviewer manifest from prototype"
```

## Task 3: Scaffold Vite React Reviewer

**Files:**
- Create: `reviewer/package.json`
- Create: `reviewer/index.html`
- Create: `reviewer/vite.config.ts`
- Create: `reviewer/tsconfig.json`
- Create: `reviewer/src/test/setup.ts`
- Create: `reviewer/src/main.tsx`
- Create: `reviewer/src/styles.css`

- [ ] **Step 1: Create package and config files**

Create `reviewer/package.json`:

```json
{
  "name": "pdf-extract-reviewer",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc -b && vite build",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^6.0.2",
    "vite": "^8.0.16",
    "typescript": "^6.0.3",
    "react": "^19.2.7",
    "react-dom": "^19.2.7",
    "@types/react": "^19.2.17",
    "@types/react-dom": "^19.2.3",
    "react-markdown": "^10.1.0",
    "remark-gfm": "^4.0.1",
    "remark-math": "^6.0.0",
    "rehype-raw": "^7.0.0",
    "rehype-mathjax": "^7.1.0"
  },
  "devDependencies": {
    "vitest": "^4.1.8",
    "@testing-library/react": "^16.3.2",
    "@testing-library/jest-dom": "^6.9.1",
    "jsdom": "^29.1.1"
  }
}
```

Create `reviewer/vite.config.ts`:

```ts
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
});
```

Create `reviewer/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "useDefineForClassFields": true,
    "lib": ["DOM", "DOM.Iterable", "ES2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": []
}
```

Create `reviewer/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>PDF Extract Reviewer</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

Create `reviewer/src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest';
```

Create `reviewer/src/main.tsx`:

```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import { App } from './App';

createRoot(document.getElementById('root') as HTMLElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

Create `reviewer/src/styles.css` with an empty shell so imports resolve:

```css
:root {
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: #182230;
  background: #f6f7f9;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}
```

- [ ] **Step 2: Install dependencies**

Run:

```bash
cd reviewer
npm install
```

Expected: `package-lock.json` is created and npm reports installed packages with no fatal errors.

- [ ] **Step 3: Build should fail until App exists**

Run:

```bash
cd reviewer
npm run build
```

Expected: FAIL because `src/App.tsx` does not exist.

- [ ] **Step 4: Add temporary App to make scaffold compile**

Create `reviewer/src/App.tsx`:

```tsx
export function App() {
  return <main>PDF Extract Reviewer</main>;
}
```

- [ ] **Step 5: Verify scaffold**

Run:

```bash
cd reviewer
npm run build
npm test
```

Expected: build PASS and Vitest reports no test files or no failed tests.

- [ ] **Step 6: Commit**

```bash
git add reviewer
git commit -m "Scaffold React reviewer app"
```

## Task 4: Manifest Types And Asset Resolution

**Files:**
- Create: `reviewer/src/manifest.ts`
- Create: `reviewer/src/assetResolver.ts`
- Create: `reviewer/src/assetResolver.test.ts`

- [ ] **Step 1: Write asset resolver tests**

Create `reviewer/src/assetResolver.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { buildAssetMap, resolveAssetUrl } from './assetResolver';
import type { ViewerPage } from './manifest';

const page: ViewerPage = {
  page: 40,
  status: 'published',
  needs_human_review: false,
  warning_count: 0,
  asset_count: 1,
  markdown_key: 'pdf-extract/reconciled/doc/pages/page_0040/output.md',
  decision_key: 'pdf-extract/reconciled/doc/pages/page_0040/decision.json',
  assets_key: 'pdf-extract/reconciled/doc/pages/page_0040/assets.json',
  markdown_path: 'object_store/pdf-extract/reconciled/doc/pages/page_0040/output.md',
  markdown_url: '/object_store/pdf-extract/reconciled/doc/pages/page_0040/output.md',
  source_page_image_path: 'runs/doc/union/pages/page_0040/page.png',
  source_page_image_url: '/runs/doc/union/pages/page_0040/page.png',
  markdown_sha256: 'abc',
  markdown_text: '<img src="asset://pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg" />',
  error_message: null,
  decision: { source_refs: {} },
  assets: [
    {
      asset_uri: 'asset://pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
      object_key: 'pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
      local_path: 'object_store/pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
      local_url: '/object_store/pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
      source_path: 'runs/doc/union/pages/page_0040/imgs/seal.jpg',
      description: 'seal',
      content_type: 'image/jpeg',
      sha256: 'hash',
      byte_size: 4,
    },
  ],
};

describe('assetResolver', () => {
  it('resolves asset uri, object key, and source path through the page asset map', () => {
    const map = buildAssetMap(page);
    expect(resolveAssetUrl('asset://pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg', map)).toBe(
      '/object_store/pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
    );
    expect(resolveAssetUrl('pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg', map)).toBe(
      '/object_store/pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
    );
    expect(resolveAssetUrl('runs/doc/union/pages/page_0040/imgs/seal.jpg', map)).toBe(
      '/object_store/pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
    );
  });

  it('passes through existing browser URLs and marks unresolved values', () => {
    const map = buildAssetMap(page);
    expect(resolveAssetUrl('/runs/doc/page.png', map)).toBe('/runs/doc/page.png');
    expect(resolveAssetUrl('https://example.test/image.jpg', map)).toBe('https://example.test/image.jpg');
    expect(resolveAssetUrl('missing.jpg', map)).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd reviewer
npm test -- assetResolver.test.ts
```

Expected: FAIL because `manifest.ts` and `assetResolver.ts` do not exist.

- [ ] **Step 3: Implement manifest types**

Create `reviewer/src/manifest.ts`:

```ts
export type ViewerAsset = {
  asset_uri: string;
  object_key: string;
  local_path: string;
  local_url: string;
  source_path: string;
  description: string;
  content_type: string;
  sha256: string;
  byte_size: number;
};

export type ViewerPage = {
  page: number;
  status: string;
  needs_human_review: boolean;
  warning_count: number;
  asset_count: number;
  markdown_key: string | null;
  decision_key: string | null;
  assets_key: string | null;
  markdown_path: string | null;
  markdown_url: string | null;
  source_page_image_path: string | null;
  source_page_image_url: string | null;
  markdown_sha256: string | null;
  markdown_text: string;
  error_message: string | null;
  decision: Record<string, unknown>;
  assets: ViewerAsset[];
};

export type ViewerManifest = {
  document_id: string;
  generated_at: string;
  pages: ViewerPage[];
};

export function manifestUrlFromLocation(locationSearch = window.location.search): string {
  const params = new URLSearchParams(locationSearch);
  return params.get('manifest') ?? '/runs/Full_30015375000000/reconciled_viewer/viewer-manifest.json';
}

export async function loadManifest(url = manifestUrlFromLocation()): Promise<ViewerManifest> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load viewer manifest: ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as ViewerManifest;
}
```

- [ ] **Step 4: Implement asset resolver**

Create `reviewer/src/assetResolver.ts`:

```ts
import type { ViewerPage } from './manifest';

export type AssetMap = Map<string, string>;

export function buildAssetMap(page: ViewerPage): AssetMap {
  const map = new Map<string, string>();
  for (const asset of page.assets) {
    map.set(asset.asset_uri, asset.local_url);
    map.set(asset.object_key, asset.local_url);
    map.set(asset.source_path, asset.local_url);
  }
  return map;
}

export function resolveAssetUrl(src: string | undefined, assetMap: AssetMap): string | null {
  if (!src) {
    return null;
  }
  const mapped = assetMap.get(src);
  if (mapped) {
    return mapped;
  }
  if (
    src.startsWith('/') ||
    src.startsWith('http://') ||
    src.startsWith('https://') ||
    src.startsWith('data:')
  ) {
    return src;
  }
  return null;
}
```

- [ ] **Step 5: Verify resolver tests**

Run:

```bash
cd reviewer
npm test -- assetResolver.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add reviewer/src/manifest.ts reviewer/src/assetResolver.ts reviewer/src/assetResolver.test.ts
git commit -m "Add reviewer manifest and asset resolution"
```

## Task 5: Markdown Pane With Rendered And Raw Modes

**Files:**
- Create: `reviewer/src/ErrorBoundary.tsx`
- Create: `reviewer/src/MarkdownPane.tsx`
- Create: `reviewer/src/MarkdownPane.test.tsx`

- [ ] **Step 1: Write Markdown pane tests**

Create `reviewer/src/MarkdownPane.test.tsx`:

```tsx
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MarkdownPane } from './MarkdownPane';
import type { ViewerPage } from './manifest';

function makePage(markdown: string): ViewerPage {
  return {
    page: 40,
    status: 'published',
    needs_human_review: false,
    warning_count: 0,
    asset_count: 1,
    markdown_key: 'md',
    decision_key: 'decision',
    assets_key: 'assets',
    markdown_path: 'object_store/output.md',
    markdown_url: '/object_store/output.md',
    source_page_image_path: 'runs/page.png',
    source_page_image_url: '/runs/page.png',
    markdown_sha256: 'hash',
    markdown_text: markdown,
    error_message: null,
    decision: {},
    assets: [
      {
        asset_uri: 'asset://pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
        object_key: 'pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
        local_path: 'object_store/pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
        local_url: '/object_store/pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
        source_path: 'runs/doc/union/pages/page_0040/imgs/seal.jpg',
        description: 'seal',
        content_type: 'image/jpeg',
        sha256: 'hash',
        byte_size: 4,
      },
    ],
  };
}

describe('MarkdownPane', () => {
  it('renders raw HTML tables and resolves asset images', () => {
    render(
      <MarkdownPane
        page={makePage('<table><tr><td>Lease Line</td></tr></table><img src="asset://pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg" alt="Seal" />')}
      />,
    );

    expect(screen.getByRole('cell', { name: 'Lease Line' })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Seal' })).toHaveAttribute(
      'src',
      '/object_store/pdf-extract/reconciled/doc/pages/page_0040/assets/seal.jpg',
    );
  });

  it('renders GFM pipe tables', () => {
    render(<MarkdownPane page={makePage('| MD | TVD |\\n|---:|---:|\\n| 5669 | 5667 |')} />);

    expect(screen.getByRole('columnheader', { name: 'MD' })).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: '5669' })).toBeInTheDocument();
  });

  it('keeps raw markdown available', () => {
    const markdown = 'Dip Angle: $60.02^{\\\\circ}$';
    render(<MarkdownPane page={makePage(markdown)} />);

    fireEvent.click(screen.getByRole('tab', { name: 'Raw Markdown' }));
    expect(screen.getByText(markdown)).toBeInTheDocument();
  });

  it('shows unresolved image fallback', () => {
    render(<MarkdownPane page={makePage('<img src="missing.jpg" alt="Missing seal" />')} />);

    const fallback = screen.getByText(/Unresolved image/);
    expect(within(fallback.closest('.image-fallback') as HTMLElement).getByText('missing.jpg')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd reviewer
npm test -- MarkdownPane.test.tsx
```

Expected: FAIL because `MarkdownPane.tsx` does not exist.

- [ ] **Step 3: Implement error boundary**

Create `reviewer/src/ErrorBoundary.tsx`:

```tsx
import { Component, type ErrorInfo, type ReactNode } from 'react';

type Props = {
  children: ReactNode;
  fallback: (error: Error) => ReactNode;
};

type State = {
  error: Error | null;
};

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Markdown render failed', error, info);
  }

  render() {
    if (this.state.error) {
      return this.props.fallback(this.state.error);
    }
    return this.props.children;
  }
}
```

- [ ] **Step 4: Implement Markdown pane**

Create `reviewer/src/MarkdownPane.tsx`:

```tsx
import { useMemo, useState } from 'react';
import Markdown from 'react-markdown';
import rehypeMathjax from 'rehype-mathjax';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import { buildAssetMap, resolveAssetUrl } from './assetResolver';
import { ErrorBoundary } from './ErrorBoundary';
import type { ViewerPage } from './manifest';

type Props = {
  page: ViewerPage;
};

export function MarkdownPane({ page }: Props) {
  const [mode, setMode] = useState<'rendered' | 'raw'>('rendered');
  const assetMap = useMemo(() => buildAssetMap(page), [page]);

  return (
    <section className="markdown-pane" aria-label="Markdown output">
      <div className="pane-toolbar" role="tablist" aria-label="Markdown view mode">
        <button className={mode === 'rendered' ? 'active' : ''} role="tab" aria-selected={mode === 'rendered'} onClick={() => setMode('rendered')}>
          Rendered
        </button>
        <button className={mode === 'raw' ? 'active' : ''} role="tab" aria-selected={mode === 'raw'} onClick={() => setMode('raw')}>
          Raw Markdown
        </button>
      </div>
      {mode === 'raw' ? (
        <pre className="raw-markdown">{page.markdown_text}</pre>
      ) : (
        <ErrorBoundary
          fallback={(error) => (
            <div className="render-error">
              <strong>Render error</strong>
              <p>{error.message}</p>
              <pre className="raw-markdown">{page.markdown_text}</pre>
            </div>
          )}
        >
          <div className="rendered-markdown">
            <Markdown
              remarkPlugins={[remarkGfm, remarkMath]}
              rehypePlugins={[rehypeRaw, rehypeMathjax]}
              components={{
                img(props) {
                  const resolved = resolveAssetUrl(props.src, assetMap);
                  if (!resolved) {
                    return (
                      <span className="image-fallback">
                        Unresolved image <code>{props.src}</code>
                      </span>
                    );
                  }
                  return <img {...props} src={resolved} alt={props.alt ?? ''} />;
                },
                table(props) {
                  return (
                    <div className="table-scroll">
                      <table {...props} />
                    </div>
                  );
                },
                a(props) {
                  return <a {...props} target="_blank" rel="noreferrer" />;
                },
              }}
            >
              {page.markdown_text}
            </Markdown>
          </div>
        </ErrorBoundary>
      )}
    </section>
  );
}
```

- [ ] **Step 5: Add Markdown pane CSS**

Append to `reviewer/src/styles.css`:

```css
.markdown-pane {
  display: flex;
  min-height: 0;
  flex-direction: column;
}

.pane-toolbar {
  display: flex;
  gap: 6px;
  border-bottom: 1px solid #d0d5dd;
  padding: 8px;
}

.pane-toolbar button {
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #344054;
  padding: 6px 10px;
  border-radius: 6px;
  cursor: pointer;
}

.pane-toolbar button.active {
  background: #e8f1ff;
  border-color: #7aa7f7;
  color: #1849a9;
}

.rendered-markdown,
.raw-markdown {
  flex: 1;
  overflow: auto;
  padding: 14px;
}

.raw-markdown {
  margin: 0;
  white-space: pre-wrap;
  font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: #101828;
  color: #f9fafb;
}

.table-scroll {
  max-width: 100%;
  overflow-x: auto;
}

.rendered-markdown table {
  border-collapse: collapse;
}

.rendered-markdown td,
.rendered-markdown th {
  border: 1px solid #98a2b3;
  padding: 4px 6px;
}

.rendered-markdown img {
  max-width: 100%;
  height: auto;
}

.image-fallback,
.render-error {
  display: block;
  border: 1px solid #f79009;
  background: #fffaeb;
  color: #7a2e0e;
  padding: 8px;
  border-radius: 6px;
}
```

- [ ] **Step 6: Verify Markdown tests**

Run:

```bash
cd reviewer
npm test -- MarkdownPane.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add reviewer/src/ErrorBoundary.tsx reviewer/src/MarkdownPane.tsx reviewer/src/MarkdownPane.test.tsx reviewer/src/styles.css
git commit -m "Render reconciled markdown with raw fallback"
```

## Task 6: Read-Only Reviewer Layout

**Files:**
- Modify: `reviewer/src/App.tsx`
- Create: `reviewer/src/App.test.tsx`
- Create: `reviewer/src/PageSidebar.tsx`
- Create: `reviewer/src/SourcePagePane.tsx`
- Create: `reviewer/src/MetadataPanel.tsx`
- Modify: `reviewer/src/styles.css`

- [ ] **Step 1: Write app layout test**

Create `reviewer/src/App.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import type { ViewerManifest } from './manifest';

const manifest: ViewerManifest = {
  document_id: 'Full_30015375000000',
  generated_at: '2026-06-07T00:00:00Z',
  pages: [
    {
      page: 40,
      status: 'published',
      needs_human_review: false,
      warning_count: 0,
      asset_count: 0,
      markdown_key: 'md',
      decision_key: 'decision',
      assets_key: 'assets',
      markdown_path: 'object_store/output.md',
      markdown_url: '/object_store/output.md',
      source_page_image_path: 'runs/doc/page.png',
      source_page_image_url: '/runs/doc/page.png',
      markdown_sha256: 'hash',
      markdown_text: '# Page 40',
      error_message: null,
      decision: { winner: 'union' },
      assets: [],
    },
  ],
};

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => manifest,
      })),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('loads the manifest and shows the split reviewer', async () => {
    render(<App />);

    await waitFor(() => expect(screen.getByText('Full_30015375000000')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /Page 40/ })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: 'Source PDF page 40' })).toHaveAttribute('src', '/runs/doc/page.png');
    expect(screen.getByText('decision')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Page 40' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd reviewer
npm test -- App.test.tsx
```

Expected: FAIL because the layout components do not exist.

- [ ] **Step 3: Implement layout components**

Create `reviewer/src/PageSidebar.tsx`:

```tsx
import type { ViewerPage } from './manifest';

type Props = {
  pages: ViewerPage[];
  selectedPage: number;
  onSelectPage: (page: number) => void;
};

export function PageSidebar({ pages, selectedPage, onSelectPage }: Props) {
  return (
    <aside className="page-sidebar" aria-label="Pages">
      <div className="section-label">Pages</div>
      {pages.map((page) => (
        <button
          key={page.page}
          className={page.page === selectedPage ? 'selected' : ''}
          onClick={() => onSelectPage(page.page)}
        >
          Page {page.page} | {page.status} | assets {page.asset_count}
        </button>
      ))}
    </aside>
  );
}
```

Create `reviewer/src/SourcePagePane.tsx`:

```tsx
import type { ViewerPage } from './manifest';

export function SourcePagePane({ page }: { page: ViewerPage }) {
  return (
    <section className="pane source-pane" aria-label="Source PDF page">
      <div className="pane-title">Source PDF Page Image</div>
      {page.source_page_image_url ? (
        <img src={page.source_page_image_url} alt={`Source PDF page ${page.page}`} />
      ) : (
        <div className="image-fallback">No source page image</div>
      )}
      <div className="path-text">{page.source_page_image_path}</div>
    </section>
  );
}
```

Create `reviewer/src/MetadataPanel.tsx`:

```tsx
import type { ViewerPage } from './manifest';

export function MetadataPanel({ page }: { page: ViewerPage }) {
  return (
    <section className="metadata-panel" aria-label="Page metadata">
      <div>
        <strong>Decision</strong>
        <code>{page.decision_key}</code>
      </div>
      <div>
        <strong>Markdown</strong>
        <code>{page.markdown_key}</code>
      </div>
      <div>
        <strong>Assets</strong>
        <code>{page.assets_key}</code>
      </div>
      <ul>
        {page.assets.map((asset) => (
          <li key={asset.asset_uri}>
            <code>{asset.asset_uri}</code> | {asset.content_type} | {asset.byte_size} bytes | {asset.sha256}
          </li>
        ))}
      </ul>
    </section>
  );
}
```

- [ ] **Step 4: Implement App**

Replace `reviewer/src/App.tsx`:

```tsx
import { useEffect, useMemo, useState } from 'react';
import { MarkdownPane } from './MarkdownPane';
import { MetadataPanel } from './MetadataPanel';
import { PageSidebar } from './PageSidebar';
import { SourcePagePane } from './SourcePagePane';
import { loadManifest, type ViewerManifest } from './manifest';

export function App() {
  const [manifest, setManifest] = useState<ViewerManifest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedPage, setSelectedPage] = useState<number | null>(null);

  useEffect(() => {
    loadManifest()
      .then((loaded) => {
        setManifest(loaded);
        setSelectedPage(loaded.pages[0]?.page ?? null);
      })
      .catch((err: Error) => setError(err.message));
  }, []);

  const page = useMemo(
    () => manifest?.pages.find((candidate) => candidate.page === selectedPage) ?? null,
    [manifest, selectedPage],
  );

  if (error) {
    return <main className="app-shell"><div className="render-error">{error}</div></main>;
  }
  if (!manifest || !page) {
    return <main className="app-shell">Loading reviewer...</main>;
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <div className="section-label">Document</div>
          <h1>{manifest.document_id}</h1>
        </div>
        <div className="header-meta">Generated {manifest.generated_at}</div>
      </header>
      <div className="reviewer-grid">
        <PageSidebar pages={manifest.pages} selectedPage={page.page} onSelectPage={setSelectedPage} />
        <section className="page-review">
          <div className="page-heading">
            <div>
              <div className="section-label">Page {page.page}</div>
              <h2>Page {page.page}</h2>
            </div>
            <div className="status-line">
              {page.status} | warnings {page.warning_count} | assets {page.asset_count}
            </div>
          </div>
          <div className="split-view">
            <SourcePagePane page={page} />
            <section className="pane markdown-shell" aria-label="Rendered Markdown">
              <MarkdownPane page={page} />
            </section>
          </div>
          <MetadataPanel page={page} />
        </section>
      </div>
    </main>
  );
}
```

- [ ] **Step 5: Add layout CSS**

Append to `reviewer/src/styles.css`:

```css
.app-shell {
  min-height: 100vh;
  padding: 18px;
}

.app-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid #d0d5dd;
  padding-bottom: 12px;
  margin-bottom: 16px;
}

h1,
h2 {
  margin: 0;
}

.section-label {
  color: #667085;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.header-meta,
.status-line,
.path-text {
  color: #667085;
  font-size: 12px;
}

.reviewer-grid {
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr);
  gap: 16px;
}

.page-sidebar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border-right: 1px solid #d0d5dd;
  padding-right: 12px;
}

.page-sidebar button {
  border: 1px solid #cbd5e1;
  background: #fff;
  border-radius: 6px;
  cursor: pointer;
  padding: 8px;
  text-align: left;
}

.page-sidebar button.selected {
  background: #e8f1ff;
  border-color: #7aa7f7;
}

.page-review {
  min-width: 0;
}

.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}

.split-view {
  display: grid;
  grid-template-columns: minmax(300px, 48%) minmax(360px, 52%);
  gap: 14px;
  min-height: 70vh;
}

.pane {
  min-width: 0;
  overflow: hidden;
  border: 1px solid #d0d5dd;
  border-radius: 6px;
  background: #fff;
}

.pane-title {
  border-bottom: 1px solid #d0d5dd;
  font-weight: 700;
  padding: 8px 10px;
}

.source-pane {
  display: flex;
  flex-direction: column;
}

.source-pane img {
  flex: 1;
  min-height: 0;
  width: 100%;
  max-height: 80vh;
  object-fit: contain;
  background: #f2f4f7;
}

.path-text {
  border-top: 1px solid #d0d5dd;
  overflow-wrap: anywhere;
  padding: 8px 10px;
}

.markdown-shell {
  display: flex;
  flex-direction: column;
}

.metadata-panel {
  border-top: 1px solid #d0d5dd;
  color: #344054;
  display: grid;
  gap: 8px;
  margin-top: 12px;
  padding-top: 10px;
  font-size: 12px;
}

.metadata-panel code {
  display: block;
  overflow-wrap: anywhere;
}

@media (max-width: 900px) {
  .reviewer-grid {
    grid-template-columns: 1fr;
  }

  .page-sidebar {
    border-right: 0;
    border-bottom: 1px solid #d0d5dd;
    flex-direction: row;
    overflow-x: auto;
    padding: 0 0 12px;
  }

  .split-view {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 6: Verify app tests and build**

Run:

```bash
cd reviewer
npm test -- App.test.tsx MarkdownPane.test.tsx assetResolver.test.ts
npm run build
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add reviewer/src/App.tsx reviewer/src/App.test.tsx reviewer/src/PageSidebar.tsx reviewer/src/SourcePagePane.tsx reviewer/src/MetadataPanel.tsx reviewer/src/styles.css
git commit -m "Build read-only split-view reviewer"
```

## Task 7: End-To-End Prototype Verification

**Files:**
- Modify only if verification exposes a bug in files from earlier tasks.

- [ ] **Step 1: Run Python regression tests**

Run:

```bash
uv run pytest tests/test_reconciled_store.py tests/test_reconciled_viewer.py tests/test_reconciled_prototype.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend tests and build**

Run:

```bash
cd reviewer
npm test
npm run build
```

Expected: PASS.

- [ ] **Step 3: Regenerate real three-page prototype**

Run from repo root:

```bash
uv run python scripts/run_reconciled_store_prototype.py \
  --run-root runs/Full_30015375000000 \
  --object-store-root object_store \
  --sqlite-path reconciled_catalog.sqlite \
  --viewer-dir runs/Full_30015375000000/reconciled_viewer \
  --pages 1,2,40
```

Expected JSON includes:

```json
{
  "document_id": "Full_30015375000000",
  "published_pages": [1, 2, 40]
}
```

and a `viewer_manifest_path` ending with `runs/Full_30015375000000/reconciled_viewer/viewer-manifest.json`.

- [ ] **Step 4: Serve repo root and open reviewer**

Run from repo root:

```bash
python3 -m http.server 8765
```

Open:

```text
http://localhost:8765/reviewer/dist/index.html?manifest=/runs/Full_30015375000000/reconciled_viewer/viewer-manifest.json
```

Expected:

- Page 1, page 2, and page 40 appear in the sidebar.
- Page 40 source image appears on the left.
- Page 40 rendered Markdown appears on the right.
- Raw HTML tables render as tables.
- Inline math remains visible and renders when MathJax can parse it.
- Three image assets resolve under `/object_store/...`.
- Raw Markdown tab shows the original page Markdown.

- [ ] **Step 5: Run full test suite**

Stop the local HTTP server with `Ctrl-C`, then run:

```bash
uv run pytest -q
cd reviewer
npm test
npm run build
```

Expected: all commands PASS.

- [ ] **Step 6: Commit verification fixes if needed**

Run:

```bash
git status --short
```

Expected when no fixes were required: no source files are modified. Do not create
an empty commit.

Expected when fixes were required: `git status --short` lists the exact source
or test files changed during verification. Stage only those listed source or test
files, then commit:

```bash
git add pdf_extract/reconciled_viewer.py pdf_extract/reconciled_prototype.py tests/test_reconciled_viewer.py tests/test_reconciled_prototype.py reviewer
git commit -m "Verify split-view React reviewer"
```

## Task 8: Final Review Notes

**Files:**
- Modify: `docs/superpowers/plans/2026-06-07-split-view-react-reviewer-implementation.md` only if execution reveals plan corrections that future agents need.

- [ ] **Step 1: Check git status**

Run:

```bash
git status --short
```

Expected: only intentional generated artifacts may remain untracked, such as `object_store/`, `reconciled_catalog.sqlite`, and `runs/Full_30015375000000/reconciled_viewer/`.

- [ ] **Step 2: Summarize manual reviewer URL**

Record the final local URL in the execution handoff:

```text
http://localhost:8765/reviewer/dist/index.html?manifest=/runs/Full_30015375000000/reconciled_viewer/viewer-manifest.json
```

- [ ] **Step 3: Stop any long-running servers**

Confirm no `python3 -m http.server` or `npm run dev` session is still running unless the user explicitly asked to keep it open.
