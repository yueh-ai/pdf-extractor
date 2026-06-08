import json
import sqlite3
import pytest

from pdf_extract.reconciled_store import (
    LocalObjectStore,
    PageCatalog,
    assemble_document,
    ReconciledPagePublisher,
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


def make_result(markdown: str, page: int = 2) -> PageReconciliationResult:
    return PageReconciliationResult(
        document_id="Full_30015375000000",
        page=page,
        reconciled_markdown=markdown,
        winner="mixed",
        warnings=["prototype warning"],
        needs_human_review=True,
        model="prototype",
        prompt_version="reconcile-page-v1",
        source_refs={
            "page_image": f"runs/doc/union/pages/page_{page:04d}/page.png",
            "union_markdown": f"runs/doc/union/pages/page_{page:04d}/output.md",
            "small_markdown": f"runs/doc/small/pages/page_{page:04d}/output.md",
        },
    )


def make_result_with_markdown(markdown: str, page: int = 2) -> PageReconciliationResult:
    return PageReconciliationResult(
        document_id="Full_30015375000000",
        page=page,
        reconciled_markdown=markdown,
        winner="mixed",
        warnings=["prototype warning"],
        needs_human_review=True,
        model="prototype",
        prompt_version="reconcile-page-v1",
        source_refs={
            "page_image": f"runs/doc/union/pages/page_{page:04d}/page.png",
            "union_markdown": f"runs/doc/union/pages/page_{page:04d}/output.md",
            "small_markdown": f"runs/doc/small/pages/page_{page:04d}/output.md",
        },
    )


def test_page_result_validates_required_fields():
    result = PageReconciliationResult(**_result_args())
    payload = result.decision_payload()

    assert result.warning_count == 0
    assert payload["winner"] == "mixed"
    assert payload["warnings"] == []
    assert payload["source_refs"]["page_image"].endswith("page.png")
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["source_refs"], dict)


def test_page_result_decision_payload_includes_llm_calls():
    args = _result_args()
    args["llm_calls"] = [
        {
            "round": 1,
            "model": "gpt-5",
            "prompt_version": "reconcile-page-v1",
            "input_tokens": 1200,
            "output_tokens": 300,
            "total_tokens": 1500,
        }
    ]

    result = PageReconciliationResult(**args)
    payload = result.decision_payload()

    assert payload["llm_calls"] == args["llm_calls"]
    assert isinstance(result.llm_calls, tuple)


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


def test_publish_page_with_no_assets_writes_page_artifacts(tmp_path):
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )

    published = publisher.publish(make_result("# Page body\n\nNo image."), asset_base_dir=tmp_path)

    assert published.status == "published"
    assert published.asset_count == 0
    assert publisher.store.read_text(published.markdown_key) == "# Page body\n\nNo image."
    assets = json.loads(publisher.store.read_text(published.assets_key))
    decision = json.loads(publisher.store.read_text(published.decision_key))
    assert assets == {"document_id": "Full_30015375000000", "page": 2, "assets": []}
    assert decision["winner"] == "mixed"

    with publisher.catalog.connect() as conn:
        row = conn.execute(
            "SELECT status, warning_count, asset_count, markdown_text FROM pages WHERE document_id = ? AND page = ?",
            ("Full_30015375000000", 2),
        ).fetchone()
    assert row["status"] == "published"
    assert row["warning_count"] == 1
    assert row["asset_count"] == 0
    assert row["markdown_text"] == "# Page body\n\nNo image."


def test_publish_page_copies_imgs_reference_and_rewrites_to_asset_uri(tmp_path):
    source = tmp_path / "page_0002"
    (source / "imgs").mkdir(parents=True)
    (source / "imgs" / "seal.jpg").write_bytes(b"jpeg")
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )

    published = publisher.publish(
        make_result('<img src="imgs/seal.jpg" alt="Seal" />'),
        asset_base_dir=source,
    )

    rewritten = publisher.store.read_text(published.markdown_key)
    assert 'src="asset://pdf-extract/reconciled/Full_30015375000000/pages/page_0002/assets/seal.jpg"' in rewritten
    assert publisher.store.path_for_key(
        "pdf-extract/reconciled/Full_30015375000000/pages/page_0002/assets/seal.jpg"
    ).read_bytes() == b"jpeg"
    assets = json.loads(publisher.store.read_text(published.assets_key))
    assert assets["assets"][0]["source_path"].endswith("page_0002/imgs/seal.jpg")
    assert assets["assets"][0]["sha256"] == "41e5787e9f28562d07b891b1816b492309d646c0f2829743fa4963a9f9cc1d61"


