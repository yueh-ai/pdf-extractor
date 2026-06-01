#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def _display_path(path: Path, cwd: Path) -> str:
    try:
        return path.resolve().relative_to(cwd).as_posix()
    except ValueError:
        return str(path.resolve())


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=False) + "\n")


def _infer_paths(source_run_dir: Path) -> tuple[Path, Path]:
    source_name = source_run_dir.name
    if not source_name.endswith("_vl"):
        raise ValueError(f"source run directory must end with _vl: {source_run_dir}")

    document_stem = source_name[: -len("_vl")]
    document_root = source_run_dir.parent / document_stem
    union_run_dir = document_root / "union"
    return document_root, union_run_dir


def _update_config(union_run_dir: Path, cwd: Path) -> None:
    config_path = union_run_dir / "config.json"
    config = _load_json(config_path)
    if not config:
        return

    config["out"] = _display_path(union_run_dir, cwd)
    config["run_mode"] = "union"
    config["layout_merge_bboxes_mode"] = None
    _write_json(config_path, config)


def _update_document_metadata(document_root: Path, union_run_dir: Path) -> None:
    document_path = document_root / "document.json"
    config = _load_json(union_run_dir / "config.json")
    document = _load_json(document_path)

    document["document_stem"] = document_root.name
    if "input_pdf" in config:
        document["input_pdf"] = config["input_pdf"]
    else:
        document.setdefault("input_pdf", "")

    modes = document.setdefault("modes", {})
    modes["union"] = "union"
    _write_json(document_path, document)


def migrate(source_run_dir: Path, *, apply: bool, copy: bool) -> int:
    cwd = Path.cwd().resolve()
    source_run_dir = source_run_dir.expanduser()
    document_root, union_run_dir = _infer_paths(source_run_dir)

    if not source_run_dir.is_dir():
        print(f"error: source run directory does not exist: {source_run_dir}", file=sys.stderr)
        return 2
    if union_run_dir.exists():
        print(f"error: destination already exists: {union_run_dir}", file=sys.stderr)
        print("Refusing to overwrite an existing union run.", file=sys.stderr)
        return 2

    action = "copy" if copy else "move"
    print(f"source:      {_display_path(source_run_dir, cwd)}")
    print(f"destination: {_display_path(union_run_dir, cwd)}")
    print(f"action:      {action}")
    print("metadata:    set config.run_mode=union, config.out=<destination>")
    print("metadata:    add modes.union to document.json")

    if not apply:
        print("\ndry run only; re-run with --apply to migrate")
        return 0

    document_root.mkdir(parents=True, exist_ok=True)
    if copy:
        shutil.copytree(source_run_dir, union_run_dir)
    else:
        shutil.move(str(source_run_dir), str(union_run_dir))

    _update_config(union_run_dir, cwd)
    _update_document_metadata(document_root, union_run_dir)
    print("\nmigration complete")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Move a legacy runs/<pdf_stem>_vl run into runs/<pdf_stem>/union."
    )
    parser.add_argument("source_run_dir", type=Path, help="Legacy run directory ending in _vl")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually perform the migration. Without this, only prints the plan.",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy into union instead of moving the legacy directory.",
    )
    args = parser.parse_args()

    try:
        return migrate(args.source_run_dir, apply=args.apply, copy=args.copy)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
