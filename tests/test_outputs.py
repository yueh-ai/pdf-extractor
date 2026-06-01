import json
from pathlib import Path

from pdf_extract.combine import write_combined_outputs
from pdf_extract.paddle_output import (
    atomic_write_bytes,
    atomic_write_text,
    save_page_result_bundle,
)


class FakePaddleResult:
    def save_to_json(self, path):
        atomic_write_text(path, '{"ok": true}')

    def save_to_markdown(self, path):
        atomic_write_text(path, "markdown")

    def save_to_img(self, path):
        atomic_write_bytes(path, b"\x89PNG\r\n\x1a\nimage")

    def save_to_word(self, path):
        atomic_write_bytes(path / "page.docx", b"docx")


class SideEffectPaddleResult(FakePaddleResult):
    def save_to_markdown(self, path):
        super().save_to_markdown(path)
        Path("files").mkdir()
        atomic_write_bytes(Path("files") / "asset.bin", b"asset")


class MarkdownImagePaddleResult(FakePaddleResult):
    def save_to_markdown(self, path):
        atomic_write_text(
            path,
            '<div><img src="imgs/picture.jpg" alt="Image" /></div>',
        )
        Path("imgs").mkdir()
        atomic_write_bytes(Path("imgs") / "picture.jpg", b"jpeg")


def test_atomic_writes_create_files(tmp_path):
    atomic_write_text(tmp_path / "a.txt", "hello")
    atomic_write_bytes(tmp_path / "b.bin", b"world")

    assert (tmp_path / "a.txt").read_text(encoding="utf-8") == "hello"
    assert (tmp_path / "b.bin").read_bytes() == b"world"


def test_save_page_result_bundle_normalizes_paddle_outputs(tmp_path):
    save_page_result_bundle(FakePaddleResult(), tmp_path)

    assert (tmp_path / "res.json").read_text(encoding="utf-8") == '{"ok": true}'
    assert (tmp_path / "output.md").read_text(encoding="utf-8") == "markdown"
    assert (tmp_path / "layout_det_res.png").read_bytes().startswith(b"\x89PNG")
    assert (tmp_path / "output.docx").read_bytes() == b"docx"


def test_save_page_result_bundle_contains_files_side_effects(tmp_path, monkeypatch):
    work_dir = tmp_path / "work"
    page_dir = tmp_path / "page"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)

    save_page_result_bundle(SideEffectPaddleResult(), page_dir)

    assert not (work_dir / "files").exists()
    assert (page_dir / "files" / "asset.bin").read_bytes() == b"asset"


def test_save_page_result_bundle_contains_markdown_image_assets(tmp_path, monkeypatch):
    work_dir = tmp_path / "work"
    page_dir = tmp_path / "page"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)

    save_page_result_bundle(MarkdownImagePaddleResult(), page_dir)

    assert not (work_dir / "imgs").exists()
    assert (page_dir / "imgs" / "picture.jpg").read_bytes() == b"jpeg"


def test_write_combined_outputs_uses_successful_pages(tmp_path):
    for page in [1, 2]:
        page_dir = tmp_path / "pages" / f"page_{page:04d}"
        page_dir.mkdir(parents=True)
        (page_dir / "output.md").write_text(f"page {page}", encoding="utf-8")
        (page_dir / "res.json").write_text(json.dumps({"page": page}), encoding="utf-8")

    write_combined_outputs(tmp_path, ok_pages=[1], failed_pages=[2])

    combined_md = (tmp_path / "combined.md").read_text(encoding="utf-8")
    assert "# Page 1" in combined_md
    assert "page 1" in combined_md
    assert json.loads((tmp_path / "combined.jsonl").read_text(encoding="utf-8")) == {
        "page": 1
    }
    assert (tmp_path / "failed_pages.txt").read_text(encoding="utf-8") == "2\n"


def test_write_combined_outputs_rewrites_page_local_image_paths(tmp_path):
    page_dir = tmp_path / "pages" / "page_0001"
    page_dir.mkdir(parents=True)
    (page_dir / "output.md").write_text(
        '<img src="imgs/picture.jpg" alt="Image" />\n\n'
        "![diagram](imgs/diagram.png)",
        encoding="utf-8",
    )
    (page_dir / "res.json").write_text(json.dumps({"page": 1}), encoding="utf-8")

    write_combined_outputs(tmp_path, ok_pages=[1], failed_pages=[])

    combined_md = (tmp_path / "combined.md").read_text(encoding="utf-8")
    assert 'src="pages/page_0001/imgs/picture.jpg"' in combined_md
    assert "![diagram](pages/page_0001/imgs/diagram.png)" in combined_md
