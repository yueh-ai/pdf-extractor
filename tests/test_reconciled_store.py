import json
import sqlite3
import pytest

from pdf_extract.reconciled_store import (
    LocalObjectStore,
    PageCatalog,
    PageReconciliationResult,
)


def _result_args() -> dict:
    return {
        "document_id": "Full_30015375000000",
        "page": 2,
        "reconciled_markdown": "hello",
        "winner": "mixed",
        "warnings": [],
        "needs_human_review": False,
        "model": "prototype",
        "prompt_version": "reconcile-page-v1",
        "source_refs": {
            "page_image": "runs/doc/union/pages/page_0002/page.png",
            "union_markdown": "runs/doc/union/pages/page_0002/output.md",
            "small_markdown": "runs/doc/small/pages/page_0002/output.md",
        },
    }


def test_page_result_validates_required_fields():
    result = PageReconciliationResult(**_result_args())
    payload = result.decision_payload()

    assert result.warning_count == 0
    assert payload["winner"] == "mixed"
    assert payload["warnings"] == []
    assert payload["source_refs"]["page_image"].endswith("page.png")
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["source_refs"], dict)


def test_page_result_rejects_invalid_page():
    args = _result_args()
    args["page"] = 0

    with pytest.raises(ValueError, match="page must be >= 1"):
        PageReconciliationResult(**args)


def test_page_result_rejects_unsupported_winner():
    args = _result_args()
    args["winner"] = "unsupported"

    with pytest.raises(ValueError, match="Unsupported winner"):
        PageReconciliationResult(**args)


def test_page_result_requires_source_refs_keys():
    args = _result_args()
    del args["source_refs"]["small_markdown"]

    with pytest.raises(ValueError, match="source_refs\\.small_markdown is required"):
        PageReconciliationResult(**args)


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
