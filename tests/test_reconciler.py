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
    ModelCallResult,
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


class SequencedVisionClient:
    model = "sequenced-fake-model"

    def __init__(self, responses: list[dict[str, object]]):
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def reconcile(self, *, image_path: Path, prompt: str) -> dict[str, object]:
        self.calls.append({"image_path": image_path, "prompt": prompt})
        if not self.responses:
            raise AssertionError("SequencedVisionClient received an unexpected call")
        return dict(self.responses.pop(0))


class MetadataVisionClient:
    model = "metadata-fake-model"

    def reconcile(self, *, image_path: Path, prompt: str) -> ModelCallResult:
        return ModelCallResult(
            payload={
                "reconciled_markdown": "# merged",
                "winner": "mixed",
                "warnings": [],
                "needs_human_review": False,
            },
            call_metadata={
                "response_id": "resp_test",
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            },
        )


class MetadataAssetVisionClient:
    model = "metadata-fake-model"

    def reconcile(self, *, image_path: Path, prompt: str) -> ModelCallResult:
        return ModelCallResult(
            payload={
                "reconciled_markdown": "![seal](imgs/seal.jpg)",
                "winner": "mixed",
                "warnings": [],
                "needs_human_review": False,
            },
            call_metadata={"response_id": "resp_test"},
        )


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
            "needs_human_review": False,
        }


class FakeInputTokensAPI:
    def __init__(self, counts: list[int] | None = None, *, fail: bool = False):
        self.counts = list(counts or [])
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("input token preflight failed")
        if not self.counts:
            raise AssertionError("No fake input token count queued")
        return SimpleNamespace(input_tokens=self.counts.pop(0))


class FakeCountOnlyInputTokensAPI:
    def __init__(self, counts: list[int] | None = None):
        self.counts = list(counts or [])
        self.calls: list[dict[str, object]] = []

    def count(self, **kwargs):
        self.calls.append(kwargs)
        if not self.counts:
            raise AssertionError("No fake input token count queued")
        return SimpleNamespace(input_tokens=self.counts.pop(0))


class FakeResponsesAPI:
    def __init__(
        self,
        payload: dict,
        *,
        usage: object | None = None,
        input_token_counts: list[int] | None = None,
        input_tokens_fail: bool = False,
    ):
        self.payload = payload
        self.usage = usage
        self.calls: list[dict[str, object]] = []
        self.input_tokens = FakeInputTokensAPI(input_token_counts, fail=input_tokens_fail)

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            id="resp_test",
            output_text=json.dumps(self.payload),
            usage=self.usage,
        )


class FakeOpenAISDK:
    def __init__(
        self,
        payload: dict,
        *,
        usage: object | None = None,
        input_token_counts: list[int] | None = None,
        input_tokens_fail: bool = False,
    ):
        self.responses = FakeResponsesAPI(
            payload,
            usage=usage,
            input_token_counts=input_token_counts,
            input_tokens_fail=input_tokens_fail,
        )


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


