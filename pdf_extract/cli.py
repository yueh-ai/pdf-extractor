from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Sequence

from tqdm import tqdm

from .combine import write_combined_outputs
from .manifest import append_manifest_entry, is_page_complete, load_latest_manifest
from .page_ranges import parse_page_spec
from .paddle_output import atomic_write_text, save_page_result_bundle
from .render import get_pdf_page_count, page_dir_name, render_page_to_png
from .run_layout import VALID_RUN_MODES, mode_run_dir, write_document_metadata


DEFAULT_SERVER_URL = "http://localhost:8111/"
DEFAULT_MODEL_NAME = "PaddlePaddle/PaddleOCR-VL-1.6"
PipelineFactory = Callable[[argparse.Namespace], Any]


def create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run PaddleOCR-VL over a PDF one rendered page at a time."
    )
    parser.add_argument("input_pdf", help="Input PDF path")
    parser.add_argument("--out", type=Path, help="Output run directory")
    parser.add_argument(
        "--run-mode",
        choices=VALID_RUN_MODES,
        help="Use document layout runs/<pdf_stem>/<mode>; small also enables small layout merge mode",
    )
    parser.add_argument("--pages", help="Page selection such as 1, 1-5, or 1,3,7-9")

    resume_group = parser.add_mutually_exclusive_group()
    resume_group.add_argument(
        "--resume", dest="resume", action="store_true", help="Skip complete pages"
    )
    resume_group.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Do not skip complete pages",
    )
    parser.set_defaults(resume=True)

    parser.add_argument(
        "--force",
        action="store_true",
        help="Rerun selected pages even if complete output exists",
    )
    parser.add_argument("--retries", type=int, default=0, help="Retries after failure")
    parser.add_argument(
        "--fail-fast", action="store_true", help="Stop after first unrecovered failure"
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=900,
        help="Recorded for run config; same-process calls are not hard-killed",
    )
    parser.add_argument("--server-url", default=DEFAULT_SERVER_URL, help="MLX server URL")
    parser.add_argument(
        "--model-name", default=DEFAULT_MODEL_NAME, help="PaddleOCR-VL API model name"
    )
    parser.add_argument(
        "--vl-rec-max-concurrency",
        type=int,
        default=1,
        help="Maximum concurrent VLM requests sent to the MLX server",
    )
    parser.add_argument(
        "--layout-merge-bboxes-mode",
        help="Optional PaddleOCR diagnostic layout merge override",
    )
    parser.add_argument(
        "--no-save-page-image",
        action="store_true",
        help="Do not keep the rendered source page PNG after processing",
    )
    return parser


def create_default_pipeline(args: argparse.Namespace) -> Any:
    from paddleocr import PaddleOCRVL

    return PaddleOCRVL(
        pipeline_version="v1.6",
        device="cpu",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_layout_detection=True,
        vl_rec_backend="mlx-vlm-server",
        vl_rec_server_url=args.server_url,
        vl_rec_max_concurrency=args.vl_rec_max_concurrency,
        vl_rec_api_model_name=args.model_name,
        layout_merge_bboxes_mode=args.layout_merge_bboxes_mode,
    )


def _run_dir_for(args: argparse.Namespace, input_pdf: Path) -> Path:
    if args.out is not None:
        return args.out
    if args.run_mode is not None:
        return mode_run_dir(input_pdf, args.run_mode)
    return Path("runs") / f"{input_pdf.stem}_vl"


def _write_config(
    run_dir: Path,
    args: argparse.Namespace,
    *,
    input_pdf: Path,
    total_pages: int,
    selected_pages: list[int],
) -> None:
    config = {
        "input_pdf": str(input_pdf),
        "out": str(run_dir),
        "run_mode": args.run_mode,
        "pages": args.pages,
        "selected_pages": selected_pages,
        "total_pages": total_pages,
        "resume": args.resume,
        "force": args.force,
        "retries": args.retries,
        "fail_fast": args.fail_fast,
        "timeout_sec": args.timeout_sec,
        "server_url": args.server_url,
        "model_name": args.model_name,
        "vl_rec_max_concurrency": args.vl_rec_max_concurrency,
        "layout_merge_bboxes_mode": args.layout_merge_bboxes_mode,
        "save_page_image": not args.no_save_page_image,
    }
    atomic_write_text(run_dir / "config.json", json.dumps(config, indent=2) + "\n")


def _attempt_start(latest_entry: dict[str, Any] | None) -> int:
    if latest_entry is None:
        return 1
    attempt = latest_entry.get("attempt", 0)
    return int(attempt) + 1 if isinstance(attempt, int) else 1


def _relative(path: Path, run_dir: Path) -> str:
    return path.relative_to(run_dir).as_posix()


def _predict_one(pipeline: Any, image_path: Path, args: argparse.Namespace) -> Any:
    predict_kwargs: dict[str, Any] = {}
    if args.layout_merge_bboxes_mode is not None:
        predict_kwargs["layout_merge_bboxes_mode"] = args.layout_merge_bboxes_mode
    results = list(pipeline.predict(str(image_path), **predict_kwargs))
    if not results:
        raise RuntimeError("PaddleOCRVL returned no results")
    return results[0]