def test_publish_page_duplicates_same_ref_only_once(tmp_path):
    source = tmp_path / "page_0002"
    (source / "imgs").mkdir(parents=True)
    (source / "imgs" / "seal.jpg").write_bytes(b"jpeg")
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )

    published = publisher.publish(
        make_result('<img src="imgs/seal.jpg" alt="Seal" /><img src="imgs/seal.jpg" alt="Seal again" />'),
        asset_base_dir=source,
    )

    assets = json.loads(publisher.store.read_text(published.assets_key))
    assert len(assets["assets"]) == 1
    assert published.asset_count == 1
    rewritten = publisher.store.read_text(published.markdown_key)
    expected = 'src="asset://pdf-extract/reconciled/Full_30015375000000/pages/page_0002/assets/seal.jpg"'
    assert rewritten.count(expected) == 2


def test_publish_page_with_duplicate_basenames_uses_collision_suffix(tmp_path):
    source = tmp_path / "page_0002"
    (source / "imgs").mkdir(parents=True)
    (source / "imgs" / "seal.jpg").write_bytes(b"jpeg")
    (source / "assets").mkdir()
    (source / "assets" / "seal.jpg").write_bytes(b"other-jpeg")
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )

    published = publisher.publish(
        make_result('![left](imgs/seal.jpg) and ![right](assets/seal.jpg)'),
        asset_base_dir=source,
    )

    assets = json.loads(publisher.store.read_text(published.assets_key))
    assert len(assets["assets"]) == 2
    object_keys = [asset["object_key"] for asset in assets["assets"]]
    assert len(object_keys) == 2
    assert any(key.endswith("/seal.jpg") for key in object_keys)
    assert any(key.endswith(".jpg") and "/seal_" in key for key in object_keys)
    assert len(set(object_keys)) == 2

    for asset in assets["assets"]:
        assert "asset_uri" in asset
        assert asset["asset_uri"].startswith("asset://")
        assert asset["content_type"] == "image/jpeg"
        assert isinstance(asset["byte_size"], int)
        assert asset["description"] == "seal"


def test_publish_page_with_missing_asset_then_failure_clears_stale_row_fields(tmp_path):
    source = tmp_path / "page_0002"
    (source / "imgs").mkdir(parents=True)
    (source / "imgs" / "seal.jpg").write_bytes(b"jpeg")
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )

    success = publisher.publish(make_result("![seal](imgs/seal.jpg)"), asset_base_dir=source)
    assert success.status == "published"

    with publisher.catalog.connect() as conn:
        row = conn.execute(
            "SELECT status, markdown_key, assets_key, decision_key, markdown_text, asset_count FROM pages WHERE document_id = ? AND page = ?",
            ("Full_30015375000000", 2),
        ).fetchone()
    assert row["status"] == "published"
    assert row["markdown_text"] is not None
    assert row["asset_count"] == 1

    failed = publisher.publish(make_result("![missing](imgs/missing.jpg)"), asset_base_dir=source)
    assert failed.status == "publish_failed"
    assert "Missing referenced asset: imgs/missing.jpg" in failed.error_message

    with publisher.catalog.connect() as conn:
        row = conn.execute(
            "SELECT status, markdown_key, assets_key, decision_key, markdown_text, asset_count, error_message FROM pages WHERE document_id = ? AND page = ?",
            ("Full_30015375000000", 2),
        ).fetchone()
    assert row["status"] == "publish_failed"
    assert row["markdown_key"] is None
    assert row["assets_key"] is None
    assert row["decision_key"] is None
    assert row["markdown_text"] is None
    assert row["asset_count"] == 0
    assert "Missing referenced asset: imgs/missing.jpg" in row["error_message"]


def test_publish_page_with_missing_asset_records_failure(tmp_path):
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )

    published = publisher.publish(make_result("![missing](imgs/missing.jpg)"), asset_base_dir=tmp_path)

    assert published.status == "publish_failed"
    assert "Missing referenced asset: imgs/missing.jpg" in published.error_message

    with publisher.catalog.connect() as conn:
        row = conn.execute(
            "SELECT status, error_message, asset_count, markdown_text FROM pages WHERE document_id = ? AND page = ?",
            ("Full_30015375000000", 2),
        ).fetchone()
    assert row["status"] == "publish_failed"
    assert "Missing referenced asset: imgs/missing.jpg" in row["error_message"]
    assert row["asset_count"] == 0
    assert row["markdown_text"] is None


def test_publish_page_with_unsafe_relative_ref_records_failure(tmp_path):
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )

    published = publisher.publish(make_result('<img src="../secret.jpg" alt="secret" />'), asset_base_dir=tmp_path / "page_0002")

    assert published.status == "publish_failed"
    assert "Unsafe referenced asset path: ../secret.jpg" in published.error_message

    with publisher.catalog.connect() as conn:
        row = conn.execute(
            "SELECT status, error_message, asset_count, markdown_text FROM pages WHERE document_id = ? AND page = ?",
            ("Full_30015375000000", 2),
        ).fetchone()
    assert row["status"] == "publish_failed"
    assert "Unsafe referenced asset path: ../secret.jpg" in row["error_message"]
    assert row["asset_count"] == 0
    assert row["markdown_text"] is None


