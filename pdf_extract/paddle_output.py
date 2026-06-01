from __future__ import annotations

import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_bytes(data)
    os.replace(tmp_path, path)


def _replace_file(src: Path, dest: Path) -> None:
    if not src.is_file() or src.stat().st_size == 0:
        raise RuntimeError(f"Expected non-empty generated artifact at {src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_dest = dest.with_name(f".{dest.name}.tmp")
    shutil.copyfile(src, tmp_dest)
    os.replace(tmp_dest, dest)


def _replace_tree_if_present(src: Path, dest: Path) -> None:
    if not src.exists():
        if dest.exists():
            shutil.rmtree(dest)
        return
    if not src.is_dir():
        raise RuntimeError(f"Expected generated artifact directory at {src}")

    tmp_dest = dest.with_name(f".{dest.name}.tmp")
    if tmp_dest.exists():
        shutil.rmtree(tmp_dest)
    shutil.copytree(src, tmp_dest)
    if dest.exists():
        if dest.is_dir():
            shutil.rmtree(dest)
        else:
            dest.unlink()
    os.replace(tmp_dest, dest)


@contextmanager
def _working_directory(path: Path):
    original = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)


def _call_required(result: Any, method_name: str, *args: Any, **kwargs: Any) -> None:
    method = getattr(result, method_name, None)
    if method is None:
        raise RuntimeError(f"PaddleOCR result does not provide {method_name}()")
    method(*args, **kwargs)


def save_page_result_bundle(result: Any, page_dir: Path) -> None:
    page_dir.mkdir(parents=True, exist_ok=True)
    page_dir = page_dir.resolve()

    with TemporaryDirectory(prefix=".paddleocr-", dir=page_dir) as tmp_dir_text:
        tmp_dir = Path(tmp_dir_text).resolve()

        json_path = tmp_dir / "res.json"
        md_path = tmp_dir / "output.md"
        layout_path = tmp_dir / "layout_det_res.png"

        with _working_directory(tmp_dir):
            _call_required(result, "save_to_json", json_path)
            _call_required(result, "save_to_markdown", md_path)
            _call_required(result, "save_to_img", layout_path)
            _call_required(result, "save_to_word", tmp_dir)

        docx_candidates = sorted(tmp_dir.glob("*.docx"))
        if not docx_candidates:
            raise RuntimeError("PaddleOCR result did not generate a DOCX artifact")

        _replace_file(json_path, page_dir / "res.json")
        _replace_file(md_path, page_dir / "output.md")
        _replace_file(layout_path, page_dir / "layout_det_res.png")
        _replace_file(docx_candidates[0], page_dir / "output.docx")
        _replace_tree_if_present(tmp_dir / "imgs", page_dir / "imgs")
        _replace_tree_if_present(tmp_dir / "files", page_dir / "files")
