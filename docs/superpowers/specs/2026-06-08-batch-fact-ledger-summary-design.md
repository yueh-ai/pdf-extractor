# Batch Fact Ledger Summary Design

## Purpose

Generate a current wellbore data summary like
`runs/Full_30015375000000/pre134/combined_summary_current.md` from reconciled
PDF page Markdown.

The v1 target is only wellbore-diagram/current well data:

- Well identity.
- Elevations.
- Operation timeline.
- Hole sections.
- Casing and tubing strings.
- Downhole items and reference depths.
- Cement jobs.
- Plugs.
- Perforations and treatments.
- Directional and lateral details.
- Formation tops.
- Consolidated conflicts and uncertain data.

The system should work for many PDFs without manually selecting relevant pages.
It scans the reconciled Markdown in batches, records candidate facts in a fact
ledger, then reduces the ledger into one human-facing summary.

## Current Context

The repository already has:

- Dual PaddleOCR outputs under `runs/<document_id>/union/` and
  `runs/<document_id>/small/`.
- Page-level reconciliation outputs under local object-store layouts such as
  `object_store_eval_20_html_tables_strict/pdf-extract/reconciled/<document_id>/`.
- Page-level `output.md`, `decision.json`, and `assets.json` artifacts.
- A hand-built target summary under
  `runs/Full_30015375000000/pre134/combined_summary_current.md`.
- A fuller proposed/actual/conflict source summary under
  `runs/Full_30015375000000/pre134/combined_summary.md`.

The existing page reconciler stops at page Markdown. This design adds the next
layer: document-level wellbore fact extraction and current-value reduction.

## Design Decision

Use a batch fact ledger.

The pipeline is:

```text
reconciled page Markdown
-> 10-page overlapping batch fact scout
-> fact_ledger.jsonl
-> current-value reducer
-> combined_summary_current.md
```

V1 does not use retrieval repair, LlamaIndex, Haystack, or page-image
verification. Those remain future extensions. V1 also does not write separate
section reports or a machine-readable reduction report.

## Inputs

The input is the existing reconciled page store:

```text
object_store.../pages/page_XXXX/output.md
object_store.../pages/page_XXXX/decision.json
```

The fact scout uses reconciled Markdown only. It does not send `page.png` to the
model in v1.

`decision.json.needs_human_review` may be carried as page metadata for warnings
or future verification, but it does not change v1 prompt inputs.

## Batching

Process all reconciled pages in overlapping batches:

```text
batch_size = 10
overlap = 1
examples: 1-10, 10-19, 19-28, 28-37
```

Each page in the prompt must be labeled with a system-provided `source_id`. The
one-page overlap lets facts that cross a boundary appear in at least one
complete local context. Duplicate facts from overlap are expected and removed
during dedupe.

## Page Grounding

Source page handling is critical because batches contain multiple pages and the
overlap repeats one page in adjacent batches. The model must never infer source
pages from page order inside the batch, and it must not use page numbers printed
inside the PDF or form as citations.

Every batch prompt should include a page manifest before the page Markdown:

```text
Source manifest:
- source_id: page_0028
- source_id: page_0029
- source_id: page_0030
```

Then each page should use a repeated boundary format:

```text
===== BEGIN SOURCE page_0028 =====
<reconciled Markdown for PDF page 28>
===== END SOURCE page_0028 =====
```

The scout output must cite `source_page_ids`, not numeric page numbers:

```json
"source_page_ids": ["page_0028"]
```

`source_page_ids` must contain only `source_id` values from the manifest. Code
maps those stable source IDs to display page numbers when rendering
`combined_summary_current.md`.

The structured-output schema should generate the allowed `source_page_ids` enum
per batch:

```json
{
  "source_page_ids": {
    "type": "array",
    "items": {
      "type": "string",
      "enum": ["page_0028", "page_0029", "page_0030"]
    },
    "minItems": 1
  }
}
```

If one fact is supported by multiple pages in the same batch, cite all of them:

```json
"source_page_ids": ["page_0028", "page_0030"]
```

If a fact appears on the overlap page and is extracted in two adjacent batches,
dedupe should merge the duplicate facts by normalized value and source ID. The
same `source_id` must remain stable across batches.

## Fact Scout Output

Each batch returns structured candidate facts. The scout does not decide the
final current summary. It only records facts that may help fill the target
wellbore sections.

Fact shape:

