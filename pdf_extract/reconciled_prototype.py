from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from .reconciled_store import (
    LocalObjectStore,
    PageCatalog,
    PageReconciliationResult,
    ReconciledPagePublisher,
    assemble_document,
)
from .render import page_dir_name


def build_prototype_result(run_root: Path, page: int) -> PageReconciliationResult:
    page_label = page_dir_name(page)
    union_page_dir = run_root / "union" / "pages" / page_label
    small_page_dir = run_root / "small" / "pages" / page_label
    union_markdown_path = union_page_dir / "output.md"
    small_markdown_path = small_page_dir / "output.md"
    union_markdown = union_markdown_path.read_text(encoding="utf-8")
    small_markdown = small_markdown_path.read_text(encoding="utf-8")
    if "imgs/" in union_markdown:
        markdown = union_markdown
        winner = "union"
        asset_base_dir = union_page_dir
    else:
        markdown = union_markdown if union_markdown.strip() else small_markdown
        winner = "union" if union_markdown.strip() else "small"
        asset_base_dir = union_page_dir if union_markdown.strip() else small_page_dir
    return PageReconciliationResult(
        document_id=run_root.name,
        page=page,
        reconciled_markdown=markdown,
        winner=winner,
        warnings=[],
        needs_human_review=False,
        model="prototype-no-llm",
        prompt_version="prototype-page-v1",
        source_refs={
            "page_image": (union_page_dir / "page.png").as_posix(),
            "union_markdown": union_markdown_path.as_posix(),
            "small_markdown": small_markdown_path.as_posix(),
            "asset_base_dir": asset_base_dir.as_posix(),
        },
    )


def write_static_viewer(
    *,
    catalog: PageCatalog,
    store: LocalObjectStore,
    document_id: str,
    viewer_dir: Path,
) -> Path:
    rows = catalog.list_pages(document_id)
    viewer_dir.mkdir(parents=True, exist_ok=True)
    page_items: list[str] = []
    page_sections: list[str] = []
    for row in rows:
        page = int(row["page"])
        markdown = row["markdown_text"] or ""
        assets = {"assets": []}
        if row["assets_key"]:
            assets = json.loads(store.read_text(row["assets_key"]))
        page_items.append(
            f'<li><a href="#page-{page}">Page {page}</a> '
            f'<span>{html.escape(row["status"])}</span></li>'
        )
        asset_items_list: list[str] = []
        for asset in assets["assets"]:
            asset_items_list.append(
                "<li>"
                f"<strong>URI:</strong> {html.escape(asset['asset_uri'])}<br>"
                f"<strong>Description:</strong> {html.escape(asset['description'])}<br>"
                f"<strong>Content Type:</strong> {html.escape(asset['content_type'])}<br>"
                f"<strong>Byte Size:</strong> {asset['byte_size']}<br>"
                f"<strong>SHA256:</strong> {html.escape(asset['sha256'])}"
                "</li>"
            )
        asset_items = "".join(asset_items_list)
        page_sections.append(
            f'<section id="page-{page}">'
            f'<h2>Page {page}</h2>'
            f'<p>Status: {html.escape(row["status"])} | '
            f'Warnings: {row["warning_count"]} | Assets: {row["asset_count"]}</p>'
            f'<pre>{html.escape(markdown)}</pre>'
            f'<h3>Assets</h3><ul>{asset_items}</ul>'
            f'<p><code>{html.escape(row["decision_key"] or "")}</code></p>'
            f'</section>'
        )
    html_text = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>Reconciled Page Viewer</title>"
        "<style>body{font-family:sans-serif;margin:2rem;}"
        "pre{white-space:pre-wrap;border:1px solid #ddd;padding:1rem;}"
        "section{border-top:1px solid #ccc;margin-top:2rem;padding-top:1rem;}"
        "</style></head><body>"
        f"<h1>{html.escape(document_id)}</h1>"
        f"<ul>{''.join(page_items)}</ul>"
        f"{''.join(page_sections)}"
        "</body></html>"
    )
    index_path = viewer_dir / "index.html"
    index_path.write_text(html_text, encoding="utf-8")
    return index_path


def run_three_page_prototype(
    *,
    run_root: Path,
    object_store_root: Path,
    sqlite_path: Path,
    viewer_dir: Path,
    pages: list[int] | None = None,
) -> dict[str, Any]:
    selected_pages = pages or [1, 2, 40]
    store = LocalObjectStore(object_store_root)
    catalog = PageCatalog(sqlite_path)
    publisher = ReconciledPagePublisher(store=store, catalog=catalog)
    published_pages: list[int] = []
    for page in selected_pages:
        result = build_prototype_result(run_root, page)
        asset_base_dir = Path(result.source_refs["asset_base_dir"])
        published = publisher.publish(result, asset_base_dir=asset_base_dir)
        if published.status == "published":
            published_pages.append(page)
    assembly = assemble_document(
        document_id=run_root.name,
        store=store,
        catalog=catalog,
        expected_pages=selected_pages,
    )
    viewer_path = write_static_viewer(
        catalog=catalog,
        store=store,
        document_id=run_root.name,
        viewer_dir=viewer_dir,
    )
    return {
        "document_id": run_root.name,
        "published_pages": published_pages,
        "assembly": assembly,
        "viewer_path": viewer_path.as_posix(),
    }
