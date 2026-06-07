from __future__ import annotations

import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

from pdf_extract.reconciled_store import PUBLISHED
from pdf_extract.reconciler import (
    DEFAULT_RECONCILE_MODEL,
    DEFAULT_RECONCILE_PROMPT_VERSION,
    OpenAIResponsesVisionClient,
    PageReconcileInputs,
    VisionReconciler,
    build_reconcile_prompt,
    discover_reconcile_pages,
    load_page_inputs,
    run_reconciliation,
)


def write_page(run_root: Path, mode: str, page: int, markdown: str, *, image: bool = True) -> Path:
    page_dir = run_root / mode / "pages" / f"page_{page:04d}"
    page_dir.mkdir(parents=True, exist_ok=True)
    (page_dir / "output.md").write_text(markdown, encoding="utf-8")
    if image:
        (page_dir / "page.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return page_dir


class FakeVisionClient:
    def __init__(self, response: dict, *, model: str = "fake-vision-model"):
        self.model = model
        self.response = response
        self.calls: list[dict[str, object]] = []

    def reconcile(self, *, image_path: Path, prompt: str) -> dict:
        self.calls.append({"image_path": image_path, "prompt": prompt})
        return dict(self.response)


class CountingVisionClient:
    model = "counting-fake-model"

    def __init__(self):
        self.pages: list[int] = []

    def reconcile(self, *, image_path: Path, prompt: str) -> dict:
        page = int(image_path.parent.name.removeprefix("page_"))
        self.pages.append(page)
        return {
            "reconciled_markdown": f"# Page {page}\n\nmerged markdown",
            "winner": "mixed",
            "warnings": [f"warning {page}"],
            "needs_human_review": page % 2 == 0,
        }


class FakeResponsesAPI:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=json.dumps(self.payload))


class FakeOpenAISDK:
    def __init__(self, payload: dict):
        self.responses = FakeResponsesAPI(payload)


def load_run_reconcile_script() -> dict[str, object]:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_reconcile.py"
    return runpy.run_path(str(script_path), run_name="run_reconcile_test")


def test_discover_reconcile_pages_returns_pages_present_in_both_modes(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 1, "union one")
    write_page(run_root, "small", 1, "small one")
    write_page(run_root, "union", 2, "union two")
    write_page(run_root, "small", 3, "small three")

    assert discover_reconcile_pages(run_root) == [1]


