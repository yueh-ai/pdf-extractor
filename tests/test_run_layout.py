import json

import pytest

from pdf_extract.run_layout import mode_run_dir, validate_run_mode, write_document_metadata


def test_mode_run_dir_uses_document_stem_and_mode(tmp_path):
    input_pdf = tmp_path / "Full_30015375000000.pdf"

    assert mode_run_dir(input_pdf, "small", runs_dir=tmp_path / "runs") == (
        tmp_path / "runs" / "Full_30015375000000" / "small"
    )


def test_validate_run_mode_rejects_unknown_mode():
    with pytest.raises(ValueError):
        validate_run_mode("large")


def test_write_document_metadata_records_modes_without_losing_existing_modes(tmp_path):
    input_pdf = tmp_path / "input.pdf"
    input_pdf.write_bytes(b"%PDF")
    root = tmp_path / "runs" / "input"

    write_document_metadata(root, input_pdf=input_pdf, mode="union")
    document_path = write_document_metadata(root, input_pdf=input_pdf, mode="small")

    document = json.loads(document_path.read_text(encoding="utf-8"))
    assert document == {
        "document_stem": "input",
        "input_pdf": str(input_pdf.resolve()),
        "modes": {
            "small": "small",
            "union": "union",
        },
    }
