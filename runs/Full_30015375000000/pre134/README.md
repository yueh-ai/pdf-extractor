# Pre-134 Extraction Workspace

This folder contains bounded source artifacts for testing `instruction_engineer_readable.md`.

- `combined.md`: OCR/VL markdown copied only through PDF page 133.
- `combined.jsonl`: OCR/VL JSONL copied only through PDF page 133.
- `manifest.jsonl`: run manifest copied only through PDF page 133.
- `allowed_pages.txt`: page directory names permitted for image verification.
- `section_reports/`: one markdown report per extraction section.

Agents should search only these bounded artifacts for text/JSON. For image checks, use only
`../union/pages/page_0001` through `../union/pages/page_0133`.