```json
{
  "section": "casing_and_tubing_strings",
  "field": "production_casing",
  "value": "5-1/2\" 17# L-80 LT&C 8rd casing set at 10,490'",
  "source_page_ids": ["page_0028"],
  "source_context": "C-105 completion report casing table",
  "source_snippet": "5-1/2 ... 17# ... L-80 ... 10,490",
  "status_hint": "actual",
  "confidence": "high",
  "notes": "Completion table supports the actual production casing setting depth."
}
```

Required fields:

```text
section
field
value
source_page_ids
source_context
source_snippet
status_hint
confidence
notes
```

Allowed `section` values:

```text
well_identity
elevations
operation_timeline
hole_sections
casing_and_tubing_strings
downhole_items_and_reference_depths
cement_jobs
plugs
perforations_and_treatments
directional_and_lateral_details
formation_tops
```

Allowed `status_hint` values:

```text
actual
proposed
historical
uncertain
unknown
```

Allowed `confidence` values:

```text
high
medium
low
```

`source_snippet` is required. It should be a short source phrase or compact
paraphrase, not a long copied passage. Its job is to show what the data looked
like so dedupe and reduction can decide what to merge, discard, or retain.

`source_context` should identify the form, table, narrative, or page region
when clear. If the exact form is not clear, it should use a useful generic
description instead of inventing one.

## Common Source Contexts

The fact-scout prompt should include likely source contexts:

- APD / C-101 permit or application: often proposed well plan, proposed casing,
  proposed cement, proposed TD, proposed location.
- C-102 plat: location, SHL/BHL, section-township-range, county, coordinates,
  lease/well name.
- C-103 subsequent report / sundry notice: actual operations, casing set,
  cement jobs, plugs, drilling progress, TD, rig release, changes.
- C-104 request for allowable / authorization to transport: completion status,
  producing interval, first production, operator/well identity.
- C-105 well completion report: final TD/PBTD, casing/tubing, cement,
  formations, perforations, dates, elevations.
- C-105 continuation / attachment: perforation lists, treatment stages,
  casing/cement details.
- Directional plan: proposed KOP, planned MD/TVD, planned lateral, planned
  azimuth, target details.
- Directional survey / final survey: actual survey stations, MD/TVD,
  inclination, azimuth, closure, BHL, lateral direction.
- Formation tops table: formation names and top depths.
- Operator change / C-145 / transfer material: later/current operator, OGRID,
  effective dates.
- C-129 or production/transport forms: operator identity, API, well status,
  production/admin data.
- Wellbore diagram / schematic: visual summary of casing, cement, plugs,
  perforations, TD/PBTD, formation tops.
- Daily completion/workover narrative: tubing, packer, acid/frac/perforation
  stages, plugs, DV tool, cleanup.
- Unknown form/table/header: use when the source type is not clear.

These labels are guidance, not a closed set. The scout must not invent a form
name when the provided Markdown does not make it clear.

## Fact Ledger

Write all batch outputs to:

```text
fact_ledger.jsonl
```

Each JSONL row represents one batch result:

```json
{
  "document_id": "Full_30015375000000",
  "batch_id": "pages_0028_0037",
  "batch_pages": [28, 29, 30, 31, 32, 33, 34, 35, 36, 37],
  "model": "gpt-5.4-mini",
  "prompt_version": "wellbore-fact-scout-v1",
  "facts": [],
  "warnings": []
}
```

The ledger is the audit/debug artifact for v1. It should be enough to inspect
why the final summary selected, merged, or preserved facts.

## Dedupe And Normalization

After all batches finish, normalize facts for comparison:

- Dates: compare common variants such as `9/20/10` and `2010-09-20`.
- Depths: compare variants such as `10490'`, `10,490 ft`, and `10490 ft`.
- API numbers: compare dashed and undashed variants.
- Sizes: compare variants such as `5.5"` and `5-1/2"`.
- Source IDs: sort and deduplicate `source_page_ids`, then map them to display
  page numbers during rendering.

Group likely duplicates by:

```text
section + field + normalized value + compatible source context/status meaning
```

Do not merge facts that look similar but differ in datum, context, status, or
meaning. For example, `3191'KB`, `3190.50 RKB`, and `18 ft KB-to-ground` remain
separate elevation facts.

## Reducer

The reducer takes the fact ledger and writes only:

```text
combined_summary_current.md
```

It should produce a human-facing Markdown report shaped like the current-values
summary:

```text
### Well Identity
| Field | Value | Source PDF Page | Notes |

### Elevations
...
```

Reducer rules:

- Prefer `actual` facts over `proposed` facts.
- Use proposed facts only when no actual/current evidence exists, and label them
  clearly as proposed.
