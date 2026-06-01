from __future__ import annotations

import json
from pathlib import Path

from .paddle_output import atomic_write_text


VALID_RUN_MODES = ("union", "small")


def validate_run_mode(mode: str) -> str:
    if mode not in VALID_RUN_MODES:
        valid = ", ".join(VALID_RUN_MODES)
        raise ValueError(f"Invalid run mode {mode!r}; expected one of: {valid}")
    return mode


def document_run_root(input_pdf: Path, *, runs_dir: Path = Path("runs")) -> Path:
    return runs_dir / input_pdf.stem


def mode_run_dir(input_pdf: Path, mode: str, *, runs_dir: Path = Path("runs")) -> Path:
    return document_run_root(input_pdf, runs_dir=runs_dir) / validate_run_mode(mode)


def write_document_metadata(root: Path, *, input_pdf: Path, mode: str) -> Path:
    mode = validate_run_mode(mode)
    document_path = root / "document.json"
    if document_path.exists():
        document = json.loads(document_path.read_text(encoding="utf-8"))
    else:
        document = {
            "input_pdf": str(input_pdf.resolve()),
            "document_stem": input_pdf.stem,
            "modes": {},
        }

    document["input_pdf"] = str(input_pdf.resolve())
    document["document_stem"] = input_pdf.stem
    modes = document.setdefault("modes", {})
    modes[mode] = mode
    root.mkdir(parents=True, exist_ok=True)
    atomic_write_text(document_path, json.dumps(document, indent=2, sort_keys=True) + "\n")
    return document_path