def test_build_reconcile_prompt_preserves_complex_html_tables(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(
        run_root,
        "union",
        2,
        '<table><tr><td colspan="2">Merged header</td></tr><tr><td>A</td><td>B</td></tr></table>',
    )
    write_page(run_root, "small", 2, "<table><tr><td>A</td><td>B</td></tr></table>")

    prompt = build_reconcile_prompt(load_page_inputs(run_root, 2))

    assert "preserve raw HTML <table>" in prompt
    assert "Use raw HTML <table> markup only when the visible table needs structure" in prompt
    assert "rowspan, colspan, or irregular form layout" in prompt
    assert "needs_human_review=true" in prompt


def test_build_reconcile_prompt_prefers_gfm_for_simple_tables(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(
        run_root,
        "union",
        2,
        "| Depth | Value |\n|---|---:|\n| 100 | 42 |",
    )
    write_page(run_root, "small", 2, "| Depth | Value |\n|---|---:|\n| 100 | 42 |")

    prompt = build_reconcile_prompt(load_page_inputs(run_root, 2))

    assert "Prefer GFM pipe tables for simple rectangular data tables" in prompt
    assert "Every GFM table row must have the same number of cells" in prompt
    assert "If an OCR draft contains raw HTML but the visible table is simple and rectangular" in prompt


def test_build_reconcile_prompt_names_high_risk_and_ambiguity_policy(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 17, "union draft")
    write_page(run_root, "small", 17, "small draft")

    prompt = build_reconcile_prompt(load_page_inputs(run_root, 17))

    assert "Narrow high-risk structures" in prompt
    assert "casing, tubing, cement, formation tops" in prompt
    assert "directional survey, directional targets, and coordinate tables" in prompt
    assert "latitude, longitude, +N/-S offsets, +E/-W offsets" in prompt
    assert "Checkbox groups where the checked or unchecked state changes meaning" in prompt
    assert "Handwritten or crossed-out corrections" in prompt
    assert "Material ambiguity" in prompt
    assert "Do not set needs_human_review=true merely because" in prompt
    assert "warnings are audit notes" in prompt


def test_build_reconcile_prompt_rejects_chart_grid_noise_as_tables(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(
        run_root,
        "union",
        2,
        "<table><tr><td>5600</td><td>000000000000000000000000000000</td></tr></table>",
    )
    write_page(
        run_root,
        "small",
        2,
        "<table><tr><td>5600</td><td>000000000000000000000000000000</td></tr></table>",
    )

    prompt = build_reconcile_prompt(load_page_inputs(run_root, 2))

    assert "Do not convert charts, plots, graph grids" in prompt
    assert "long repeated-character runs" in prompt
    assert "keep supported image references instead of inventing tabular data" in prompt


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


def test_vision_reconciler_records_llm_call_metadata(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 15, "union draft")
    write_page(run_root, "small", 15, "small draft")

    result = VisionReconciler(client=MetadataVisionClient()).reconcile_page(
        load_page_inputs(run_root, 15)
    )

    assert result.llm_calls == (
        {
            "round": 1,
            "model": "metadata-fake-model",
            "prompt_version": DEFAULT_RECONCILE_PROMPT_VERSION,
            "response_id": "resp_test",
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
        },
    )


def test_round_one_false_does_not_run_round_two(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 18, "union draft")
    write_page(run_root, "small", 18, "small draft")
    client = SequencedVisionClient(
        [
            {
                "reconciled_markdown": "# round one",
                "winner": "mixed",
                "warnings": ["audit only"],
                "needs_human_review": False,
            },
            {
                "reconciled_markdown": "# round two should not run",
                "winner": "mixed",
                "warnings": [],
                "needs_human_review": False,
            },
        ]
    )

    result = VisionReconciler(client=client).reconcile_page(load_page_inputs(run_root, 18))

    assert len(client.calls) == 1
    assert result.reconciled_markdown == "# round one"
    assert result.needs_human_review is False
    assert [call["round"] for call in result.llm_calls] == [1]


def test_round_one_true_runs_round_two_and_publishes_round_two_result(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 19, "union draft")
    write_page(run_root, "small", 19, "small draft")
    client = SequencedVisionClient(
        [
            {
                "reconciled_markdown": "# round one\n\nNeeds verification.",
                "winner": "mixed",
                "warnings": ["table alignment uncertain"],
                "needs_human_review": True,
            },
            {
                "reconciled_markdown": "# round two final",
                "winner": "mixed",
                "warnings": [],
                "needs_human_review": False,
            },
        ]
    )

    result = VisionReconciler(client=client).reconcile_page(load_page_inputs(run_root, 19))

    assert len(client.calls) == 2
    assert result.reconciled_markdown == "# round two final"
    assert result.needs_human_review is False
    assert [call["round"] for call in result.llm_calls] == [1, 2]
    round_two_prompt = client.calls[1]["prompt"]
    assert "# round one\n\nNeeds verification." in round_two_prompt
    assert "Candidate round-one Markdown:" in round_two_prompt
    assert "Union OCR draft Markdown:" not in round_two_prompt
    assert "Small OCR draft Markdown:" not in round_two_prompt


def test_round_two_true_leaves_final_page_for_human_review(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 20, "union draft")
    write_page(run_root, "small", 20, "small draft")
    client = SequencedVisionClient(
        [
            {
                "reconciled_markdown": "# round one",
                "winner": "mixed",
                "warnings": ["ambiguous checkbox"],
                "needs_human_review": True,
            },
            {
                "reconciled_markdown": "# round two unresolved",
                "winner": "uncertain",
                "warnings": ["checkbox remains ambiguous"],
                "needs_human_review": True,
            },
        ]
    )

    result = VisionReconciler(client=client).reconcile_page(load_page_inputs(run_root, 20))

    assert len(client.calls) == 2
    assert result.reconciled_markdown == "# round two unresolved"
    assert result.needs_human_review is True
    assert [call["round"] for call in result.llm_calls] == [1, 2]


def test_uncertain_round_one_winner_runs_round_two(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 21, "union draft")
    write_page(run_root, "small", 21, "small draft")
    client = SequencedVisionClient(
        [
            {
                "reconciled_markdown": "# uncertain round one",
                "winner": "uncertain",
                "warnings": [],
                "needs_human_review": False,
            },
            {
                "reconciled_markdown": "# verified round two",
                "winner": "mixed",
                "warnings": [],
                "needs_human_review": False,
            },
        ]
    )

    result = VisionReconciler(client=client).reconcile_page(load_page_inputs(run_root, 21))

    assert len(client.calls) == 2
    assert result.reconciled_markdown == "# verified round two"
    assert result.needs_human_review is False
    assert [call["round"] for call in result.llm_calls] == [1, 2]


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


def test_prepared_publish_preserves_llm_calls(tmp_path):
    run_root = tmp_path / "runs" / "sample-doc"
    write_page(run_root, "union", 16, "# union")
    small_page = write_page(run_root, "small", 16, "# small")
    (small_page / "imgs").mkdir()
    (small_page / "imgs" / "seal.jpg").write_bytes(b"jpeg")
    client = MetadataAssetVisionClient()

    result = run_reconciliation(
        run_root=run_root,
        object_store_root=tmp_path / "object_store",
        sqlite_path=tmp_path / "catalog.sqlite",
        viewer_dir=None,
        client=client,
        pages=[16],
    )

    assert result["published_pages"] == [16]
    decision = json.loads(
        (
            tmp_path
            / "object_store"
            / "pdf-extract"
            / "reconciled"
            / "sample-doc"
            / "pages"
            / "page_0016"
            / "decision.json"
        ).read_text(encoding="utf-8")
    )
    assert decision["llm_calls"][0]["response_id"] == "resp_test"


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
        },
        input_token_counts=[100, 20],
    )
    client = OpenAIResponsesVisionClient(model="gpt-test-vision", sdk_client=fake_sdk)

    response = client.reconcile(image_path=image_path, prompt="reconcile this page")

    assert response.payload["winner"] == "mixed"
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


def test_openai_responses_vision_client_returns_usage_and_token_split_metadata(tmp_path):
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    usage = SimpleNamespace(
        input_tokens=1200,
        input_tokens_details=SimpleNamespace(cached_tokens=100),
        output_tokens=300,
        output_tokens_details=SimpleNamespace(reasoning_tokens=40),
        total_tokens=1500,
    )
    fake_sdk = FakeOpenAISDK(
        {
            "reconciled_markdown": "# merged",
            "winner": "mixed",
            "warnings": [],
            "needs_human_review": False,
        },
        usage=usage,
        input_token_counts=[1200, 200],
    )
    client = OpenAIResponsesVisionClient(model="gpt-5.4-mini", sdk_client=fake_sdk)

    response = client.reconcile(image_path=image_path, prompt="reconcile this page")

    assert isinstance(response, ModelCallResult)
    assert response.payload["winner"] == "mixed"
    assert response.call_metadata["response_id"] == "resp_test"
    assert response.call_metadata["input_tokens"] == 1200
    assert response.call_metadata["cached_input_tokens"] == 100
    assert response.call_metadata["output_tokens"] == 300
    assert response.call_metadata["reasoning_tokens"] == 40
    assert response.call_metadata["total_tokens"] == 1500
    assert response.call_metadata["input_text_tokens_derived"] == 200
    assert response.call_metadata["input_image_tokens_derived"] == 1000
    assert response.call_metadata["input_split_method"] == "responses.input_tokens_delta"
    assert response.call_metadata["image_count"] == 1
    assert response.call_metadata["image_detail"] == "high"
    expected_cost = (
        (1100 / 1_000_000 * 0.75)
        + (100 / 1_000_000 * 0.075)
        + (300 / 1_000_000 * 4.5)
    )
    assert response.call_metadata["estimated_cost_usd"] == pytest.approx(expected_cost)
    assert response.call_metadata["pricing"]["captured_at"] == "2026-06-08"


def test_openai_responses_vision_client_uses_input_token_count_endpoint(tmp_path):
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    fake_sdk = FakeOpenAISDK(
        {
            "reconciled_markdown": "# merged",
            "winner": "mixed",
            "warnings": [],
            "needs_human_review": False,
        }
    )
    fake_sdk.responses.input_tokens = FakeCountOnlyInputTokensAPI([1200, 200])
    client = OpenAIResponsesVisionClient(model="gpt-5.4-mini", sdk_client=fake_sdk)

    response = client.reconcile(image_path=image_path, prompt="reconcile this page")

    assert response.call_metadata["input_split_method"] == "responses.input_tokens_delta"
    assert response.call_metadata["input_text_tokens_derived"] == 200
    assert response.call_metadata["input_image_tokens_derived"] == 1000


def test_openai_responses_vision_client_keeps_content_when_token_preflight_fails(tmp_path):
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    usage = {
        "input_tokens": 1200,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens": 300,
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": 1500,
    }
    fake_sdk = FakeOpenAISDK(
        {
            "reconciled_markdown": "# merged",
            "winner": "mixed",
            "warnings": [],
            "needs_human_review": False,
        },
        usage=usage,
        input_tokens_fail=True,
    )
    client = OpenAIResponsesVisionClient(model="gpt-5.4-mini", sdk_client=fake_sdk)

    response = client.reconcile(image_path=image_path, prompt="reconcile this page")

    assert response.payload["reconciled_markdown"] == "# merged"
    assert response.call_metadata["input_text_tokens_derived"] is None
    assert response.call_metadata["input_image_tokens_derived"] is None
    assert response.call_metadata["input_split_method"] == "unavailable"
    assert "input token preflight failed" in response.call_metadata["accounting_warning"]


def test_openai_responses_vision_client_keeps_content_when_input_token_endpoint_missing(tmp_path):
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    fake_sdk = FakeOpenAISDK(
        {
            "reconciled_markdown": "# merged",
            "winner": "mixed",
            "warnings": [],
            "needs_human_review": False,
        }
    )
    del fake_sdk.responses.input_tokens
    client = OpenAIResponsesVisionClient(model="gpt-5.4-mini", sdk_client=fake_sdk)

    response = client.reconcile(image_path=image_path, prompt="reconcile this page")

    assert response.payload["reconciled_markdown"] == "# merged"
    assert response.call_metadata["input_text_tokens_derived"] is None
    assert response.call_metadata["input_image_tokens_derived"] is None
    assert response.call_metadata["input_split_method"] == "unavailable"


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