- Completion reports and actual operation reports generally beat APD/proposed
  plan values.
- Later/current operator-change facts can supersede earlier operator facts,
  while the earlier operator can remain as historical/conflict context.
- Repeated duplicate values collapse into one row with combined source pages.
- Same-looking values stay separate when datum, context, status, or meaning
  differs.
- Survey report "Date Completed" values must not become well completion dates
  unless the fact specifically says it is the well completion/ready-to-produce
  date.
- If facts conflict and no clear current value can be selected, keep the
  conflict in `Consolidated Conflicts And Uncertain Data`.
- Every selected value must cite source PDF page or pages.
- Notes should explain why the value was selected, merged, or kept separate.
- Do not mention batches, prompts, fact IDs, or model behavior in the final
  Markdown.

## Fact Scout Prompt

Draft prompt:

```text
You are extracting wellbore-diagram/current-data candidate facts from
reconciled PDF Markdown.

You receive a batch of PDF page sources. Each source has a system-provided
source_id such as `page_0028`. Use source IDs for citations. Use only the
provided Markdown. Do not use outside knowledge. Do not guess.

Important source citation rule:
- Every fact must cite source_page_ids from the provided source manifest.
- Use source_id values exactly, such as page_0028.
- Do not cite the page's position inside this batch.
- Do not cite page numbers printed inside the PDF/form/Markdown.
- Do not invent source IDs.
- If one fact is supported by multiple sources in this batch, include all
  supporting source IDs.

Your job is not to write the final summary. Your job is to collect candidate
facts that may help fill a current wellbore data summary.

Target sections:
- well_identity
- elevations
- operation_timeline
- hole_sections
- casing_and_tubing_strings
- downhole_items_and_reference_depths
- cement_jobs
- plugs
- perforations_and_treatments
- directional_and_lateral_details
- formation_tops

Extract facts about:
- well name, API, operator, location, county/state, coordinates, spud/completion
  dates
- GL/GR/KB/RKB/elevation datum values
- drilling/completion timeline events
- hole sizes and intervals
- casing/tubing strings, weights, grades, connections, setting depths
- TD, PBTD, KOP, TOC, DV tool, float collar, casing shoes, packers, plugs
- cement jobs, volumes, classes/blends, top/bottom depths, returns/circulation
- perforation depths, treatment intervals, acid/frac/squeeze/cement treatments
- directional/lateral MD/TVD ranges, azimuth/direction, pilot-hole details
- formation tops

Common source contexts you may see:
- APD / C-101 permit or application: often proposed well plan, proposed casing,
  proposed cement, proposed TD, proposed location.
- C-102 plat: location, SHL/BHL, section-township-range, county, coordinates,
  lease/well name.
- C-103 subsequent report / sundry notice: actual operations, casing set,
  cement jobs, plugs, drilling progress, TD, rig release, changes.
- C-104 request for allowable / authorization to transport: completion status,
  producing interval, first production, operator/well identity.
- C-105 well completion report: final TD/PBTD, casing/tubing, cement,
  formations, perforations, dates, elevations.
- C-105 continuation / attachment: perforation lists, treatment stages,
  casing/cement details.
- Directional plan: proposed KOP, planned MD/TVD, planned lateral, planned
  azimuth, target details.
- Directional survey / final survey: actual survey stations, MD/TVD,
  inclination, azimuth, closure, BHL, lateral direction.
- Formation tops table: formation names and top depths.
- Operator change / C-145 / transfer material: later/current operator, OGRID,
  effective dates.
- C-129 or production/transport forms: operator identity, API, well status,
  production/admin data.
- Wellbore diagram / schematic: visual summary of casing, cement, plugs,
  perforations, TD/PBTD, formation tops.
- Daily completion/workover narrative: tubing, packer, acid/frac/perforation
  stages, plugs, DV tool, cleanup.
- Unknown form/table/header: use this when the source type is not clear.

Use these labels inside source_context when they fit. Do not invent a form name
when the provided pages do not make it clear.

For each fact, return:
- section
- field
- value
- source_page_ids
- source_context
- source_snippet
- status_hint
- confidence
- notes

Rules:
- source_page_ids must contain one or more source_id values from the source
  manifest.
- source_snippet is required. Keep it short: enough to recognize the source
  evidence, not a long copy.
- source_context should describe the form/table/narrative context when clear. If
  unclear, use a generic context such as operation narrative, completion table,
  directional survey table, formation tops table, proposed plan, or unknown
  form.
- status_hint must be one of: actual, proposed, historical, uncertain, unknown.
- confidence must be one of: high, medium, low.
- Mark APD, permit plans, drilling plans, directional plans, revised plans, and
  contingency designs as proposed unless the page clearly reports actual
  execution.
- Mark completion reports, subsequent reports, actual operation narratives,
  final survey/control records, and operator-change/current operator records as
  actual when they report executed/current facts.
- Mark superseded real values as historical when the batch itself makes that
  clear.
- Use uncertain when the value is ambiguous, malformed, contradicted, or
  low-confidence.
- Preserve proposed values as facts; the later reducer will decide whether they
  belong in the current summary.
- Do not deduplicate aggressively inside the batch. If two facts differ in
  value, context, status, datum, or source ID, keep both.
- Do not invent missing values.
- If a source contains no relevant wellbore facts, return no facts for that
  source.
```

