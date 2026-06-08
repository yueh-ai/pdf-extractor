from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from pdf_extract.wellbore_summary import (
    DEFAULT_FACT_SCOUT_MODEL,
    OpenAIResponsesTextClient,
    run_wellbore_summary,
)


class DryRunSummaryClient:
    model = "dry-run-no-llm"

    def create_json(
        self,
        *,
        prompt: str,
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "facts": [],
            "warnings": ["dry-run summary client did not call a model"],
        }

    def create_text(self, *, prompt: str) -> str:
        return "<!-- dry-run reducer did not call a model -->\n"


class WellboreSummaryArgumentParser(argparse.ArgumentParser):
    def parse_args(
        self,
        args: list[str] | None = None,
        namespace: argparse.Namespace | None = None,
    ) -> argparse.Namespace:
        parsed = super().parse_args(args=args, namespace=namespace)
        if parsed.out_dir is None:
            parsed.out_dir = Path("summary_runs") / parsed.document_id
        return parsed


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


def create_client(provider: str, model: str | None):
    if provider == "dry-run":
        return DryRunSummaryClient()
    if provider == "openai":
        return OpenAIResponsesTextClient(
            model=model
            or os.environ.get("OPENAI_SUMMARY_MODEL", DEFAULT_FACT_SCOUT_MODEL)
        )
    raise ValueError(f"Unsupported provider: {provider}")


def create_arg_parser() -> argparse.ArgumentParser:
    parser = WellboreSummaryArgumentParser(
        description=(
            "Generate a current wellbore data summary from reconciled page Markdown."
        )
    )
    parser.add_argument(
        "--document-id",
        required=True,
        help="Document ID under the reconciled object store.",
    )
    parser.add_argument(
        "--object-store-root",
        type=Path,
        default=Path("object_store"),
        help="Local object-store root containing pdf-extract/reconciled/<document-id>.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to summary_runs/<document-id>.",
    )
    parser.add_argument(
        "--provider",
        choices=("openai", "dry-run"),
        default="openai",
        help="Use dry-run to validate file flow without model calls.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENAI_SUMMARY_MODEL", DEFAULT_FACT_SCOUT_MODEL),
        help="OpenAI model for fact scouting and reduction.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Pages per fact-scout batch.",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=1,
        help="Pages repeated between adjacent batches.",
    )
    return parser


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    load_openai_api_key_from_repo_env(repo_root)

    parser = create_arg_parser()
    args = parser.parse_args()
    out_dir = args.out_dir or Path("summary_runs") / args.document_id
    result = run_wellbore_summary(
        object_store_root=args.object_store_root,
        document_id=args.document_id,
        out_dir=out_dir,
        client=create_client(provider=args.provider, model=args.model),
        batch_size=args.batch_size,
        overlap=args.overlap,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
