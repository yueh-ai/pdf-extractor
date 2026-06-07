import json
import sqlite3

from pdf_extract.reconciled_prototype import run_three_page_prototype


def write_page(run_root, mode, page, markdown, image_name=None):
    page_dir = run_root / mode / "pages" / f"page_{page:04d}"
    page_dir.mkdir(parents=True, exist_ok=True)
    (page_dir / "output.md").write_text(markdown, encoding="utf-8")
    (page_dir / "page.png").write_bytes(b"png")
    if image_name:
        (page_dir / "imgs").mkdir()
        (page_dir / "imgs" / image_name).write_bytes(b"jpeg")


def test_three_page_prototype_publishes_assembles_and_writes_viewer(tmp_path):
    run_root = tmp_path / "runs" / "Full_30015375000000"
    for page in [1, 2, 40]:
        write_page(run_root, "union", page, f"union page {page}")
        write_page(run_root, "small", page, f"small page {page}")
    write_page(
        run_root,
        "union",
        40,
        '<img src="imgs/seal.jpg" alt="Seal" />',
        image_name="seal.jpg",
    )

    result = run_three_page_prototype(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=tmp_path / "viewer",
        pages=[1, 2, 40],
    )

    assert result["document_id"] == "Full_30015375000000"
    assert result["published_pages"] == [1, 2, 40]
    assert (tmp_path / "viewer" / "index.html").is_file()
    with sqlite3.connect(tmp_path / "catalog.sqlite") as conn:
        rows = conn.execute("SELECT page, status, asset_count FROM pages ORDER BY page").fetchall()
    assert rows == [(1, "published", 0), (2, "published", 0), (40, "published", 1)]
    manifest = json.loads(
        (tmp_path / "object_store" / result["assembly"]["manifest_key"]).read_text(
            encoding="utf-8"
        )
    )
    assert manifest["included_pages"] == [1, 2, 40]
