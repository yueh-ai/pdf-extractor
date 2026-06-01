from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .markdown_assets import iter_page_local_image_paths


REQUIRED_PAGE_ARTIFACTS = (
    "layout_det_res.png",
    "res.json",
    "output.docx",
    "output.md",
)


def page_bundle_dir(run_dir: Path, page: int) -> Path:
    return run_dir / "pages" / f"page_{page:04d}"


def append_manifest_entry(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        json.dump(entry, handle, ensure_ascii=False, sort_keys=True)
        handle.write("\n")


def load_latest_manifest(path: Path) -> dict[int, dict[str, Any]]:
    latest: dict[int, dict[str, Any]] = {}
    if not path.exists():
        return latest

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path} at line {line_number}") from exc
            page = entry.get("page")
            if not isinstance(page, int):
                raise ValueError(f"Manifest entry at line {line_number} has no integer page")
            latest[page] = entry
    return latest


def is_non_empty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _referenced_markdown_assets_exist(page_dir: Path) -> bool:
    md_path = page_dir / "output.md"
    md_text = md_path.read_text(encoding="utf-8")
    return all(
        is_non_empty_file(page_dir / image_path)
        for image_path in iter_page_local_image_paths(md_text)
    )


def is_page_complete(
    page: int,
    run_dir: Path,
    latest_manifest: dict[int, dict[str, Any]],
    *,
    require_page_image: bool,
) -> bool:
    latest = latest_manifest.get(page)
    if latest is None or latest.get("status") != "ok":
        return False

    page_dir = page_bundle_dir(run_dir, page)
    required = list(REQUIRED_PAGE_ARTIFACTS)
    if require_page_image:
        required.append("page.png")

    return all(is_non_empty_file(page_dir / name) for name in required) and (
        _referenced_markdown_assets_exist(page_dir)
    )
