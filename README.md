# PDF Extract

Resumable PDF extraction runner for `PaddleOCR-VL-1.6` with the MLX VLM server backend.

The runner processes a PDF one rendered page at a time. For each page it saves the original rendered page image, PaddleOCR layout visualization, JSON, DOCX, and Markdown immediately, then writes combined Markdown/JSONL outputs for the pages that completed.

## Outputs

A single extraction run directory looks like this:

```text
runs/<name>/
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
```

Per-page files:

- `page.png`: the real rendered source PDF page that was sent to PaddleOCR.
- `layout_det_res.png`: PaddleOCR's visual layout detection result with boxes/annotations.
- `res.json`: PaddleOCR's structured JSON output for the page.
- `output.docx`: PaddleOCR's Word export for the page.
- `output.md`: PaddleOCR's Markdown export for the page.

Run-level files:

- `config.json`: the command configuration recorded for the run.
- `manifest.jsonl`: append-only page attempt log. Successful and failed attempts are both recorded.
- `failed_pages.txt`: page numbers that failed after retries. Empty means the selected pages completed.
- `combined.md`: completed page Markdown joined together, with `# Page N` headers.
- `combined.jsonl`: one JSON object per completed page.

For dual-mode extraction and later reconciliation, use the document layout:

```text
runs/<pdf_stem>/
  document.json
  union/
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
  small/
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
```

`union` uses the default PaddleOCR layout merge behavior. `small` passes
`layout_merge_bboxes_mode="small"`.

## Recommended Setup

On Apple Silicon, use PaddleOCR for the document parser and MLX only as the VLM inference backend. The MLX server is not an end-to-end PDF parser.

Use `uv` for this repo:

```bash
cd /Users/yuehu/projects/pdf-extract

uv venv
uv sync --extra dev --extra paddle
```

The `paddle` extra includes `paddleocr[doc-parser]`, `paddlepaddle>=3.2.1,<3.4`, and `python-docx` for DOCX export. `paddlepaddle` is pinned to Paddle's CPU wheel index in `pyproject.toml`; `uv.lock` currently resolves it to `3.3.1`, which has been smoke-tested with this runner.

If model downloads or model source checks complain, set:

```bash
export HF_HUB_DISABLE_XET=1
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
```

If you already have the PaddleOCR repo environment working, you can also use it directly. That is only a shortcut for reusing an existing heavy Paddle/MLX install:

```bash
cd /Users/yuehu/projects/pdf-extract

/Users/yuehu/opensources/PaddleOCR/.venv/bin/python scripts/run_pdf_vl.py \
  /path/to/input.pdf \
  --out runs/input_vl \
  --pages 1 \
  --resume \
  --retries 1 \
  --server-url http://localhost:8111/
```

## Start The MLX Server

Recommended: use the already-working PaddleOCR environment for the MLX server. Run this in a separate terminal and keep it running while the extractor runs:

```bash
cd /Users/yuehu/opensources/PaddleOCR
source .venv/bin/activate
mlx_vlm.server --port 8111
```

Or without activating:

```bash
/Users/yuehu/opensources/PaddleOCR/.venv/bin/mlx_vlm.server --port 8111
```

The server is separate from this runner. It does not need to run from this repo as long as it is listening on `http://localhost:8111/`.

If you want a fully self-contained environment in this repo, sync the `mlx` extra first:

```bash
cd /Users/yuehu/projects/pdf-extract
uv sync --extra dev --extra paddle --extra mlx
uv run --extra paddle --extra mlx mlx_vlm.server --port 8111
```

## Run It

From this repo:

```bash
uv run --extra paddle run-pdf-vl /path/to/input.pdf \
  --out runs/input_vl \
  --resume \
  --retries 1 \
  --vl-rec-max-concurrency 1 \
  --server-url http://localhost:8111/
```

That command runs through the whole PDF. To limit a run to specific pages, add `--pages`.
The runner defaults `--vl-rec-max-concurrency` to `1` for the MLX server path because concurrent block-level VLM requests can trigger server-side generation shape errors.

