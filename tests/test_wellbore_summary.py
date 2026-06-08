from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf_extract.wellbore_summary import (
    BatchFactResult,
    CandidateFact,
    ReconciledSummaryPage,
    SummaryBatch,
    run_fact_scout_batches,
    build_fact_scout_prompt,
    build_fact_scout_response_format,
    build_summary_batches,
    discover_reconciled_summary_pages,
    page_number_from_source_id,
    parse_batch_fact_result,
    source_id_for_page,
    write_fact_ledger,
)


def valid_payload() -> dict:
    return {
        "facts": [
            {
                "section": "casing_and_tubing_strings",
                "field": "production_casing",
                "value": "5-1/2 inch casing set at 10,490 ft",
                "source_page_ids": ["page_0028"],
                "source_context": "C-105 completion report casing table",
                "source_snippet": "5-1/2 ... 10,490",
                "status_hint": "actual",
                "confidence": "high",
                "notes": "Completion table supports the production casing setting depth.",
            }
        ],
        "warnings": [],
    }


class FakeTextClient:
    model = "fake-text-model"

    def __init__(
        self,
        json_responses: list[dict] | None = None,
        text_response: str = "",
    ):
        self.json_responses = list(json_responses or [])
        self.text_response = text_response
        self.json_calls: list[dict] = []
        self.text_calls: list[dict] = []

    def create_json(self, *, prompt: str, response_format: dict) -> dict:
        self.json_calls.append(
            {"prompt": prompt, "response_format": response_format}
        )
        if not self.json_responses:
            raise AssertionError("Unexpected create_json call")
        return self.json_responses.pop(0)

    def create_text(self, *, prompt: str) -> str:
        self.text_calls.append({"prompt": prompt})
        return self.text_response


def test_source_id_for_page_formats_four_digits():
    assert source_id_for_page(1) == "page_0001"
    assert source_id_for_page(28) == "page_0028"


def test_parse_batch_fact_result_accepts_valid_payload():
    result = parse_batch_fact_result(
        payload=valid_payload(),
        document_id="Full_30015375000000",
        batch_id="pages_0028_0037",
        batch_pages=(28, 29, 30),
        allowed_source_ids=("page_0028", "page_0029", "page_0030"),
        model="fake-model",
        prompt_version="wellbore-fact-scout-v1",
    )

    assert isinstance(result, BatchFactResult)
    assert isinstance(result.facts[0], CandidateFact)
    assert result.batch_pages == (28, 29, 30)
    assert result.facts[0].source_page_ids == ("page_0028",)
    assert result.facts[0].status_hint == "actual"


def test_parse_batch_fact_result_rejects_malformed_fact_entry():
    payload = {"facts": ["bad"], "warnings": []}

    with pytest.raises(ValueError, match="fact must be an object"):
        parse_batch_fact_result(
            payload=payload,
            document_id="doc",
            batch_id="pages_0028_0037",
            batch_pages=(28,),
            allowed_source_ids=("page_0028",),
            model="fake-model",
            prompt_version="wellbore-fact-scout-v1",
        )


@pytest.mark.parametrize("warnings", ["bad", [1]])
def test_parse_batch_fact_result_rejects_invalid_warnings_shape(warnings):
    payload = valid_payload()
    payload["warnings"] = warnings

    with pytest.raises(ValueError, match=r"warnings must be a list\[str\]"):
        parse_batch_fact_result(
            payload=payload,
            document_id="doc",
            batch_id="pages_0028_0037",
            batch_pages=(28,),
            allowed_source_ids=("page_0028",),
            model="fake-model",
            prompt_version="wellbore-fact-scout-v1",
        )


def test_parse_batch_fact_result_dedupes_source_ids_in_first_seen_order():
    payload = valid_payload()
    payload["facts"][0]["source_page_ids"] = [
        "page_0029",
        "page_0028",
        "page_0029",
    ]

    result = parse_batch_fact_result(
        payload=payload,
        document_id="doc",
        batch_id="pages_0028_0037",
        batch_pages=(28, 29),
        allowed_source_ids=("page_0028", "page_0029"),
        model="fake-model",
        prompt_version="wellbore-fact-scout-v1",
    )

    assert result.facts[0].source_page_ids == ("page_0029", "page_0028")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("section", "bad_section", "Unsupported section"),
        ("status_hint", "current", "Unsupported status_hint"),
        ("confidence", "certain", "Unsupported confidence"),
    ],
)
def test_parse_batch_fact_result_rejects_invalid_enums(field, value, message):
    payload = valid_payload()
    payload["facts"][0][field] = value

    with pytest.raises(ValueError, match=message):
        parse_batch_fact_result(
            payload=payload,
            document_id="doc",
            batch_id="pages_0028_0037",
            batch_pages=(28,),
            allowed_source_ids=("page_0028",),
            model="fake-model",
            prompt_version="wellbore-fact-scout-v1",
        )


