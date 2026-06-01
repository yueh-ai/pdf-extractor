import json
import sys
import types

import pypdfium2 as pdfium

from pdf_extract.cli import create_arg_parser, create_default_pipeline, main
from pdf_extract.paddle_output import atomic_write_bytes, atomic_write_text


class FakePaddleResult:
    def save_to_json(self, path):
        atomic_write_text(path, json.dumps({"fake": True}))

    def save_to_markdown(self, path):
        atomic_write_text(path, "fake markdown")

    def save_to_img(self, path):
        atomic_write_bytes(path, b"\x89PNG\r\n\x1a\nlayout")

    def save_to_word(self, path):
        atomic_write_bytes(path / "page.docx", b"docx")


class FakePipeline:
    def __init__(self):
        self.calls = []

    def predict(self, input_path, **kwargs):
        self.calls.append((input_path, kwargs))
        return [FakePaddleResult()]


def make_one_page_pdf(path):
    doc = pdfium.PdfDocument.new()
    doc.new_page(width=100, height=100)
    doc.save(path)
    doc.close()


def test_main_processes_one_page_with_fake_pipeline(tmp_path):
    pdf_path = tmp_path / "input.pdf"
    out_dir = tmp_path / "run"
    make_one_page_pdf(pdf_path)
    pipeline = FakePipeline()

    exit_code = main(
        [str(pdf_path), "--out", str(out_dir), "--pages", "1"],
        pipeline_factory=lambda _args: pipeline,
    )

    assert exit_code == 0
    page_dir = out_dir / "pages" / "page_0001"
    assert (page_dir / "page.png").read_bytes().startswith(b"\x89PNG")
    assert (page_dir / "layout_det_res.png").read_bytes().startswith(b"\x89PNG")
    assert json.loads((page_dir / "res.json").read_text(encoding="utf-8")) == {
        "fake": True
    }
    assert (page_dir / "output.md").read_text(encoding="utf-8") == "fake markdown"
    assert (page_dir / "output.docx").read_bytes() == b"docx"
    assert '"status": "ok"' in (out_dir / "manifest.jsonl").read_text(encoding="utf-8")
    assert "fake markdown" in (out_dir / "combined.md").read_text(encoding="utf-8")
    assert (out_dir / "failed_pages.txt").read_text(encoding="utf-8") == ""
    assert len(pipeline.calls) == 1


def test_run_mode_small_uses_document_small_dir_and_layout_override(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pdf_path = tmp_path / "input.pdf"
    make_one_page_pdf(pdf_path)
    pipeline = FakePipeline()

    exit_code = main(
        [str(pdf_path), "--run-mode", "small", "--pages", "1"],
        pipeline_factory=lambda _args: pipeline,
    )

    assert exit_code == 0
    run_dir = tmp_path / "runs" / "input" / "small"
    assert (run_dir / "pages" / "page_0001" / "output.md").read_text(
        encoding="utf-8"
    ) == "fake markdown"
    assert json.loads((run_dir / "config.json").read_text(encoding="utf-8"))[
        "run_mode"
    ] == "small"
    assert json.loads((run_dir / "config.json").read_text(encoding="utf-8"))[
        "layout_merge_bboxes_mode"
    ] == "small"
    assert pipeline.calls[0][1] == {"layout_merge_bboxes_mode": "small"}


def test_run_mode_union_uses_document_union_dir_without_layout_override(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    pdf_path = tmp_path / "input.pdf"
    make_one_page_pdf(pdf_path)
    pipeline = FakePipeline()

    exit_code = main(
        [str(pdf_path), "--run-mode", "union", "--pages", "1"],
        pipeline_factory=lambda _args: pipeline,
    )

    assert exit_code == 0
    run_dir = tmp_path / "runs" / "input" / "union"
    assert (run_dir / "pages" / "page_0001" / "output.md").exists()
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    assert config["run_mode"] == "union"
    assert config["layout_merge_bboxes_mode"] is None
    assert pipeline.calls[0][1] == {}


def test_default_output_without_run_mode_uses_document_union_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pdf_path = tmp_path / "input.pdf"
    make_one_page_pdf(pdf_path)
    pipeline = FakePipeline()

    exit_code = main(
        [str(pdf_path), "--pages", "1"],
        pipeline_factory=lambda _args: pipeline,
    )

    assert exit_code == 0
    run_dir = tmp_path / "runs" / "input" / "union"
    assert (run_dir / "pages" / "page_0001" / "output.md").exists()
    assert not (tmp_path / "runs" / "input_vl").exists()
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    assert config["run_mode"] == "union"
    assert config["layout_merge_bboxes_mode"] is None
    assert pipeline.calls[0][1] == {}


def test_default_run_mode_rejects_layout_override_without_small_mode(tmp_path):
    pdf_path = tmp_path / "input.pdf"
    make_one_page_pdf(pdf_path)

    exit_code = main(
        [
            str(pdf_path),
            "--layout-merge-bboxes-mode",
            "small",
            "--pages",
            "1",
        ],
        pipeline_factory=lambda _args: FakePipeline(),
    )

    assert exit_code == 2


def test_default_run_mode_with_explicit_out_does_not_write_document_metadata(tmp_path):
    pdf_path = tmp_path / "input.pdf"
    out_dir = tmp_path / "runs" / "smoke_page1"
    make_one_page_pdf(pdf_path)

    exit_code = main(
        [str(pdf_path), "--out", str(out_dir), "--pages", "1"],
        pipeline_factory=lambda _args: FakePipeline(),
    )

    assert exit_code == 0
    config = json.loads((out_dir / "config.json").read_text(encoding="utf-8"))
    assert config["run_mode"] == "union"
    assert not (out_dir.parent / "document.json").exists()


def test_run_mode_small_rejects_conflicting_layout_override(tmp_path):
    pdf_path = tmp_path / "input.pdf"
    make_one_page_pdf(pdf_path)

    exit_code = main(
        [
            str(pdf_path),
            "--run-mode",
            "small",
            "--layout-merge-bboxes-mode",
            "large",
            "--pages",
            "1",
        ],
        pipeline_factory=lambda _args: FakePipeline(),
    )

    assert exit_code == 2


def test_main_resume_skips_complete_page(tmp_path):
    pdf_path = tmp_path / "input.pdf"
    out_dir = tmp_path / "run"
    make_one_page_pdf(pdf_path)
    pipeline = FakePipeline()

    assert (
        main(
            [str(pdf_path), "--out", str(out_dir), "--pages", "1"],
            pipeline_factory=lambda _args: pipeline,
        )
        == 0
    )
    assert (
        main(
            [str(pdf_path), "--out", str(out_dir), "--pages", "1", "--resume"],
            pipeline_factory=lambda _args: pipeline,
        )
        == 0
    )

    assert len(pipeline.calls) == 1


def test_arg_parser_defaults_vl_rec_max_concurrency_to_one():
    parser = create_arg_parser()

    args = parser.parse_args(["input.pdf"])

    assert args.vl_rec_max_concurrency == 1


def test_create_default_pipeline_passes_vl_rec_max_concurrency(monkeypatch):
    captured = {}

    class FakePaddleOCRVL:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setitem(
        sys.modules,
        "paddleocr",
        types.SimpleNamespace(PaddleOCRVL=FakePaddleOCRVL),
    )
    parser = create_arg_parser()
    args = parser.parse_args(["input.pdf", "--vl-rec-max-concurrency", "3"])

    create_default_pipeline(args)

    assert captured["vl_rec_max_concurrency"] == 3
