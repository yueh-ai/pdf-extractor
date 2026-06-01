# Handoff: Resumable PDF Extraction with PaddleOCR-VL + MLX

## Goal

Build a new project that extracts LLM-friendly Markdown/JSON context from scanned or image-heavy PDFs using PaddleOCR-VL-1.6. The runner should process full PDFs without manual cropping, show progress, survive mid-run failures, and use Apple Silicon MLX acceleration for the VLM recognition stage.

## Key Lessons From The PaddleOCR Test

- `PP-StructureV3` was fast enough to test, but on the sample form it over-merged a large lower-page region into one table and scrambled important content.
- `PaddleOCR-VL-1.6` via `doc_parser` produced much better page-level content and recognized difficult table values such as casing fractions.
- `layout_merge_bboxes_mode=small` made the Section 21 casing table cleaner, but dropped the Section 22 narrative. Do not make it the default for full-document extraction.
- The best general default is `PaddleOCR-VL-1.6` with normal layout detection, then downstream validation and cleanup.
- Manual cropping is useful for diagnosis, but should not be the main production path.

## Important MLX Detail

The MLX server is only the VLM inference backend. It is not the complete document parser.

The full pipeline still runs through `PaddleOCRVL`, which handles document preprocessing, layout detection, page/block orchestration, Markdown/JSON result construction, and calls the MLX server for the VLM recognition stage.

Do not send PDFs directly to `mlx_vlm.server` as if it were an end-to-end parser.

## Pipeline Granularity

With the normal default path, `PaddleOCRVL` does not send a whole multi-page PDF to the VLM. It treats PDF pages as separate page instances, runs document preprocessing and layout detection per page, then sends layout block images to the VLM recognition module. Those VLM calls may be batched internally for efficiency, but the units are page-derived blocks, not the entire PDF.

If `use_layout_detection=False`, the pipeline creates one full-page block and sends that whole page image to the VLM with the selected prompt label. This is useful as a diagnostic path, but it was slow on CPU during our test and is not the recommended default.

The custom runner should still process one rendered page at a time because that gives us explicit progress, checkpointing, resume behavior, retries, and timeout isolation. The built-in pipeline has page-level results, but it does not provide the robust job manifest/resume semantics we want for long PDFs.

## Environment Setup

Recommended on Apple Silicon:

```bash
python -m venv .venv
source .venv/bin/activate

python -m pip install paddlepaddle==3.2.1 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
python -m pip install -U "paddleocr[doc-parser]"
python -m pip install "mlx-vlm>=0.3.11" tqdm pypdfium2 pillow
```

If large model downloads behave oddly, set:

```bash
export HF_HUB_DISABLE_XET=1
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
```

Start the MLX VLM service in a separate terminal:

```bash
source .venv/bin/activate
mlx_vlm.server --port 8111
```

## Python API Wiring

Use `PaddleOCRVL` with the MLX backend:

```python
from paddleocr import PaddleOCRVL

pipeline = PaddleOCRVL(
    pipeline_version="v1.6",
    device="cpu",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    vl_rec_backend="mlx-vlm-server",
    vl_rec_server_url="http://localhost:8111/",
    vl_rec_api_model_name="PaddlePaddle/PaddleOCR-VL-1.6",
)
```

Do not pass the whole 219-page PDF to `pipeline.predict()` as one monolithic job. Render and process one page image at a time so progress, checkpointing, retries, and failure isolation are simple.

## Runner Requirements

Create a script like:

```bash
python scripts/run_pdf_vl.py /path/to/input.pdf \
  --out runs/input_vl \
  --backend mlx \
  --server-url http://localhost:8111/ \
  --pages 1-5 \
  --resume \
  --retries 1 \
  --timeout-sec 900
```

Core behavior:

- Render PDF pages to images with `pypdfium2` or PyMuPDF.
- Process pages sequentially by default.
- Show a `tqdm` progress bar with page number, status, and elapsed time.
- Save each page immediately after it completes.
- Resume by default: skip pages with completed output and an `ok` manifest entry.
- Never wait until the full PDF finishes before writing results.
- Keep the pipeline loaded once for normal mode to avoid reloading the VLM for every page.
- Add an optional `--isolate-pages` mode later, where each page or small batch runs in a child process. This is slower but protects long jobs from hard crashes or hangs.

