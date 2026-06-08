from __future__ import annotations

import pytest

from pdf_extract.wellbore_summary import (
    BatchFactResult,
    CandidateFact,
    build_fact_scout_response_format,
    parse_batch_fact_result,
    source_id_for_page,
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
