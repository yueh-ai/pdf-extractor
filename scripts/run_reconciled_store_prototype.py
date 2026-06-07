from __future__ import annotations

import argparse
import json
from pathlib import Path

from pdf_extract.reconciled_prototype import run_three_page_prototype


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish a three-page reconciled store prototype.")
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path("runs/Full_30015375000000"),
        help="Document run root containing union/ and small/ directories.",
    )
    parser.add_argument(
        "--object-store-root",
        type=Path,
        default=Path("object_store"),
        help="Local fake-S3 root.",
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=Path("reconciled_catalog.sqlite"),
        help="SQLite catalog path.",
    )
    parser.add_argument(
        "--viewer-dir",
        type=Path,
        default=Path("runs/Full_30015375000000/reconciled_viewer"),
        help="Directory for static viewer files.",
    )
    parser.add_argument(
        "--pages",
        default="1,2,40",
        help="Comma-separated page numbers to publish.",
    )
    args = parser.parse_args()
    pages = [int(part) for part in args.pages.split(",") if part.strip()]
    result = run_three_page_prototype(
        run_root=args.run_root,
        object_store_root=args.object_store_root,
        sqlite_path=args.sqlite_path,
        viewer_dir=args.viewer_dir,
        pages=pages,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