def _normalize_mode_args(args: argparse.Namespace) -> None:
    if args.run_mode == "small":
        if args.layout_merge_bboxes_mode not in (None, "small"):
            raise ValueError(
                "--run-mode small cannot be combined with "
                "--layout-merge-bboxes-mode values other than small"
            )
        args.layout_merge_bboxes_mode = "small"
    elif args.run_mode == "union" and args.layout_merge_bboxes_mode is not None:
        raise ValueError(
            "--run-mode union uses the default layout merge behavior; remove "
            "--layout-merge-bboxes-mode or use --run-mode small"
        )


def run(args: argparse.Namespace, *, pipeline_factory: PipelineFactory) -> int:
    _normalize_mode_args(args)
    input_pdf = Path(args.input_pdf).expanduser().resolve()
    if not input_pdf.is_file():
        raise FileNotFoundError(f"Input PDF does not exist: {input_pdf}")
    if args.retries < 0:
        raise ValueError("--retries must be >= 0")
    if args.vl_rec_max_concurrency < 1:
        raise ValueError("--vl-rec-max-concurrency must be >= 1")

    run_dir = _run_dir_for(args, input_pdf)
    run_dir.mkdir(parents=True, exist_ok=True)
    if args.run_mode is not None:
        write_document_metadata(run_dir.parent, input_pdf=input_pdf, mode=args.run_mode)
    total_pages = get_pdf_page_count(input_pdf)
    selected_pages = parse_page_spec(args.pages, total_pages=total_pages)
    _write_config(
        run_dir,
        args,
        input_pdf=input_pdf,
        total_pages=total_pages,
        selected_pages=selected_pages,
    )

    manifest_path = run_dir / "manifest.jsonl"
    latest_manifest = load_latest_manifest(manifest_path)
    require_page_image = not args.no_save_page_image
    ok_pages: set[int] = set()
    failed_pages: set[int] = set()
    pipeline = None

    progress = tqdm(selected_pages, unit="page", disable=not sys.stderr.isatty())
    for page in progress:
        progress.set_description(f"page {page}")
        if (
            args.resume
            and not args.force
            and is_page_complete(
                page, run_dir, latest_manifest, require_page_image=require_page_image
            )
        ):
            ok_pages.add(page)
            continue

        if pipeline is None:
            pipeline = pipeline_factory(args)

        page_dir = run_dir / "pages" / page_dir_name(page)
        page_dir.mkdir(parents=True, exist_ok=True)
        image_path = page_dir / ("page.png" if not args.no_save_page_image else ".page.png")
        first_attempt = _attempt_start(latest_manifest.get(page))
        max_attempt = first_attempt + args.retries

        for attempt in range(first_attempt, max_attempt + 1):
            started = time.monotonic()
            try:
                render_page_to_png(input_pdf, page_number=page, out_path=image_path)
                result = _predict_one(pipeline, image_path, args)
                save_page_result_bundle(result, page_dir)
                if args.no_save_page_image and image_path.exists():
                    image_path.unlink()

                elapsed = time.monotonic() - started
                entry = {
                    "page": page,
                    "status": "ok",
                    "attempt": attempt,
                    "elapsed_sec": round(elapsed, 3),
                    "image": _relative(page_dir / "page.png", run_dir)
                    if not args.no_save_page_image
                    else None,
                    "layout": _relative(page_dir / "layout_det_res.png", run_dir),
                    "json": _relative(page_dir / "res.json", run_dir),
                    "md": _relative(page_dir / "output.md", run_dir),
                    "docx": _relative(page_dir / "output.docx", run_dir),
                }
                append_manifest_entry(manifest_path, entry)
                latest_manifest[page] = entry
                ok_pages.add(page)
                failed_pages.discard(page)
                break
            except Exception as exc:
                elapsed = time.monotonic() - started
                entry = {
                    "page": page,
                    "status": "failed",
                    "attempt": attempt,
                    "elapsed_sec": round(elapsed, 3),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                    "traceback": traceback.format_exc(limit=6),
                }
                append_manifest_entry(manifest_path, entry)
                latest_manifest[page] = entry
                if attempt >= max_attempt:
                    failed_pages.add(page)
                    if args.fail_fast:
                        write_combined_outputs(
                            run_dir, ok_pages=ok_pages, failed_pages=failed_pages
                        )
                        return 1

    write_combined_outputs(run_dir, ok_pages=ok_pages, failed_pages=failed_pages)
    return 1 if failed_pages else 0


def main(
    argv: Sequence[str] | None = None,
    *,
    pipeline_factory: PipelineFactory = create_default_pipeline,
) -> int:
    parser = create_arg_parser()
    args = parser.parse_args(argv)
    try:
        return run(args, pipeline_factory=pipeline_factory)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
