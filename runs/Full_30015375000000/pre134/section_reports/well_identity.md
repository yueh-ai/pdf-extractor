# Well Identity

## Deduplicated Results

| Field | Value | Source PDF Page | Notes |
| --- | --- | --- | --- |
| Well name | Jericho BKJ State Com #2H | 4 | Page 4 source form states "Facility or well name: Jericho BKJ State Com #2H". Duplicate forms use capitalization and number variants including "JERICHO BKJ STATE COM #002H", "Jericho BKJ State Com" plus "2H", and "JERICHO BKJ STATE COM 2H". |
| Location description | Unit Letter A, Section 15, Township 25S, Range 27E, NMPM; 660 ft from the North line and 330 ft from the East line | 10 | Page 10 source form gives the clearest complete surface location wording. This matches the APD/plats on pages 1-2 and the page 4 location fields. |
| County and state | Eddy County, New Mexico | 4 | Rendered page image confirms County is "Eddy" on the C-144 form, under the State of New Mexico heading. Survey pages also state "EDDY COUNTY, NEW MEXICO". |
| Latitude and longitude | N 32.135547, W 104.170700 (NAD83) | 4 | Rendered page image confirms NAD 1983 is checked. The source labels this as the "Center of Proposed Design"; see coordinate uncertainty below. |
| API number | 30-015-37500 | 4 | Same API appears on APD, permit comment, sundry, and completion forms. Later C-129 forms omit dashes as "3001537500"; treated as the same API format. |
| Spud date | 2/1/2010 | 10 | Page 10 subsequent report states the well "Spudded 12-1/4\" hole at 4:00 PM" on 2/1/10. Page 1 also lists 2/1/2010 as the spud date. |
| Completion date | 9/20/2010 | 28 | Page 28 C-105 completion report field 16 states "Date Completed (Ready to Produce) 9/20/10". Survey "Date Completed" values were not treated as well completion dates. |
| Operator | EOG Resources Inc | 133 | Later source forms/conditions list EOG Resources Inc as operator. Earlier drilling and completion forms list Yates Petroleum Corporation; preserved as a conflict/sequence below. |

## Conflicts And Uncertain Data Contribution

| Field | Value A | Source PDF Page A | Value B | Source PDF Page B | Notes |
| --- | --- | --- | --- | --- | --- |
| Operator | Yates Petroleum Corporation | 4 | EOG Y Resources, Inc.; EOG Resources Inc | 98; 133 | Early APD, C-144, sundry, and C-105 completion forms list Yates. Later change-operator/C-129 material lists EOG variants, including explicit "Operator: EOG RESOURCES INC" on page 133. This appears to be an operator succession rather than a simple OCR conflict. |
| Latitude and longitude | N 32.135547, W 104.170700 (NAD83; center of proposed design) | 4 | LAT 32.8.7.9146 N, LON 104.10.14.5000 W (survey reference/wellhead) | 43 | The values are close but not identical, and the labels differ. Page 4 is an official source form coordinate for the design center; page 43 is a survey wellhead/reference coordinate. |
| Spud date | 2/1/2010 | 10 | Date Spudded field shows "RH 2/1/10" and "RT 6/18/10" | 28 | Page 10 is the clearest actual spud report. Page 28's completion-report field carries two sublabels/dates; 6/18/10 was not used as the spud date. |
| Completion date | 9/20/2010, Date Completed (Ready to Produce) | 28 | 06/21/2010 and 06/28/2010, "Date Completed" on survey reports | 43; 50 | The survey report dates are completion dates for survey deliverables/control reports, not the well's ready-to-produce completion date. They were treated as search false positives, not alternate well completion dates. |

## Deduplication Notes

Merged well-name variants by preserving the source's lease/name wording and normalizing the well number to `#2H`. The variants `#002H`, `#2H`, bare `2H`, and no-pound-sign forms all refer to the same API and location.

Merged API variants by preserving the dashed official form value `30-015-37500`; later undashed entries `3001537500` are the same ten-digit API without punctuation.

Merged repeated surface-location forms from pages 1, 2, 4, 10, and 28. Page 10 was selected because it states the feet-from-line description in plain text and includes Section/Township/Range/NMPM/Eddy County in the same source form.

Selected the actual spud report from page 10 over the APD's proposed spud field on page 1. Page 28's `RH`/`RT` sublabels were retained only as an uncertainty note.

Selected the C-105 `Date Completed (Ready to Produce)` value from page 28 for the completion date. PathFinder survey `Date Completed` fields on pages 43 and 50 were excluded because they describe survey/report completion, not well completion.

Selected the later EOG operator form for the deduplicated operator value while preserving the earlier Yates forms in the conflict table, because the later filings appear to document an operator transition.

## Heuristic Log