def test_publish_page_with_absolute_ref_inside_allowed_root_publishes(tmp_path):
    source = tmp_path / "union" / "pages" / "page_0002"
    (source / "imgs").mkdir(parents=True)
    allowed_root_asset = source.parent.parent / "assets" / "seal.jpg"
    allowed_root_asset.parent.mkdir(parents=True)
    allowed_root_asset.write_bytes(b"jpeg")
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )

    published = publisher.publish(
        make_result_with_markdown(f"![abs]({allowed_root_asset})"),
        asset_base_dir=source,
    )
    expected_asset_key = "pdf-extract/reconciled/Full_30015375000000/pages/page_0002/assets/seal.jpg"
    expected_asset_uri = f"asset://{expected_asset_key}"

    assert published.status == "published"
    assert published.asset_count == 1
    rewritten = publisher.store.read_text(published.markdown_key)
    assert expected_asset_uri in rewritten
    assert publisher.store.path_for_key(expected_asset_key).read_bytes() == b"jpeg"


def test_assemble_document_joins_expected_pages_subset_and_ignores_stale_rows(tmp_path):
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )
    publisher.publish(make_result("page one", page=1), asset_base_dir=tmp_path)
    publisher.publish(make_result("page two", page=2), asset_base_dir=tmp_path)
    publisher.publish(make_result("page forty", page=40), asset_base_dir=tmp_path)

    result = assemble_document(
        document_id="Full_30015375000000",
        store=publisher.store,
        catalog=publisher.catalog,
        expected_pages=[1, 2],
    )

    combined = publisher.store.read_text(result["combined_markdown_key"])
    manifest = json.loads(publisher.store.read_text(result["manifest_key"]))
    assert manifest["included_pages"] == [1, 2]
    assert "# Page 1" in combined
    assert "# Page 2" in combined
    assert "# Page 40" not in combined


def test_publish_page_with_absolute_ref_outside_allowed_root_records_failure(tmp_path):
    source = tmp_path / "union" / "pages" / "page_0002"
    (source / "imgs").mkdir(parents=True)
    outside_root_asset = tmp_path / "outside_root" / "forbidden.jpg"
    outside_root_asset.parent.mkdir(parents=True)
    outside_root_asset.write_bytes(b"not-allowed")
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )

    published = publisher.publish(
        make_result_with_markdown(f"![abs]({outside_root_asset})"),
        asset_base_dir=source,
    )
    expected_output_key = "pdf-extract/reconciled/Full_30015375000000/pages/page_0002/output.md"

    assert published.status == "publish_failed"
    assert f"Unsafe referenced asset path: {outside_root_asset}" in published.error_message
    assert not publisher.store.path_for_key(expected_output_key).exists()

    with publisher.catalog.connect() as conn:
        row = conn.execute(
            "SELECT status, error_message, asset_count, markdown_text FROM pages WHERE document_id = ? AND page = ?",
            ("Full_30015375000000", 2),
        ).fetchone()
    assert row["status"] == "publish_failed"
    assert f"Unsafe referenced asset path: {outside_root_asset}" in row["error_message"]
    assert row["asset_count"] == 0
    assert row["markdown_text"] is None


def test_republishing_page_updates_one_catalog_row(tmp_path):
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )

    publisher.publish(make_result("first"), asset_base_dir=tmp_path)
    publisher.publish(make_result("second"), asset_base_dir=tmp_path)

    rows = publisher.catalog.list_pages("Full_30015375000000")
    assert len(rows) == 1
    assert rows[0]["markdown_text"] == "second"


def test_assemble_document_joins_published_pages_and_reports_missing(tmp_path):
    publisher = ReconciledPagePublisher(
        store=LocalObjectStore(tmp_path / "object_store"),
        catalog=PageCatalog(tmp_path / "catalog.sqlite"),
    )
    publisher.publish(make_result("page two", page=2), asset_base_dir=tmp_path)
    publisher.publish(make_result("page one", page=1), asset_base_dir=tmp_path)

    result = assemble_document(
        document_id="Full_30015375000000",
        store=publisher.store,
        catalog=publisher.catalog,
        expected_pages=[1, 2, 3],
    )

    combined = publisher.store.read_text(result["combined_markdown_key"])
    manifest = json.loads(publisher.store.read_text(result["manifest_key"]))
    assert combined == "# Page 1\n\npage one\n\n# Page 2\n\npage two\n"
    assert manifest["included_pages"] == [1, 2]
    assert manifest["missing_pages"] == [3]