def test_load_page_inputs_prefers_union_page_image(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    union_page = write_page(run_root, "union", 2, "union markdown")
    small_page = write_page(run_root, "small", 2, "small markdown")

    inputs = load_page_inputs(run_root, 2)

    assert isinstance(inputs, PageReconcileInputs)
    assert inputs.document_id == "sample-doc"
    assert inputs.page == 2
    assert inputs.page_image_path == union_page / "page.png"
    assert inputs.union_markdown_path == union_page / "output.md"
    assert inputs.small_markdown_path == small_page / "output.md"
    assert inputs.union_markdown == "union markdown"
    assert inputs.small_markdown == "small markdown"


def test_load_page_inputs_falls_back_to_small_page_image(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 4, "union markdown", image=False)
    small_page = write_page(run_root, "small", 4, "small markdown")

    inputs = load_page_inputs(run_root, 4)

    assert inputs.page_image_path == small_page / "page.png"


def test_load_page_inputs_requires_markdown_and_page_image(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 5, "union markdown", image=False)
    write_page(run_root, "small", 5, "small markdown", image=False)

    with pytest.raises(FileNotFoundError, match="page image"):
        load_page_inputs(run_root, 5)


def test_build_reconcile_prompt_is_general_and_uses_image_as_authority(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 1, "union draft with ![img](imgs/union.png)")
    write_page(run_root, "small", 1, "small draft")

    prompt = build_reconcile_prompt(load_page_inputs(run_root, 1))

    assert "authoritative source of truth" in prompt
    assert "union draft with ![img](imgs/union.png)" in prompt
    assert "small draft" in prompt
    assert "res.json" not in prompt
    assert "wellbore" not in prompt.lower()
    assert "oil" not in prompt.lower()


def test_vision_reconciler_validates_structured_fields(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 1, "union draft")
    write_page(run_root, "small", 1, "small draft")
    client = FakeVisionClient(
        {
            "reconciled_markdown": "# ok",
            "winner": "not-valid",
            "warnings": [],
            "needs_human_review": False,
        }
    )

    with pytest.raises(ValueError, match="winner"):
        VisionReconciler(client=client).reconcile_page(load_page_inputs(run_root, 1))


def test_vision_reconciler_returns_page_result_and_uses_prompt_version(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    union_page = write_page(run_root, "union", 3, "union draft")
    small_page = write_page(run_root, "small", 3, "small draft")
    client = FakeVisionClient(
        {
            "reconciled_markdown": "# merged",
            "winner": "mixed",
            "warnings": ["needs review"],
            "needs_human_review": True,
        }
    )

    result = VisionReconciler(client=client).reconcile_page(load_page_inputs(run_root, 3))

    assert result.document_id == "sample-doc"
    assert result.page == 3
    assert result.reconciled_markdown == "# merged"
    assert result.winner == "mixed"
    assert result.warnings == ("needs review",)
    assert result.needs_human_review is True
    assert result.model == "fake-vision-model"
    assert result.prompt_version == DEFAULT_RECONCILE_PROMPT_VERSION
    assert result.source_refs == {
        "page_image": (union_page / "page.png").as_posix(),
        "union_markdown": (union_page / "output.md").as_posix(),
        "small_markdown": (small_page / "output.md").as_posix(),
    }
    assert "res.json" not in client.calls[0]["prompt"]


def test_run_reconciliation_processes_all_discovered_pages_and_writes_viewer_manifest(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 1, "# union one")
    write_page(run_root, "small", 1, "# small one")
    write_page(run_root, "union", 2, "# union two")
    write_page(run_root, "small", 2, "# small two")
    write_page(run_root, "union", 3, "# union three")
    client = CountingVisionClient()

    result = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=tmp_path / "viewer",
        client=client,
    )

    assert client.pages == [1, 2]
    assert result["processed_pages"] == [1, 2]
    assert result["published_pages"] == [1, 2]
    assert result["skipped_pages"] == []
    assert result["assembly"]["included_pages"] == [1, 2]
    assert (tmp_path / "viewer" / "viewer-manifest.json").is_file()
    decision = json.loads(
        (tmp_path / "object_store" / "pdf-extract" / "reconciled" / "sample-doc" / "pages" / "page_0001" / "decision.json").read_text(
            encoding="utf-8"
        )
    )
    assert sorted(decision["source_refs"]) == ["page_image", "small_markdown", "union_markdown"]


def test_run_reconciliation_respects_requested_pages(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    for page in (1, 2, 3):
        write_page(run_root, "union", page, f"union {page}")
        write_page(run_root, "small", page, f"small {page}")
    client = CountingVisionClient()

    result = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=None,
        client=client,
        pages=[2, 3],
    )

    assert client.pages == [2, 3]
    assert result["processed_pages"] == [2, 3]


def test_run_reconciliation_skips_published_pages_unless_forced(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 2, "# union two")
    write_page(run_root, "small", 2, "# small two")
    first_client = CountingVisionClient()

    first = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=tmp_path / "viewer",
        client=first_client,
        pages=[2],
    )

    resumed_client = CountingVisionClient()
    resumed = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=tmp_path / "viewer",
        client=resumed_client,
        pages=[2],
    )

    forced_client = CountingVisionClient()
    forced = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=tmp_path / "viewer",
        client=forced_client,
        pages=[2],
        force=True,
    )

    assert first["published_pages"] == [2]
    assert resumed["processed_pages"] == []
    assert resumed["skipped_pages"] == [2]
    assert resumed_client.pages == []
    assert forced["processed_pages"] == [2]
    assert forced["skipped_pages"] == []
    assert forced_client.pages == [2]


def test_run_reconciliation_mixed_page_can_publish_page_local_assets(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    union_page = write_page(run_root, "union", 6, "# union")
    write_page(run_root, "small", 6, "# small")
    (union_page / "imgs").mkdir()
    (union_page / "imgs" / "seal.jpg").write_bytes(b"jpeg")
    client = FakeVisionClient(
        {
            "reconciled_markdown": "![seal](imgs/seal.jpg)",
            "winner": "mixed",
            "warnings": [],
            "needs_human_review": False,
        }
    )

    result = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=None,
        client=client,
        pages=[6],
    )

    assert result["published_pages"] == [6]
    output = (
        tmp_path
        / "object_store"
        / "pdf-extract"
        / "reconciled"
        / "sample-doc"
        / "pages"
        / "page_0006"
        / "output.md"
    ).read_text(encoding="utf-8")
    assert "asset://pdf-extract/reconciled/sample-doc/pages/page_0006/assets/seal.jpg" in output


def test_run_reconciliation_mixed_page_can_publish_small_only_assets(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 7, "# union")
    small_page = write_page(run_root, "small", 7, "# small")
    (small_page / "imgs").mkdir()
    (small_page / "imgs" / "seal.jpg").write_bytes(b"jpeg")
    client = FakeVisionClient(
        {
            "reconciled_markdown": "![seal](imgs/seal.jpg)",
            "winner": "mixed",
            "warnings": [],
            "needs_human_review": False,
        }
    )

    result = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=None,
        client=client,
        pages=[7],
    )

    assert result["published_pages"] == [7]
    asset_path = (
        tmp_path
        / "object_store"
        / "pdf-extract"
        / "reconciled"
        / "sample-doc"
        / "pages"
        / "page_0007"
        / "assets"
        / "seal.jpg"
    )
    assert asset_path.read_bytes() == b"jpeg"


