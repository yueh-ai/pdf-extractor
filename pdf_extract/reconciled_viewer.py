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
