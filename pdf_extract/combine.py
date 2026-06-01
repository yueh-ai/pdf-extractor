from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .markdown_assets import rewrite_page_local_image_paths
from .paddle_output import atomic_write_text
from .render import page_dir_name


def write_combined_outputs(
    run_dir: Path, *, ok_pages: Iterable[int], failed_pages: Iterable[int]
) -> None:
    ok_page_list = sorted(ok_pages)
    failed_page_list = sorted(failed_pages)

    md_parts: list[str] = []
    json_lines: list[str] = []

    for page in ok_page_list:
        page_dir_label = page_dir_name(page)
        page_dir = run_dir / "pages" / page_dir_label
        md_path = page_dir / "output.md"
        json_path = page_dir / "res.json"

        md_text = md_path.read_text(encoding="utf-8").strip()
        md_text = rewrite_page_local_image_paths(md_text, page_dir_label)
        md_parts.append(f"# Page {page}\n\n{md_text}\n")

        with json_path.open("r", encoding="utf-8") as handle:
            json_data = json.load(handle)
        json_lines.append(json.dumps(json_data, ensure_ascii=False))

    failed_text = "".join(f"{page}\n" for page in failed_page_list)
    atomic_write_text(run_dir / "combined.md", "\n".join(md_parts))
    atomic_write_text(
        run_dir / "combined.jsonl",
        "".join(f"{line}\n" for line in json_lines),
    )
    atomic_write_text(run_dir / "failed_pages.txt", failed_text)