## Output Layout

Use a run directory like:

```text
runs/<pdf_stem>_vl/
  config.json
  manifest.jsonl
  failed_pages.txt
  page_images/
    page_0001.png
    page_0002.png
  pages/
    page_0001.json
    page_0001.md
    page_0001_layout_det_res.png
    page_0002.json
    page_0002.md
  combined.md
  combined.jsonl
```

`page_images/` can be optional if disk space matters, but keeping images during development makes debugging much easier.

## Manifest Format

Append one JSON line per page attempt:

```json
{"page":1,"status":"ok","attempt":1,"elapsed_sec":58.2,"image":"page_images/page_0001.png","json":"pages/page_0001.json","md":"pages/page_0001.md"}
{"page":2,"status":"failed","attempt":1,"elapsed_sec":900.0,"error_type":"TimeoutError","error":"page timed out"}
```

On resume, a page counts as complete only if:

- latest manifest entry for that page is `status="ok"`;
- expected JSON and Markdown files exist;
- files are non-empty.

Write page results to temporary paths first, then atomically rename them into place. This prevents a crash from leaving corrupt files that look complete.

## Failure Handling

If a page fails:

- record the exception type and message in `manifest.jsonl`;
- optionally retry up to `--retries`;
- continue to the next page unless `--fail-fast` is set;
- write failed page numbers to `failed_pages.txt` at the end.

If the process dies midway:

- completed page files remain usable;
- rerunning with `--resume` continues from unfinished or failed pages;
- use `--force` to rerun everything.

Timeouts are hard to enforce safely in the same Python process because the model call may block inside native code. For strict timeout enforcement, use `--isolate-pages` and run each page in a subprocess.

## Recommended Defaults

Use these defaults first:

```python
PaddleOCRVL(
    pipeline_version="v1.6",
    device="cpu",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_layout_detection=True,
    vl_rec_backend="mlx-vlm-server",
    vl_rec_server_url="http://localhost:8111/",
    vl_rec_api_model_name="PaddlePaddle/PaddleOCR-VL-1.6",
)
```

Do not default to:

```python
layout_merge_bboxes_mode="small"
```

It can improve a contained table but may remove nearby narrative text that only appears in a larger overlapping block.

Keep it as a diagnostic or second-pass option.

## Validation Checks

After each run, verify:

- total pages expected vs. total `ok` pages;
- `failed_pages.txt` is empty or intentionally accepted;
- key phrases are present in Markdown for important pages;
- Section 21 style tables have plausible columns and values;
- narrative blocks like `MUD PROGRAM`, `BOPE PROGRAM`, and `H2S IS NOT ANTICIPATED` are present when expected.

For the sample PDF, page 1 should preserve:

- `Proposed Casing and Cement Program`
- `17 1/2"`, `13 3/8"`, `12 1/4"`, `9 5/8"`, `4 1/2"`
- `MUD PROGRAM`
- `BOPE PROGRAM`
- `H2S IS NOT ANTICIPATED`

## First Smoke Tests

Run in this order:

```bash
python scripts/run_pdf_vl.py /path/to/input.pdf --out runs/smoke_page1 --pages 1 --resume
python scripts/run_pdf_vl.py /path/to/input.pdf --out runs/smoke_pages_1_3 --pages 1-3 --resume
python scripts/run_pdf_vl.py /path/to/input.pdf --out runs/full --resume
```

Do not start with the full PDF until page 1 and a short page range both produce acceptable output.

## Future Improvements

- Add schema extraction for known form sections after Markdown/JSON generation.
- Add a second-pass validator for suspicious tables, missing required phrases, or impossible field values.
- Add `--isolate-pages` for long overnight jobs.
- Add `--retry-failed-only`.
- Add a small HTML review UI for comparing page image, layout boxes, Markdown, and validation warnings.