def test_parse_batch_fact_result_rejects_numeric_page_citation():
    payload = valid_payload()
    payload["facts"][0]["source_page_ids"] = [28]

    with pytest.raises(ValueError, match="source_page_ids must be strings"):
        parse_batch_fact_result(
            payload=payload,
            document_id="doc",
            batch_id="pages_0028_0037",
            batch_pages=(28,),
            allowed_source_ids=("page_0028",),
            model="fake-model",
            prompt_version="wellbore-fact-scout-v1",
        )


def test_parse_batch_fact_result_rejects_source_outside_manifest():
    payload = valid_payload()
    payload["facts"][0]["source_page_ids"] = ["page_9999"]

    with pytest.raises(ValueError, match="outside batch source manifest"):
        parse_batch_fact_result(
            payload=payload,
            document_id="doc",
            batch_id="pages_0028_0037",
            batch_pages=(28,),
            allowed_source_ids=("page_0028",),
            model="fake-model",
            prompt_version="wellbore-fact-scout-v1",
        )


def test_parse_batch_fact_result_requires_source_snippet():
    payload = valid_payload()
    payload["facts"][0]["source_snippet"] = ""

    with pytest.raises(ValueError, match="source_snippet is required"):
        parse_batch_fact_result(
            payload=payload,
            document_id="doc",
            batch_id="pages_0028_0037",
            batch_pages=(28,),
            allowed_source_ids=("page_0028",),
            model="fake-model",
            prompt_version="wellbore-fact-scout-v1",
        )


def test_build_fact_scout_response_format_limits_source_ids_to_batch():
    schema = build_fact_scout_response_format(("page_0028", "page_0029"))
    facts = schema["schema"]["properties"]["facts"]["items"]["properties"]

    assert facts["source_page_ids"]["items"]["enum"] == ["page_0028", "page_0029"]
    assert schema["schema"]["additionalProperties"] is False


def write_reconciled_page(
    root: Path,
    document_id: str,
    page: int,
    markdown: str,
    *,
    review: bool = False,
) -> None:
    page_dir = (
        root
        / "pdf-extract"
        / "reconciled"
        / document_id
        / "pages"
        / f"page_{page:04d}"
    )
    page_dir.mkdir(parents=True)
    (page_dir / "output.md").write_text(markdown, encoding="utf-8")
    (page_dir / "decision.json").write_text(
        json.dumps({"needs_human_review": review}) + "\n",
        encoding="utf-8",
    )


def test_page_number_from_source_id_parses_source_id():
    assert page_number_from_source_id("page_0028") == 28
    with pytest.raises(ValueError, match="Invalid source_id"):
        page_number_from_source_id("28")


def test_discover_reconciled_summary_pages_reads_sorted_pages_and_metadata(tmp_path):
    root = tmp_path / "object_store"
    write_reconciled_page(root, "doc", 2, "second page", review=True)
    write_reconciled_page(root, "doc", 1, "first page")

    pages_root = root / "pdf-extract" / "reconciled" / "doc" / "pages"
    (pages_root / "page_0003").mkdir()
    (pages_root / "not-a-page").mkdir()

    pages = discover_reconciled_summary_pages(
        object_store_root=root,
        document_id="doc",
    )

    assert [page.page for page in pages] == [1, 2]
    assert pages[0].source_id == "page_0001"
    assert pages[0].markdown_key == (
        "pdf-extract/reconciled/doc/pages/page_0001/output.md"
    )
    assert pages[0].needs_human_review is False
    assert pages[1].needs_human_review is True
    assert pages[1].markdown == "second page"


