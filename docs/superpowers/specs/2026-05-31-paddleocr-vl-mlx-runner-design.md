# PaddleOCR-VL MLX Runner Design

## Goal

Build a new Python CLI project that extracts LLM-friendly Markdown, JSON, DOCX, and layout visualization artifacts from scanned or image-heavy PDFs using `PaddleOCRVL` with the MLX VLM server backend. The runner should process full PDFs page by page, show progress, save each page as soon as it completes, and support rerunning/resuming without requiring manual cropping.

## Scope

The first version will include:

- A resumable CLI runner.
- Sequential page processing in one Python process.
- PDF page rendering with `pypdfium2`.
- A single long-lived `PaddleOCRVL` pipeline instance.
- Per-page PaddleOCR output bundles.
- The rendered source page PNG in each page bundle.
- Manifest-based resume behavior.
- Retries, fail-fast behavior, and failed page reporting.
- Combined Markdown and JSONL convenience outputs.

The first version will not include:

- `--isolate-pages` subprocess execution.
- A review UI.
- Form-specific schema extraction.
- Second-pass validation of known sections.

## CLI

The primary entrypoint will be:

```bash
python scripts/run_pdf_vl.py /path/to/input.pdf \
  --out runs/input_vl \
  --server-url http://localhost:8111/ \
  --pages 1-5 \
  --resume \
  --retries 1 \
  --timeout-sec 900
```

Key options:

- `input_pdf`: required PDF path.
- `--out`: run output directory.
- `--pages`: optional page selection such as `1`, `1-5`, or `1,3,7-9`.
- `--resume`: skip completed pages. Enabled by default.
- `--force`: rerun pages even if they look complete.
- `--retries`: retry count after the first failed attempt.
- `--fail-fast`: stop after the first page that remains failed.
- `--timeout-sec`: recorded in config for future subprocess mode; same-process PaddleOCR calls cannot be hard-killed safely.
- `--server-url`: MLX VLM server URL.
- `--model-name`: VLM model name, defaulting to `PaddlePaddle/PaddleOCR-VL-1.6`.
- `--layout-merge-bboxes-mode`: optional diagnostic override, not set by default.
- `--no-save-page-image`: skip rendered page image retention when disk usage matters.

## Output Layout

The run directory will use this layout:

```text
runs/<pdf_stem>_vl/
  config.json
  manifest.jsonl
  failed_pages.txt
  combined.md
  combined.jsonl
  pages/
    page_0001/
      page.png
      layout_det_res.png
      res.json
      output.docx
      output.md
    page_0002/
      page.png
      layout_det_res.png
      res.json
      output.docx
      output.md
```

The per-page bundle is the source of truth. `page.png` is the rendered source page image, while `layout_det_res.png` is PaddleOCR's layout visualization. `combined.md` and `combined.jsonl` are convenience outputs generated from successful page bundles.

## Pipeline

The runner will:

1. Parse CLI arguments and write `config.json`.
2. Determine selected pages from the PDF page count and `--pages`.
3. Load the latest manifest state if resuming.
4. Create a `PaddleOCRVL` instance configured for the MLX VLM server:

```python
PaddleOCRVL(
    pipeline_version="v1.6",
    device="cpu",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_layout_detection=True,
    vl_rec_backend="mlx-vlm-server",
    vl_rec_server_url=server_url,
    vl_rec_api_model_name=model_name,
)
```

5. Render each selected page to `pages/page_NNNN/page.png`.
6. Pass each rendered page image to `pipeline.predict()`.
7. Save the native PaddleOCR result bundle into `pages/page_NNNN/`.
8. Append one manifest entry for each attempt.
9. Continue after page failures unless `--fail-fast` is set.
10. Write `failed_pages.txt`, `combined.md`, and `combined.jsonl` at the end.

## Resume Rules

A page counts as complete only when all conditions are true:

- The latest manifest entry for the page has `status` set to `ok`.
- `pages/page_NNNN/res.json` exists and is non-empty.
- `pages/page_NNNN/output.md` exists and is non-empty.
- `pages/page_NNNN/output.docx` exists and is non-empty.
- `pages/page_NNNN/layout_det_res.png` exists and is non-empty.
- `pages/page_NNNN/page.png` exists and is non-empty, unless `--no-save-page-image` is set.

If any condition fails, the page is eligible to rerun.

## Atomic Writes

Page artifacts will be written to temporary paths first, then atomically renamed into place. This prevents interrupted runs from leaving partial files that look complete.

Manifest entries are append-only JSON lines. The latest entry for a page determines its current status.

## Failure Handling

If a page attempt fails, the runner will append a manifest entry with:

- `page`
- `status`
- `attempt`
- `elapsed_sec`
- `error_type`
- `error`

The runner will retry up to `--retries`. If the page still fails, it will continue to the next page unless `--fail-fast` is set. At the end, all failed page numbers are written to `failed_pages.txt`.

## Testing

Initial tests will cover pure helper behavior:

- Page range parsing.
- Manifest latest-state loading.
- Resume completeness checks.
- Atomic write helper behavior.
- Combined output generation from fixture page bundles.

Smoke tests against real PaddleOCR will be manual because they require the MLX server and model downloads:

```bash
python scripts/run_pdf_vl.py /path/to/input.pdf --out runs/smoke_page1 --pages 1 --resume
python scripts/run_pdf_vl.py /path/to/input.pdf --out runs/smoke_pages_1_3 --pages 1-3 --resume
python scripts/run_pdf_vl.py /path/to/input.pdf --out runs/full --resume
```

## Open Decisions

No open design decisions remain for the first version. `--isolate-pages` is intentionally out of scope because manual reruns are acceptable.
