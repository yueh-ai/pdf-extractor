import json
import sqlite3

from pdf_extract.reconciled_store import (
    LocalObjectStore,
    PageCatalog,
    PageReconciliationResult,
    page_dir_name,
)


def test_page_result_validates_required_fields():
    result = PageReconciliationResult(
        document_id="Full_30015375000000",
        page=2,
        reconciled_markdown="hello",
        winner="mixed",
        warnings=[],
        needs_human_review=False,
        model="prototype",
        prompt_version="reconcile-page-v1",
        source_refs={
            "page_image": "runs/doc/union/pages/page_0002/page.png",
            "union_markdown": "runs/doc/union/pages/page_0002/output.md",
            "small_markdown": "runs/doc/small/pages/page_0002/output.md",
        },
    )

    assert result.warning_count == 0
    assert result.decision_payload()["winner"] == "mixed"
    assert result.decision_payload()["source_refs"]["page_image"].endswith("page.png")


def test_local_object_store_writes_and_reads_by_key(tmp_path):
    store = LocalObjectStore(tmp_path / "object_store")

    path = store.write_text("pdf-extract/reconciled/doc/pages/page_0001/output.md", "hi")

    assert path == tmp_path / "object_store/pdf-extract/reconciled/doc/pages/page_0001/output.md"
    assert store.read_text("pdf-extract/reconciled/doc/pages/page_0001/output.md") == "hi"


def test_page_catalog_creates_thin_pages_table(tmp_path):
    db_path = tmp_path / "catalog.sqlite"
    catalog = PageCatalog(db_path)
    catalog.init_schema()

    with sqlite3.connect(db_path) as conn:
        columns = [
            row[1]
            for row in conn.execute("PRAGMA table_info(pages)").fetchall()
        ]

    assert columns == [
        "document_id",
        "page",
        "status",
        "markdown_key",
        "assets_key",
        "decision_key",
        "needs_human_review",
        "warning_count",
        "asset_count",
        "markdown_sha256",
        "markdown_text",
        "error_message",
        "published_at",
    ]
