from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf_extract.wellbore_summary import (
    BatchFactResult,
    CandidateFact,
    OpenAIResponsesTextClient,
    ReconciledSummaryPage,
    SummaryBatch,
    build_reducer_prompt,
    run_fact_scout_batches,
    build_fact_scout_prompt,
    build_fact_scout_response_format,
    build_summary_batches,
    dedupe_candidate_facts,
    discover_reconciled_summary_pages,
    display_pages_for_fact,
    page_number_from_source_id,
    parse_batch_fact_result,
    run_wellbore_summary,
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


def make_fact(**overrides) -> CandidateFact:
    data = {
        "section": "elevations",
        "field": "ground_level_elevation",
        "value": "3172'GR",
        "source_page_ids": ("page_0010",),
        "source_context": "C-103 subsequent report header",
        "source_snippet": "3172'GR",
        "status_hint": "actual",
        "confidence": "high",
        "notes": "Repeated GR elevation.",
    }
    data.update(overrides)
    return CandidateFact(**data)


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


def test_display_pages_for_fact_maps_source_ids_to_numbers():
    fact = make_fact(source_page_ids=("page_0028", "page_0030"))

    assert display_pages_for_fact(fact) == "28, 30"


def test_dedupe_candidate_facts_merges_duplicate_overlap_pages():
    first = make_fact(
        source_page_ids=("page_0010",),
        notes="First copy.",
        source_snippet="3172 GR",
    )
    second = make_fact(
        source_page_ids=("page_0010", "page_0011"),
        notes="Second copy.",
        source_snippet="3172'GR",
    )

    merged = dedupe_candidate_facts((first, second))

    assert len(merged) == 1
    assert merged[0].source_page_ids == ("page_0010", "page_0011")
    assert merged[0].source_snippet == "3172 GR | 3172'GR"
    assert "First copy." in merged[0].notes
    assert "Second copy." in merged[0].notes


def test_dedupe_candidate_facts_uses_highest_confidence():
    low = make_fact(confidence="low")
    high = make_fact(confidence="high")

    merged = dedupe_candidate_facts((low, high))

    assert len(merged) == 1
    assert merged[0].confidence == "high"


def test_dedupe_candidate_facts_keeps_different_context_separate():
    header = make_fact(source_context="C-103 subsequent report header")
    diagram = make_fact(source_context="Wellbore diagram")

    merged = dedupe_candidate_facts((header, diagram))

    assert len(merged) == 2


def test_dedupe_candidate_facts_orders_source_ids_by_page_number():
    first = make_fact(source_page_ids=("page_10000",))
    second = make_fact(source_page_ids=("page_9999",))

    merged = dedupe_candidate_facts((first, second))

    assert len(merged) == 1
    assert merged[0].source_page_ids == ("page_9999", "page_10000")


def test_dedupe_candidate_facts_keeps_different_status_separate():
    actual = make_fact(status_hint="actual")
    proposed = make_fact(status_hint="proposed")

    merged = dedupe_candidate_facts((actual, proposed))

    assert len(merged) == 2


def test_build_reducer_prompt_includes_source_display_mapping():
    facts = (make_fact(source_page_ids=("page_0028",)),)

    prompt = build_reducer_prompt(facts, document_id="doc")

    assert "Source PDF Page" in prompt
    assert "Display source pages: 28" in prompt
    assert "page_0028" in prompt
    assert "Do not mention batches, prompts, fact IDs, or model behavior." in prompt


def test_run_wellbore_summary_writes_ledger_and_summary(tmp_path):
    object_store = tmp_path / "object_store"
    write_reconciled_page(
        object_store,
        "doc",
        1,
        "C-105 completion report 5-1/2 casing",
    )
    write_reconciled_page(object_store, "doc", 2, "Formation tops table")
    client = FakeTextClient(
        json_responses=[
            {
                "facts": [
                    {
                        "section": "casing_and_tubing_strings",
                        "field": "production_casing",
                        "value": "5-1/2 casing set at 10,490 ft",
                        "source_page_ids": ["page_0001"],
                        "source_context": "C-105 completion report casing table",
                        "source_snippet": "5-1/2 casing ... 10,490",
                        "status_hint": "actual",
                        "confidence": "high",
                        "notes": "Actual completion casing.",
                    }
                ],
                "warnings": [],
            }
        ],
        text_response=(
            "### Casing And Tubing Strings\n\n"
            "| Diameter | Setting Depth | Source PDF Page | Notes |\n"
            "| --- | --- | --- | --- |\n"
            "| 5-1/2 in | 10,490 ft | 1 | Actual completion casing. |\n"
        ),
    )

    result = run_wellbore_summary(
        object_store_root=object_store,
        document_id="doc",
        out_dir=tmp_path / "summary",
        client=client,
    )

    assert Path(result["fact_ledger_path"]).is_file()
    summary_path = Path(result["summary_path"])
    assert summary_path.is_file()
    assert summary_path.read_text(encoding="utf-8").startswith("### Casing")
    assert result["document_id"] == "doc"
    assert result["page_count"] == 2
    assert result["batch_count"] == 1
    assert result["fact_count"] == 1
    assert len(client.json_calls) == 1
    assert len(client.text_calls) == 1


def test_run_wellbore_summary_accepts_positional_required_arguments(tmp_path):
    object_store = tmp_path / "object_store"
    write_reconciled_page(
        object_store,
        "doc",
        1,
        "C-105 completion report 5-1/2 casing",
    )
    client = FakeTextClient(
        json_responses=[
            {
                "facts": [
                    {
                        "section": "casing_and_tubing_strings",
                        "field": "production_casing",
                        "value": "5-1/2 casing set at 10,490 ft",
                        "source_page_ids": ["page_0001"],
                        "source_context": "C-105 completion report casing table",
                        "source_snippet": "5-1/2 casing ... 10,490",
                        "status_hint": "actual",
                        "confidence": "high",
                        "notes": "Actual completion casing.",
                    }
                ],
                "warnings": [],
            }
        ],
        text_response="### Casing And Tubing Strings\n",
    )

    result = run_wellbore_summary(
        object_store,
        "doc",
        tmp_path / "summary",
        client,
    )

    assert Path(result["fact_ledger_path"]).is_file()
    assert Path(result["summary_path"]).is_file()
    assert result["batch_count"] == 1
    assert result["fact_count"] == 1
    assert len(client.json_calls) == 1
    assert len(client.text_calls) == 1


def test_openai_responses_text_client_uses_json_schema_and_text_calls():
    class FakeResponses:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            if "text" in kwargs:
                return type(
                    "Response",
                    (),
                    {"output_text": json.dumps({"facts": [], "warnings": []})},
                )()
            return type("Response", (), {"output_text": "### Summary\n"})()

    class FakeSDK:
        def __init__(self):
            self.responses = FakeResponses()

    sdk = FakeSDK()
    client = OpenAIResponsesTextClient(model="fake-openai", sdk_client=sdk)

    payload = client.create_json(
        prompt="extract",
        response_format=build_fact_scout_response_format(("page_0001",)),
    )
    text = client.create_text(prompt="reduce")

    assert payload == {"facts": [], "warnings": []}
    assert text == "### Summary\n"
    assert sdk.responses.calls[0]["model"] == "fake-openai"
    assert sdk.responses.calls[0]["text"]["format"]["name"] == (
        "wellbore_batch_fact_result"
    )
    assert sdk.responses.calls[0]["input"][0]["content"][0]["text"] == "extract"
    assert "text" not in sdk.responses.calls[1]
    assert sdk.responses.calls[1]["input"][0]["content"][0]["text"] == "reduce"