def test_run_reconciliation_mixed_page_can_publish_assets_split_across_modes(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    union_page = write_page(run_root, "union", 11, "# union")
    small_page = write_page(run_root, "small", 11, "# small")
    (union_page / "imgs").mkdir()
    (small_page / "imgs").mkdir()
    (union_page / "imgs" / "union.jpg").write_bytes(b"union-jpeg")
    (small_page / "imgs" / "small.jpg").write_bytes(b"small-jpeg")
    client = FakeVisionClient(
        {
            "reconciled_markdown": (
                "![union](imgs/union.jpg)\n\n"
                "![small](imgs/small.jpg)"
            ),
            "winner": "mixed",
            "warnings": [],
            "needs_human_review": False,
        }
    )

    result = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=None,
        client=client,
        pages=[11],
    )

    assert result["published_pages"] == [11]
    asset_dir = (
        tmp_path
        / "object_store"
        / "pdf-extract"
        / "reconciled"
        / "sample-doc"
        / "pages"
        / "page_0011"
        / "assets"
    )
    assert (asset_dir / "union.jpg").read_bytes() == b"union-jpeg"
    assert (asset_dir / "small.jpg").read_bytes() == b"small-jpeg"
    assert not (union_page / ".reconcile_assets").exists()


def test_prepared_mixed_publish_does_not_allow_unresolved_sibling_absolute_asset(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    union_page = write_page(run_root, "union", 14, "# union")
    write_page(run_root, "small", 14, "# small")
    (union_page / "imgs").mkdir()
    (union_page / "imgs" / "union.jpg").write_bytes(b"union-jpeg")
    sibling_asset = tmp_path / "runs" / "other-doc" / "union" / "leak.jpg"
    sibling_asset.parent.mkdir(parents=True)
    sibling_asset.write_bytes(b"leak")
    client = FakeVisionClient(
        {
            "reconciled_markdown": (
                "![union](imgs/union.jpg)\n\n"
                f"![leak]({sibling_asset})"
            ),
            "winner": "mixed",
            "warnings": [],
            "needs_human_review": False,
        }
    )

    result = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=None,
        client=client,
        pages=[14],
    )

    assert result["failed_pages"] == [14]
    assert result["published_pages"] == []


def test_real_run_does_not_skip_prior_dry_run_publication(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 9, "union draft")
    write_page(run_root, "small", 9, "small draft")
    dry_run_client = FakeVisionClient(
        {
            "reconciled_markdown": "<!-- dry-run -->",
            "winner": "uncertain",
            "warnings": ["dry run"],
            "needs_human_review": True,
        },
        model="dry-run-no-llm",
    )
    real_client = FakeVisionClient(
        {
            "reconciled_markdown": "# real",
            "winner": "mixed",
            "warnings": [],
            "needs_human_review": False,
        },
        model="gpt-5.4-mini",
    )

    dry_run = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=None,
        client=dry_run_client,
        pages=[9],
    )
    real_run = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=None,
        client=real_client,
        pages=[9],
    )

    assert dry_run["published_pages"] == [9]
    assert real_run["processed_pages"] == [9]
    assert real_run["skipped_pages"] == []
    assert real_client.calls


def test_real_run_does_not_skip_prior_publication_with_missing_decision(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 12, "union draft")
    write_page(run_root, "small", 12, "small draft")
    dry_run_client = FakeVisionClient(
        {
            "reconciled_markdown": "<!-- dry-run -->",
            "winner": "uncertain",
            "warnings": ["dry run"],
            "needs_human_review": True,
        },
        model="dry-run-no-llm",
    )
    real_client = FakeVisionClient(
        {
            "reconciled_markdown": "# real",
            "winner": "mixed",
            "warnings": [],
            "needs_human_review": False,
        },
        model="gpt-5.4-mini",
    )
    object_store_root = tmp_path / "object_store"
    sqlite_path = tmp_path / "catalog.sqlite"

    run_reconciliation(
        run_root=run_root,
        object_store_root=object_store_root,
        sqlite_path=sqlite_path,
        viewer_dir=None,
        client=dry_run_client,
        pages=[12],
    )
    (
        object_store_root
        / "pdf-extract"
        / "reconciled"
        / "sample-doc"
        / "pages"
        / "page_0012"
        / "decision.json"
    ).unlink()
    real_run = run_reconciliation(
        run_root=run_root,
        object_store_root=object_store_root,
        sqlite_path=sqlite_path,
        viewer_dir=None,
        client=real_client,
        pages=[12],
    )

    assert real_run["processed_pages"] == [12]
    assert real_run["skipped_pages"] == []
    assert real_client.calls