def test_discover_reconciled_summary_pages_defaults_false_for_malformed_decision(
    tmp_path,
):
    root = tmp_path / "object_store"
    write_reconciled_page(root, "doc", 1, "first page", review=True)
    decision_path = (
        root
        / "pdf-extract"
        / "reconciled"
        / "doc"
        / "pages"
        / "page_0001"
        / "decision.json"
    )
    decision_path.write_text("{not json", encoding="utf-8")

    pages = discover_reconciled_summary_pages(
        object_store_root=root,
        document_id="doc",
    )

    assert len(pages) == 1
    assert pages[0].needs_human_review is False


def test_build_summary_batches_uses_ten_pages_with_one_overlap():
    pages = tuple(
        ReconciledSummaryPage(
            document_id="doc",
            page=page,
            source_id=source_id_for_page(page),
            markdown_key=f"key-{page}",
            markdown=f"page {page}",
            needs_human_review=False,
        )
        for page in range(1, 22)
    )

    batches = build_summary_batches(pages, batch_size=10, overlap=1)

    assert all(isinstance(batch, SummaryBatch) for batch in batches)
    assert [batch.batch_id for batch in batches] == [
        "pages_0001_0010",
        "pages_0010_0019",
        "pages_0019_0021",
    ]
    assert [[page.page for page in batch.pages] for batch in batches] == [
        list(range(1, 11)),
        list(range(10, 20)),
        [19, 20, 21],
    ]


def test_build_summary_batches_rejects_overlap_not_less_than_batch_size():
    pages = (
        ReconciledSummaryPage(
            document_id="doc",
            page=1,
            source_id="page_0001",
            markdown_key="key",
            markdown="text",
            needs_human_review=False,
        ),
    )

    with pytest.raises(ValueError, match="overlap must be smaller"):
        build_summary_batches(pages, batch_size=10, overlap=10)


def test_build_fact_scout_prompt_uses_source_manifest_and_boundaries():
    batch = SummaryBatch(
        document_id="doc",
        batch_id="pages_0028_0029",
        pages=(
            ReconciledSummaryPage(
                document_id="doc",
                page=28,
                source_id="page_0028",
                markdown_key="key-28",
                markdown="C-105 casing table",
                needs_human_review=False,
            ),
            ReconciledSummaryPage(
                document_id="doc",
                page=29,
                source_id="page_0029",
                markdown_key="key-29",
                markdown="Formation tops table",
                needs_human_review=False,
            ),
        ),
    )

    prompt = build_fact_scout_prompt(batch)

    assert "Document ID: doc" in prompt
    assert "Batch ID: pages_0028_0029" in prompt
    assert "Source manifest:" in prompt
    assert "- source_id: page_0028" in prompt
    assert "===== BEGIN SOURCE page_0028 =====" in prompt
    assert "===== END SOURCE page_0029 =====" in prompt
    assert "Do not cite page numbers printed inside the PDF/form/Markdown." in prompt
    assert "source_page_ids" in prompt
    assert "C-105 casing table" in prompt
    assert "Formation tops table" in prompt


def test_run_fact_scout_batches_calls_client_with_batch_schema():
    page = ReconciledSummaryPage(
        document_id="doc",
        page=28,
        source_id="page_0028",
        markdown_key="key",
        markdown="5-1/2 casing",
        needs_human_review=False,
    )
    batch = SummaryBatch(
        document_id="doc",
        batch_id="pages_0028_0028",
        pages=(page,),
    )
    client = FakeTextClient(json_responses=[valid_payload()])

    results = run_fact_scout_batches((batch,), client=client)

    assert len(results) == 1
    assert results[0].facts[0].field == "production_casing"
    fact_properties = client.json_calls[0]["response_format"]["schema"]["properties"][
        "facts"
    ]["items"]["properties"]
    assert fact_properties["source_page_ids"]["items"]["enum"] == ["page_0028"]
    assert "===== BEGIN SOURCE page_0028 =====" in client.json_calls[0]["prompt"]


def test_write_fact_ledger_writes_one_json_object_per_batch(tmp_path):
    result = parse_batch_fact_result(
        payload=valid_payload(),
        document_id="doc",
        batch_id="pages_0028_0028",
        batch_pages=(28,),
        allowed_source_ids=("page_0028",),
        model="fake-model",
        prompt_version="wellbore-fact-scout-v1",
    )
    path = tmp_path / "nested" / "fact_ledger.jsonl"

    written = write_fact_ledger(path, (result,))

    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert written == path
    assert len(rows) == 1
    assert rows[0]["batch_id"] == "pages_0028_0028"
    assert rows[0]["facts"][0]["source_page_ids"] == ["page_0028"]