You can also call the script directly through `uv`:

```bash
uv run --extra paddle python scripts/run_pdf_vl.py /path/to/input.pdf \
  --out runs/input_vl \
  --resume \
  --retries 1 \
  --vl-rec-max-concurrency 1 \
  --server-url http://localhost:8111/
```

The earlier direct Python path is useful only when you intentionally want to run inside `/Users/yuehu/opensources/PaddleOCR/.venv`.

Page selections can be a single page, a range, or a comma-separated mix:

```bash
--pages 1
--pages 1-5
--pages 1,3,7-9
```

If `--out` is omitted, the default output directory is:

```text
runs/<pdf_stem>_vl
```

If `--run-mode union` or `--run-mode small` is provided and `--out` is omitted,
the output directory is:

```text
runs/<pdf_stem>/<run_mode>
```

For a document-layout union run:

```bash
uv run --extra paddle run-pdf-vl /path/to/input.pdf \
  --run-mode union \
  --resume \
  --retries 1 \
  --vl-rec-max-concurrency 1 \
  --server-url http://localhost:8111/
```

For the matching small-mode run:

```bash
uv run --extra paddle run-pdf-vl /path/to/input.pdf \
  --run-mode small \
  --resume \
  --retries 1 \
  --vl-rec-max-concurrency 1 \
  --server-url http://localhost:8111/
```

Do not run the union and small modes at the same time against the same MLX
server unless you have verified the server can handle the load.

## Smoke Test Order

Start small before running a large PDF:

```bash
uv run --extra paddle run-pdf-vl /path/to/input.pdf \
  --out runs/smoke_page1 \
  --pages 1 \
  --resume \
  --vl-rec-max-concurrency 1 \
  --retries 0

uv run --extra paddle run-pdf-vl /path/to/input.pdf \
  --out runs/smoke_pages_1_3 \
  --pages 1-3 \
  --resume \
  --vl-rec-max-concurrency 1 \
  --retries 1

uv run --extra paddle run-pdf-vl /path/to/input.pdf \
  --out runs/full \
  --retries 1
```

After each smoke run, check:

```bash
find runs/smoke_page1 -maxdepth 3 -type f | sort
cat runs/smoke_page1/failed_pages.txt
cat runs/smoke_page1/pages/page_0001/output.md
```

You should see `page.png`, `layout_det_res.png`, `res.json`, `output.docx`, and `output.md` under the page directory.

## Resume And Rerun

Resume is enabled by default. Re-running the same command skips pages that have:

- a latest `manifest.jsonl` entry with `status="ok"`;
- non-empty `layout_det_res.png`;
- non-empty `res.json`;
- non-empty `output.docx`;
- non-empty `output.md`;
- non-empty `page.png`, unless `--no-save-page-image` was used.

Useful flags:

- `--resume`: skip complete pages. This is the default.
- `--no-resume`: process selected pages again.
- `--force`: rerun selected pages even if they already look complete.
- `--retries 1`: retry a failed page once before moving on.
- `--fail-fast`: stop after the first unrecovered page failure.
- `--no-save-page-image`: do not keep `page.png`.

There is no `--isolate-pages` mode in this version. `--timeout-sec` is recorded in `config.json`, but same-process PaddleOCR calls are not hard-killed.

## Diagnostic Layout Mode

The default layout behavior is the safest general-purpose path. You can try PaddleOCR's smaller layout merge mode for diagnostics:

```bash
uv run --extra paddle run-pdf-vl /path/to/input.pdf \
  --out runs/diagnostic_small_layout \
  --pages 1 \
  --layout-merge-bboxes-mode small \
  --resume
```

Do not use this as the default for full-document extraction unless you have checked the page output. It can improve a contained table while dropping nearby narrative text.

## Development Checks

Run tests:

```bash
uv run --with pytest python -m pytest -v
```

Show CLI help:

```bash
uv run run-pdf-vl --help
```