| Step | Tool | Input | Why | Result |
| --- | --- | --- | --- | --- |
| Load section schema | `exec_command` | `rg -n "Well Identity\|Deduplicated Results\|Source Rule\|API\|operator\|latitude\|longitude\|county\|state\|spud\|completion" /Users/yuehu/projects/pdf-extract/instruction_engineer_readable.md` | Locate the Well Identity schema and relevant source-rule language. | Found the Well Identity table and required columns. |
| Read guide context | `exec_command` | `sed -n '1,240p' /Users/yuehu/projects/pdf-extract/instruction_engineer_readable.md` | Confirm exact report columns and source rules. | Confirmed `Field \| Value \| Source PDF Page \| Notes` and conflict columns. |
| Confirm bounded page structure | `exec_command` | `sed -n '1,140p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Verify `pre134/combined.md` starts at page 1 and uses page headings. | Confirmed page-delimited markdown and early APD identity fields. |
| Spot-check allowed run metadata | `exec_command` | `sed -n '1,12p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/manifest.jsonl` | Confirm the pre134 manifest was the bounded run artifact. | Saw per-page run records for the pre134 extraction. |
| Spot-check allowed JSONL | `exec_command` | `sed -n '1,5p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.jsonl` | Inspect JSONL structure without leaving the allowed artifact set. | Confirmed the JSONL contains extracted page-block data for the same bounded source. |
| Broad identity search | `exec_command` | `rg -n -i "well:\|well name\|api\|spud\|completion date\|date completed\|completed\|operator name\|operator:\|latitude\|longitude\|county\|surface location\|location:" /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Find candidate identity fields across pages 1-133 only. | Found APD, C-144, sundry, completion, survey, and later EOG C-129 candidates. |
| Focus identity duplicates | `exec_command` | `rg -n -i "Jericho BKJ\|30-015-37500\|Yates Petroleum\|EOG Y Resources\|EOG Resources\|spudded\|Spud Date\|Latitude\|Longitude\|Unit Letter A\|Section 15 Township 25S Range 27E\|Eddy County" /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Collect duplicate well name, API, operator, coordinate, and location variants. | Found Yates-era forms, EOG-era forms, survey coordinates, and repeated location wording. |
| Map line hits to PDF pages | `exec_command` | `rg -n "^# Page " /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Convert line-number hits into PDF page citations. | Confirmed all cited candidates are within pages 1-133. |
| Read page 4 identity form | `exec_command` | `sed -n '126,190p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Inspect C-144 identity fields and coordinate text. | Found well name, API, operator, ULSTR, and coordinate line; county/NAD needed image verification. |
| Locate page 4 image | `exec_command` | `rg --files /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/union/pages/page_0004` | Find the allowed rendered page image for visual verification. | Found `page.png` under allowed `page_0004`. |
| Verify page 4 visually | `view_image` | `/Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/union/pages/page_0004/page.png` | Resolve markdown ambiguity for county and NAD checkbox. | Confirmed County `Eddy` and NAD `1983` checked. |
| Read page 10 spud/location report | `exec_command` | `sed -n '366,420p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Get the clearest actual spud report and surface location wording. | Found actual spud on 2/1/10 at 4:00 PM and full Unit A surface location. |
| Read page 1 APD | `exec_command` | `sed -n '1,48p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Cross-check APD API, operator, county, and proposed spud date. | Confirmed API `30-015-37500`, Yates operator, Eddy County, and spud date `2/1/2010`. |
| Search date labels | `exec_command` | `rg -n -i "Date Spudded\|Spudded\|18\\. Spud Date\|Date Completed \\(Ready to Produce\\)\|Date First Production" /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Separate actual spud/completion fields from other date labels. | Found page 10 spud report and page 28 C-105 completion fields. |
| Read completion report | `exec_command` | `sed -n '1224,1288p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Extract completion date and check page 28 identity duplicates. | Found C-105 `Date Completed (Ready to Produce) 9/20/10`, Yates operator, location, and spud sublabels. |
| Read survey completion false positives | `exec_command` | `sed -n '1588,1648p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Determine whether 06/21/2010 is a well completion date or report date. | Confirmed it belongs to a PathFinder survey/control report. |
| Read pilot-hole survey false positives | `exec_command` | `sed -n '1874,1938p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Determine whether 06/28/2010 is a well completion date or report date. | Confirmed it belongs to a PathFinder pilot-hole survey report. |
| Read operator-change context | `exec_command` | `sed -n '2703,2782p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Inspect later change-operator/EOG-related material. | Found page 98 `ChangeOp` comments with `EOG Y Resources, Inc.` and page 99 EOG applicant material. |
| Read page 99 C-129 | `exec_command` | `sed -n '2745,2790p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Confirm later EOG filing still references this well/API. | Found `JERICHO BKJ STATE COM 2H - 30-015-37500` under EOG Resources applicant. |
| Read later EOG forms | `exec_command` | `sed -n '3982,4058p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Inspect later C-129/conditions operator wording. | Found page 131 operator `EOG RESOURCES INC` and page 132 EOG C-129 application. |
| Read latest allowed page | `exec_command` | `sed -n '4090,4146p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Check the latest allowed page for final operator wording. | Found page 133 `Operator: EOG RESOURCES INC`, used as preferred later operator. |
