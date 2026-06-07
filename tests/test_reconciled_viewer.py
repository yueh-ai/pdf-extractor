import json

from pdf_extract.reconciled_store import (
    LocalObjectStore,
    PageCatalog,
    PageReconciliationResult,
    ReconciledPagePublisher,
)
from pdf_extract.reconciled_viewer import repo_url_for_path, write_viewer_manifest


def make_result(markdown: str, page: int = 40) -> PageReconciliationResult:
    return PageReconciliationResult(
        document_id="Full_30015375000000",
        page=page,
        reconciled_markdown=markdown,
        winner="union",
        warnings=["check render"],
        needs_human_review=True,
        model="prototype-no-llm",
        prompt_version="prototype-page-v1",
        source_refs={
            "page_image": f"runs/Full_30015375000000/union/pages/page_{page:04d}/page.png",
            "union_markdown": f"runs/Full_30015375000000/union/pages/page_{page:04d}/output.md",
            "small_markdown": f"runs/Full_30015375000000/small/pages/page_{page:04d}/output.md",
        },
    )


def test_repo_url_for_path_requires_path_inside_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    inside = repo_root / "runs" / "doc" / "page.png"
    inside.parent.mkdir(parents=True)
    inside.write_bytes(b"png")

    assert repo_url_for_path(inside, repo_root=repo_root) == "/runs/doc/page.png"


def test_write_viewer_manifest_includes_page_image_markdown_and_asset_urls(tmp_path):
    repo_root = tmp_path / "repo"
    run_page = repo_root / "runs" / "Full_30015375000000" / "union" / "pages" / "page_0040"
    (run_page / "imgs").mkdir(parents=True)
    (run_page / "page.png").write_bytes(b"png")
    (run_page / "imgs" / "seal.jpg").write_bytes(b"jpeg")

    store = LocalObjectStore(repo_root / "object_store")
    catalog = PageCatalog(repo_root / "catalog.sqlite")
    publisher = ReconciledPagePublisher(store=store, catalog=catalog)
    publisher.publish(
        make_result('<table><tr><td>A</td></tr></table><img src="imgs/seal.jpg" />'),
        asset_base_dir=run_page,
    )

    manifest_path = write_viewer_manifest(
        catalog=catalog,
        store=store,
        document_id="Full_30015375000000",
        viewer_dir=repo_root / "runs" / "Full_30015375000000" / "reconciled_viewer",
        repo_root=repo_root,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["document_id"] == "Full_30015375000000"
    assert manifest["pages"][0]["page"] == 40
    assert manifest["pages"][0]["status"] == "published"
    assert manifest["pages"][0]["needs_human_review"] is True
    assert manifest["pages"][0]["warning_count"] == 1
    assert manifest["pages"][0]["source_page_image_path"].endswith("page_0040/page.png")
    assert manifest["pages"][0]["source_page_image_url"] == "/runs/Full_30015375000000/union/pages/page_0040/page.png"
    assert manifest["pages"][0]["markdown_url"].startswith("/object_store/")
    assert "asset://pdf-extract/reconciled" in manifest["pages"][0]["markdown_text"]
    asset = manifest["pages"][0]["assets"][0]
    assert asset["asset_uri"].startswith("asset://pdf-extract/reconciled/")
    assert asset["object_key"].endswith("/assets/seal.jpg")
    assert asset["local_path"].endswith("object_store/pdf-extract/reconciled/Full_30015375000000/pages/page_0040/assets/seal.jpg")
    assert asset["local_url"] == "/object_store/pdf-extract/reconciled/Full_30015375000000/pages/page_0040/assets/seal.jpg"
    assert asset["content_type"] == "image/jpeg"
    assert asset["byte_size"] == 4
    assert asset["sha256"]
