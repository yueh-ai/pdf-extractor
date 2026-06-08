from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from pdf_extract.reconciler import (
    DEFAULT_RECONCILE_MODEL,
    ModelCallResult,
    OpenAIResponsesVisionClient,
    run_reconciliation,
)


class DryRunVisionClient:
    model = "dry-run-no-llm"

    def reconcile(self, *, image_path: Path, prompt: str) -> ModelCallResult:
        return ModelCallResult(
            payload={
                "reconciled_markdown": "<!-- dry-run reconciliation did not call a vision model -->\n",
                "winner": "uncertain",
                "warnings": ["dry-run client did not call a vision model"],
                "needs_human_review": True,
            },
            call_metadata={
                "response_id": "dry-run",
                "input_tokens": None,
                "cached_input_tokens": None,
                "output_tokens": None,
                "reasoning_tokens": None,
                "total_tokens": None,
                "input_text_tokens_derived": None,
                "input_image_tokens_derived": None,
                "input_split_method": "unavailable",
                "image_count": 1,
                "image_detail": "high",
                "estimated_cost_usd": 0.0,
            },
        )


def load_openai_api_key_from_repo_env(repo_root: Path) -> bool:
    if os.environ.get("OPENAI_API_KEY"):
        return False

    env_path = repo_root / ".env"
    if not env_path.is_file():
        return False

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "OPENAI_API_KEY":
            continue
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if value:
            os.environ["OPENAI_API_KEY"] = value
            return True
    return False


def create_client(*, provider: str, model: str | None, sdk_client: Any | None = None):
    if provider == "dry-run":
        return DryRunVisionClient()
    if provider == "openai":
        return OpenAIResponsesVisionClient(
            model=model or os.environ.get("OPENAI_RECONCILE_MODEL", DEFAULT_RECONCILE_MODEL),
            sdk_client=sdk_client,
        )
    raise ValueError(f"Unsupported provider: {provider}")


def parse_pages_arg(value: str | None) -> list[int] | None:
    if value is None or value.strip() == "":
        return None
    pages: list[int] = []
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part.isdigit() or int(part) < 1:
            raise ValueError(f"Invalid page number: {part!r}")
        pages.append(int(part))
    return sorted(set(pages))


def create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run page-level OCR reconciliation and publish artifacts."
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path("runs/Full_30015375000000"),
        help="Document run root containing union/ and small/ directories.",
    )
    parser.add_argument(
        "--object-store-root",
        type=Path,
        default=Path("object_store"),
        help="Local fake-S3 root.",
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=Path("reconciled_catalog.sqlite"),
        help="SQLite catalog path.",
    )
    parser.add_argument(
        "--viewer-dir",
        type=Path,
        default=None,
        help="Optional directory for viewer-manifest.json.",
    )
    parser.add_argument(
        "--pages",
        default=None,
        help="Comma-separated page numbers. Omit to reconcile all discovered pages.",
    )
    parser.add_argument(
        "--provider",
        choices=("openai", "dry-run"),
        default="openai",
        help="Model provider. Use dry-run for local pipeline tests.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENAI_RECONCILE_MODEL", DEFAULT_RECONCILE_MODEL),
        help="Vision-capable model name for --provider openai.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rerun selected pages even if already published.",
    )
    parser.add_argument(
        "--no-assemble",
        action="store_true",
        help="Skip combined document assembly after page reconciliation.",
    )
    return parser


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    load_openai_api_key_from_repo_env(repo_root)

    parser = create_arg_parser()
    args = parser.parse_args()
    result = run_reconciliation(
        run_root=args.run_root,
        object_store_root=args.object_store_root,
        sqlite_path=args.sqlite_path,
        viewer_dir=args.viewer_dir,
        client=create_client(provider=args.provider, model=args.model),
        pages=parse_pages_arg(args.pages),
        force=args.force,
        assemble=not args.no_assemble,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
