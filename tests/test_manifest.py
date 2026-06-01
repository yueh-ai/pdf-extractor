import json

from pdf_extract.manifest import (
    append_manifest_entry,
    is_page_complete,
    load_latest_manifest,
)


def test_load_latest_manifest_uses_last_entry_per_page(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        "\n".join(
            [
                json.dumps({"page": 1, "status": "failed", "attempt": 1}),
                json.dumps({"page": 1, "status": "ok", "attempt": 2}),
                json.dumps({"page": 2, "status": "failed", "attempt": 1}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    latest = load_latest_manifest(manifest)

    assert latest[1]["status"] == "ok"
    assert latest[1]["attempt"] == 2
    assert latest[2]["status"] == "failed"


def test_append_manifest_entry_writes_json_line(tmp_path):
    manifest = tmp_path / "manifest.jsonl"

    append_manifest_entry(manifest, {"page": 3, "status": "ok"})

    assert json.loads(manifest.read_text(encoding="utf-8")) == {
        "page": 3,
        "status": "ok",
    }


def test_is_page_complete_requires_ok_manifest_and_bundle_files(tmp_path):
    page_dir = tmp_path / "pages" / "page_0001"
    page_dir.mkdir(parents=True)
    for name in ["page.png", "layout_det_res.png", "res.json", "output.docx", "output.md"]:
        (page_dir / name).write_bytes(b"x")

    assert is_page_complete(1, tmp_path, {1: {"status": "ok"}}, require_page_image=True)
    assert not is_page_complete(
        1, tmp_path, {1: {"status": "failed"}}, require_page_image=True
    )


def test_is_page_complete_can_skip_page_image_requirement(tmp_path):
    page_dir = tmp_path / "pages" / "page_0001"
    page_dir.mkdir(parents=True)
    for name in ["layout_det_res.png", "res.json", "output.docx", "output.md"]:
        (page_dir / name).write_bytes(b"x")

    assert is_page_complete(1, tmp_path, {1: {"status": "ok"}}, require_page_image=False)


def test_is_page_complete_requires_referenced_markdown_image_assets(tmp_path):
    page_dir = tmp_path / "pages" / "page_0001"
    page_dir.mkdir(parents=True)
    for name in ["page.png", "layout_det_res.png", "res.json", "output.docx"]:
        (page_dir / name).write_bytes(b"x")
    (page_dir / "output.md").write_text(
        '<img src="imgs/picture.jpg" alt="Image" />\n\n'
        "![diagram](imgs/diagram.png)",
        encoding="utf-8",
    )
    (page_dir / "imgs").mkdir()
    (page_dir / "imgs" / "picture.jpg").write_bytes(b"jpg")

    assert not is_page_complete(
        1, tmp_path, {1: {"status": "ok"}}, require_page_image=True
    )

    (page_dir / "imgs" / "diagram.png").write_bytes(b"png")

    assert is_page_complete(1, tmp_path, {1: {"status": "ok"}}, require_page_image=True)
