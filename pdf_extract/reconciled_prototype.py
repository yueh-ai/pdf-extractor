from __future__ import annotations

from pathlib import Path
from typing import Any

from .reconciled_store import (
    LocalObjectStore,
    PageCatalog,
    PageReconciliationResult,
    ReconciledPagePublisher,
    assemble_document,
)
from .reconciled_viewer import write_viewer_manifest
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