## Reducer Prompt

Draft prompt:

```text
You are creating a current wellbore data summary from extracted candidate facts.

Use only the provided fact ledger. Do not use outside knowledge. Do not guess.

Write a Markdown report shaped like:

### Well Identity
| Field | Value | Source PDF Page | Notes |

### Elevations
...

Use these sections:
- Well Identity
- Elevations
- Operation Timeline
- Hole Sections
- Casing And Tubing Strings
- Downhole Items And Reference Depths
- Cement Jobs
- Plugs
- Perforations And Treatments
- Directional And Lateral Details
- Formation Tops
- Consolidated Conflicts And Uncertain Data

Current-value rules:
- Prefer actual facts over proposed facts.
- Use proposed facts only when no actual/current fact exists, and clearly label
  them as proposed.
- Preserve important proposed-vs-actual differences in conflicts/uncertain data
  when they explain why a value was not selected.
- Collapse repeated duplicate values into one row with combined source pages.
- Keep same-looking values separate when they have different datum, context,
  status, or meaning.
- Later/current operator-change facts can supersede earlier operator facts.
- Completion reports and actual operation reports generally beat APD/proposed
  plan values.
- Survey report "Date Completed" values should not become well completion dates
  unless the fact specifically says it is the well completion/ready-to-produce
  date.
- If facts conflict and no clear current value can be selected, keep the
  conflict in Consolidated Conflicts And Uncertain Data.
- Every selected value must cite source PDF page(s).
- Notes should explain why the value was selected, merged, or kept separate.
- Do not include raw fact IDs.
- Do not mention implementation details, batches, prompts, or model behavior.
```

## Validation And Errors

Keep v1 simple:

- Validate fact-scout responses against the strict schema.
- Reject facts whose `source_page_ids` are not in the batch source manifest.
- Reject facts that cite page positions, numeric pages, or printed PDF/form page
  numbers instead of source IDs when that can be detected.
- Reject facts whose `section`, `status_hint`, or `confidence` are outside the
  allowed values.
- Require non-empty `source_snippet`.
- If a batch fails validation, report the failed batch in CLI output and do not
  include its facts in the ledger.
- If a section has no usable facts, omit that section from
  `combined_summary_current.md`.

No batch resume behavior is required in v1.

## Testing Strategy

Use deterministic fake model responses for unit and integration tests.

Test batch construction:

- 10-page batches with 1-page overlap.
- Short final batch handling.
- Selected page ranges if the CLI supports page selection.

Test schema validation:

- Accept valid fact-scout output.
- Reject invalid section, status, confidence, or source ID.
- Reject facts citing sources outside the batch manifest.
- Reject facts citing numeric pages instead of `source_page_ids`.
- Reject empty `source_snippet`.

Test dedupe:

- Merge duplicates from overlapping batches.
- Do not merge proposed and actual facts when they describe different source
  meanings.
- Keep different elevation datums separate.

Test reducer behavior:

- Actual casing facts beat proposed casing facts.
- Repeated ground/GR elevation values collapse with combined source pages.
- KB/RKB datum variants remain separate.
- Later operator facts can supersede earlier operator facts.
- Survey "Date Completed" does not override well completion date.
- Unresolved conflicts appear in consolidated conflicts.

Test end to end:

- Feed fake batch outputs from representative pages.
- Produce `combined_summary_current.md` with expected sections, page citations,
  and notes.

## Non-Goals

- No page-image input to the fact scout.
- No retrieval repair.
- No LlamaIndex or Haystack integration.
- No embeddings or BM25 index.
- No separate section report files.
- No reduction report JSON.
- No full proposed-and-actual summary; v1 renders the current-values summary.
