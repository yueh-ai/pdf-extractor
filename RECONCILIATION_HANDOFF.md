# Handoff: Union/Small Reconciliation Pipeline

## Purpose

We want a second-stage reconciliation pipeline after PaddleOCR-VL extraction.
The goal is not to replace PaddleOCR. The goal is to use two PaddleOCR-VL
views of the same PDF page, plus the rendered source page image, to produce a
more faithful Markdown result than either OCR mode gives alone.

The immediate reason is that the default layout merge behavior is safer for
full-document extraction, but `layout_merge_bboxes_mode="small"` can sometimes
recover cleaner table structure. Small mode is not safe as the default because
we have already seen it drop nearby narrative text. Reconciliation should let us
use small-mode wins without losing union-mode coverage.

## What Exists Now

The main runner is `run-pdf-vl`.

Legacy default output still exists for simple runs:

```text
runs/<pdf_stem>_vl/
  config.json
  manifest.jsonl
  failed_pages.txt
  combined.md
  combined.jsonl
  pages/page_0001/
    page.png
    layout_det_res.png
    res.json
    output.docx
    output.md
    imgs/
```

The new document layout exists for dual-mode extraction:

```text
runs/<pdf_stem>/
  document.json
  union/
    config.json
    manifest.jsonl
    failed_pages.txt
    combined.md
    combined.jsonl
    pages/page_0001/...
  small/
    config.json
    manifest.jsonl
    failed_pages.txt
    combined.md
    combined.jsonl
    pages/page_0001/...
```

`--run-mode union` writes to `runs/<pdf_stem>/union` and uses PaddleOCR-VL's
default layout merge behavior.

`--run-mode small` writes to `runs/<pdf_stem>/small` and forces
`layout_merge_bboxes_mode="small"`.

There is also a local ignored helper in `tmp/migrate_input_vl_to_union.py` for
moving the current in-progress flat run into the new document layout after it
finishes. That helper is intentionally not a product path.

## What The Reconciler Should Consume

For each page, the useful evidence is:

- `union/pages/page_NNNN/page.png`
- `union/pages/page_NNNN/output.md`
- `union/pages/page_NNNN/layout_det_res.png`
- `union/pages/page_NNNN/imgs/`, when referenced by Markdown
- `small/pages/page_NNNN/output.md`
- `small/pages/page_NNNN/layout_det_res.png`
- `small/pages/page_NNNN/imgs/`, when referenced by Markdown

The rendered `page.png` is the highest-authority evidence because it is the
actual page image sent to PaddleOCR.

The `output.md` files are candidate extractions, not truth.

The layout visualization PNGs are useful for diagnosing whether a block was
merged, split, dropped, or misread.

Raw `res.json` should be kept as provenance, but it should not be sent to the
LLM by default. It is bulky and usually less helpful than the source image plus
candidate Markdown. If JSON becomes useful later, send a small derived summary
instead of the full file.

Do not send DOCX by default. It is useful as an export artifact, but it is not
the best evidence for multimodal reconciliation.

## Expected Reconciled Artifact Shape

The likely target shape is:

```text
runs/<pdf_stem>/
  reconciled/
    config.json
    manifest.jsonl
    failed_pages.txt
    unresolved_pages.txt
    combined.md
    combined.jsonl
    pages/page_0001/
      prompt.md
      response.json
      decision.json
      output.md
      imgs/
```

`output.md` should be the reconciled page Markdown.

`decision.json` should record provenance and summary-level decisions, such as:

- page number
- model used
- source union page path
- source small page path
- winner: `union`, `small`, `mixed`, or `uncertain`
- whether human review is recommended
- warnings
- copied image assets referenced by `output.md`

`response.json` should preserve the raw OpenAI response or the parsed structured
response for debugging and reproducibility.

`prompt.md` should preserve the exact page prompt used for that request.

## Reconciliation Granularity

Default to page-by-page reconciliation.

Reasons:

- It matches the existing extraction/checkpoint model.
- It keeps requests smaller.
- It makes resume/retry straightforward.
- It makes failures local to one page.
- It gives clean provenance for every reconciled page.

After page reconciliation, there may be a light document assembly pass. That
later pass should fix cross-page continuity only, such as repeated headers,
broken paragraphs, table continuations, and final `combined.md` polish. It
should not reinterpret every page from scratch.

## OpenAI API Assumptions To Recheck During Implementation

Use the OpenAI Responses API for multimodal page reconciliation.

Official docs currently describe image inputs for the Responses API and say
images may be supplied by URL, base64 data URL, or file ID. They also note that
multiple image inputs can be included in one request, and that image inputs
count as tokens. See:

- https://platform.openai.com/docs/guides/images-vision
- https://platform.openai.com/docs/api-reference/responses/input-items

Use Structured Outputs if the selected model supports it. Official docs describe
Structured Outputs as JSON Schema-constrained responses and recommend them over
plain JSON mode when available:

- https://platform.openai.com/docs/guides/structured-outputs

Do not hard-code a model decision in this handoff. At implementation time,
choose an OpenAI model that supports image input and structured outputs, then
confirm current availability, pricing, and context limits.

## Prompt Intent

The model should behave as a faithful document extraction reconciler.

Core instruction:

```text
You are a faithful document extraction reconciler.

You will receive evidence for one PDF page:
1. The rendered source page image.
2. A PaddleOCR extraction using default layout merge behavior.
3. A PaddleOCR extraction using layout_merge_bboxes_mode="small".
4. Layout visualization images from both runs.

Your task is to produce the best faithful Markdown for this page.

Rules:
- The source page image is the authority.
- Treat the two OCR outputs as candidates, not truth.
- Preserve all visible narrative text, headings, lists, tables, captions,
  footnotes, and figure references.
- If one candidate includes visible text that the other omitted, include it.
- If a candidate contains text not supported by the source image, omit it or
  mark the page uncertain.
- Do not invent missing content.
- Preserve reading order as it appears on the page.
- Keep Markdown clean and document-like.
- Return only the requested structured result.
```

The expected structured result should include at least:

```json
{
  "page": 1,
  "winner": "union",
  "reconciled_markdown": "...",
  "asset_refs": [],
  "changes": [
    {
      "kind": "added_from_small",
      "summary": "Recovered table cells missing from union output.",
      "confidence": 0.82
    }
  ],
  "warnings": [],
  "needs_human_review": false
}
```

The exact schema is still open for discussion.

## Open Questions

- Should reconciliation always include both layout visualization PNGs, or only
  include them when the two Markdown candidates differ meaningfully?
- Should page image input use base64 data URLs directly, or upload files and use
  file IDs for reuse?
- Should referenced `imgs/` assets be copied into reconciled pages only when the
  final Markdown references them, or should the reconciled page keep all assets
  from both source modes?
- What confidence/warning threshold should place a page in
  `unresolved_pages.txt`?
- Should the first implementation support only document-layout runs, or also
  support legacy flat run directories?
- Should the document assembly pass be part of the first reconciler version, or
  deferred until page-level reconciliation works?

## Not The Next Step Yet

This file is not an implementation plan. Before writing the reconciler code, we
should still discuss the artifact contract, the structured output schema, and
the exact retry/resume behavior.