def test_real_run_does_not_crash_or_skip_prior_publication_with_corrupt_decision(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 13, "union draft")
    write_page(run_root, "small", 13, "small draft")
    dry_run_client = FakeVisionClient(
        {
            "reconciled_markdown": "<!-- dry-run -->",
            "winner": "uncertain",
            "warnings": ["dry run"],
            "needs_human_review": True,
        },
        model="dry-run-no-llm",
    )
    real_client = FakeVisionClient(
        {
            "reconciled_markdown": "# real",
            "winner": "mixed",
            "warnings": [],
            "needs_human_review": False,
        },
        model="gpt-5.4-mini",
    )
    object_store_root = tmp_path / "object_store"
    sqlite_path = tmp_path / "catalog.sqlite"

    run_reconciliation(
        run_root=run_root,
        object_store_root=object_store_root,
        sqlite_path=sqlite_path,
        viewer_dir=None,
        client=dry_run_client,
        pages=[13],
    )
    (
        object_store_root
        / "pdf-extract"
        / "reconciled"
        / "sample-doc"
        / "pages"
        / "page_0013"
        / "decision.json"
    ).write_text("{not json", encoding="utf-8")
    real_run = run_reconciliation(
        run_root=run_root,
        object_store_root=object_store_root,
        sqlite_path=sqlite_path,
        viewer_dir=None,
        client=real_client,
        pages=[13],
    )

    assert real_run["processed_pages"] == [13]
    assert real_run["skipped_pages"] == []
    assert real_client.calls


def test_uncertain_winner_forces_human_review(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 8, "union draft")
    write_page(run_root, "small", 8, "small draft")
    client = FakeVisionClient(
        {
            "reconciled_markdown": "# uncertain",
            "winner": "uncertain",
            "warnings": [],
            "needs_human_review": False,
        }
    )

    result = VisionReconciler(client=client).reconcile_page(load_page_inputs(run_root, 8))

    assert result.winner == "uncertain"
    assert result.needs_human_review is True


def test_openai_responses_vision_client_sends_image_and_json_schema(tmp_path):
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    fake_sdk = FakeOpenAISDK(
        {
            "reconciled_markdown": "# merged",
            "winner": "mixed",
            "warnings": ["table uncertain"],
            "needs_human_review": True,
        }
    )
    client = OpenAIResponsesVisionClient(model="gpt-test-vision", sdk_client=fake_sdk)

    response = client.reconcile(image_path=image_path, prompt="reconcile this page")

    assert response["winner"] == "mixed"
    call = fake_sdk.responses.calls[0]
    assert call["model"] == "gpt-test-vision"
    assert call["input"][0]["role"] == "user"
    assert call["input"][0]["content"][0] == {"type": "input_text", "text": "reconcile this page"}
    image_item = call["input"][0]["content"][1]
    assert image_item["type"] == "input_image"
    assert image_item["detail"] == "high"
    assert image_item["image_url"].startswith("data:image/png;base64,")
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["strict"] is True
    assert call["text"]["format"]["schema"]["required"] == [
        "reconciled_markdown",
        "winner",
        "warnings",
        "needs_human_review",
    ]


def test_cli_helpers_support_env_model_and_repo_dotenv(monkeypatch, tmp_path):
    helpers = load_run_reconcile_script()
    create_client = helpers["create_client"]
    load_repo_env = helpers["load_openai_api_key_from_repo_env"]

    monkeypatch.setenv("OPENAI_RECONCILE_MODEL", "env-model")
    dry_run_client = create_client(provider="dry-run", model=None)
    assert dry_run_client.model == "dry-run-no-llm"

    monkeypatch.setenv("OPENAI_API_KEY", "already-set")
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".env").write_text('OPENAI_API_KEY="from-dotenv"\n', encoding="utf-8")
    assert load_repo_env(repo_root) is False
    assert Path(repo_root / ".env").is_file()

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert load_repo_env(repo_root) is True
    assert helpers["os"].environ["OPENAI_API_KEY"] == "from-dotenv"

    monkeypatch.setenv("OPENAI_API_KEY", "present")
    openai_client = create_client(provider="openai", model=None, sdk_client=FakeOpenAISDK({}))
    assert openai_client.model == "env-model"


def test_default_reconcile_model_is_gpt_5_4_mini():
    assert DEFAULT_RECONCILE_MODEL == "gpt-5.4-mini"
