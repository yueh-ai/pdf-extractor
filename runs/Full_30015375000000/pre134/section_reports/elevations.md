# Elevations

## Deduplicated Results

| Field | Value | Source PDF Page | Notes |
| --- | --- | --- | --- |
| Ground level elevation | 3172 ft; also stated as `3172'GR`, `Ground Elevation: 3172.00`, `Altitude:3172.00' Ground To MSL`, and `ALTITUDE: 3172 Feet` | 1, 10-16, 21-23, 26, 28, 40, 43-45, 50, 53, 55-56 | Consolidated the recurring ground/GR datum. Page 1 labels it `Ground Level Elevation`; pages 10-16, 21-23, 26, 28, 55, and 56 use `GR`; pages 43, 44, and 50 state ground to MSL; pages 45 and 53 list altitude with the same value. |
| Ground level elevation | 3170' | 17 | C-103 elevation field reads `3170'` but does not show a GR/KB/RKB/RT suffix. Kept separate because it conflicts with the repeated 3172 ground/GR value. Visual verification confirmed the page image reads `3170'`. |
| Kelly bushing elevation | 3191'KB | 28 | Completion report field 17 states `3172'GR 3191'KB`. Kept as the completion-report KB datum. |
| Kelly bushing elevation | RKB / well reference: `WELL @ 3190.50ft (Original Well Elev)`; page 40 labels it `RKB Elevation: Well @ 3190.50... (Original Well Elev)` | 38-40 | Pages 38 and 39 use the same value as TVD/MD reference; page 40 repeats it in the well-details table as RKB elevation. Visual verification of page 40 supports the 3190.50 RKB reading. |
| Kelly bushing elevation | 18.00' Kelly Bushing To Ground; also `KELLY BUSHING ELEVATION: 18` | 43-45, 50, 53 | Relative KB height above ground, not an absolute MSL elevation. With 3172 ft ground/altitude, this implies about 3190 ft KB. |
| Other datum elevation | `Elevation: 3190.00 feet` | 46-47, 54 | PathFinder Magnetic & Grid Calculations coordinate elevation. Datum label is not explicit, but the value agrees with 3172 ft ground plus 18 ft Kelly bushing-to-ground reference. |

## Conflicts And Uncertain Data Contribution

| Field | Value A | Source PDF Page A | Value B | Source PDF Page B | Notes |
| --- | --- | --- | --- | --- | --- |
| Ground level / GR elevation | 3172 ft / `3172'GR` / `3172.00' Ground To MSL` | 1, 10-16, 21-23, 26, 28, 40, 43-45, 50, 53, 55-56 | 3170' | 17 | Page 17 lacks a datum suffix but is in the same C-103 elevation field. Treat as an unresolved conflict rather than a duplicate. |
| Kelly bushing / RKB absolute elevation | 3191'KB | 28 | `WELL @ 3190.50ft (Original Well Elev)` / RKB elevation 3190.50 | 38-40 | Completion report KB is 0.5 ft higher than the directional-plan RKB/original-well-elevation reference. |
| Kelly bushing / RKB absolute elevation | 3190.50 ft | 38-40 | 3190.00 ft, or 18.00' Kelly Bushing To Ground plus 3172.00' Ground To MSL | 43-47, 50, 53-54 | Survey/tie-in/magnetic-calculation sources imply or state 3190.00 ft, 0.5 ft lower than the 3190.50 ft RKB reference and 1 ft lower than the completion-report 3191'KB. |

## Deduplication Notes

Merged the repeated 3172 ground datum across APD, sundry, completion-report, survey, and location-form pages because the wording consistently ties the value to ground level, GR, or ground-to-MSL altitude.

Merged pages 43, 44, and 50 with pages 45 and 53 for the relative Kelly bushing height because they express the same datum relationship: 18 ft Kelly bushing to ground. I kept that separate from absolute KB/RKB elevations.

Merged pages 38, 39, and 40 for the 3190.50 ft original-well/RKB reference because the same value appears as TVD/MD reference and then as RKB elevation. Merged pages 46, 47, and 54 for the 3190.00 ft PathFinder coordinate elevation because they are repeated Magnetic & Grid Calculations pages.

Did not merge page 17's 3170' value into the 3172 ground/GR group, and did not collapse the 3191'KB, 3190.50 ft, and 3190.00 ft KB/RKB-related values, because the source values differ and the datum wording is not identical.

## Heuristic Log

| Step | Tool | Input | Why | Result |
| --- | --- | --- | --- | --- |
| 1 | `rg` | `rg -n "Elevations&#124;elevation&#124;datum&#124;ground&#124;KB&#124;Kelly&#124;GL&#124;DF" /Users/yuehu/projects/pdf-extract/instruction_engineer_readable.md` | Locate the section schema and source-rule wording in the guide. | Found the Elevations schema at lines 51-59 with columns `Field`, `Value`, `Source PDF Page`, `Notes`. |
| 2 | `sed` | `sed -n '45,62p' /Users/yuehu/projects/pdf-extract/instruction_engineer_readable.md` | Read the exact Elevations table columns and allowed field names. | Confirmed fields: Kelly bushing elevation, Ground level elevation, Other datum elevation. |
| 3 | `rg` | `rg -n -i "\b(KB&#124;K\.B\.&#124;kelly&#124;ground level&#124;ground elevation&#124;\bGL\b&#124;G\.L\.&#124;datum&#124;elevation&#124;derrick floor&#124;\bDF\b&#124;rotary&#124;RKB&#124;RT&#124;KB elevation)\b" /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Start with a broad bounded-source scan for elevation and datum language. | Found repeated `3172'GR` and ground-level hits, but also noisy short-abbreviation matches. |
| 4 | `head` | `head -n 3 /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.jsonl` | Inspect JSONL structure for page-scoped extraction. | Confirmed each line contains page JSON with `input_path` and `parsing_res_list`. |
| 5 | `jq` | `jq -r '(.input_path &#124; capture("page_(?<p>[0-9]{4})").p &#124; tonumber) as $pg &#124; .parsing_res_list[]? &#124; select((.block_content // "") &#124; test("(?i)(Ground Level Elevation&#124;Elevation \\(Show whether&#124;[0-9]{4}&#x27;GR&#124;[0-9]{4}'\''GR&#124;Kelly bushing&#124;KB elevation&#124;derrick floor&#124;rotary table&#124;\\bRKB\\b&#124;\\bRT\\b)")) &#124; "PAGE \($pg) BLOCK \(.block_id // "?") [\(.block_label // "?")]\n\(.block_content)\n---"' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.jsonl` | Pull page-scoped matching blocks from bounded JSONL. | Identified page 1 ground-level elevation, repeated C-103 `3172'GR`, page 17 `3170'`, page 28 `3172'GR 3191'KB`, pages 40/43-45/50/53 KB-related entries, and pages 55-56 `3172'GR`. |
| 6 | `rg` | `rg -n -i "Ground Level Elevation&#124;Elevation \(Show whether&#124;[0-9]{4}&#x27;GR&#124;[0-9]{4}'GR&#124;Kelly bushing&#124;KB elevation&#124;derrick floor&#124;rotary table&#124;\bRKB\b&#124;\bRT\b" /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Cross-check JSONL hits against the bounded markdown text. | Confirmed the core candidate pages and exposed some noisy `RT` matches, so later searches used more specific phrases. |
| 7 | `sed` | `sed -n '812,850p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Inspect the anomalous page 17 source text. | Page 17 C-103 table showed `11. Elevation ... 3170'`. |
| 8 | `sed` | `sed -n '1210,1275p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Inspect the completion-report elevation row. | Page 28 showed `17. Elevations (DF and RKB, RT, GR, etc.) 3172'GR 3191'KB`. |
| 9 | `rg` | `rg -n -i "^# Page&#124;Elevation:" /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Find generic `Elevation:` labels that the stricter datum scan might miss. | Found PathFinder Magnetic & Grid Calculation pages with `Elevation: 3190.00 feet` on pages 46, 47, and 54, plus unrelated blank/generic labels. |
| 10 | `sed` | `sed -n '1431,1457p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Inspect directional-survey reference pages for 3190.50 ft. | Pages 38 and 39 showed TVD/MD reference `WELL @ 3190.50ft (Original Well Elev)`. |
| 11 | `sed` | `sed -n '1458,1492p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Inspect page 40 well-details table. | Page 40 showed `Ground Elevation: 3172.00` and `RKB Elevation: Well @ 3190.50...`. |
| 12 | `sed` | `sed -n '1588,1682p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Inspect pages 43-45 for survey datum wording. | Found `18.00' Kelly Bushing To Ground`, `3172.00' Ground To MSL`, and `KELLY BUSHING ELEVATION: 18`. |
| 13 | `sed` | `sed -n '1695,1782p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Inspect pages 46-47 Magnetic & Grid Calculations. | Found `Elevation: 3190.00 feet` on repeated PathFinder calculation pages. |
| 14 | `sed` | `sed -n '1959,2020p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Inspect page 53 and page 54 follow-on datum values. | Page 53 repeated `KELLY BUSHING ELEVATION: 18` and `ALTITUDE: 3172 Feet`; page 54 repeated `Elevation: 3190.00 feet`. |
| 15 | `awk` | `awk '/^# Page /{p=$3} /Ground Level Elevation&#124;3172&#x27;GR&#124;3172'\''GR&#124;3191&#x27;KB&#124;3190\.50&#124;KELLY BUSHING ELEVATION&#124;Survey Vert\. Reference&#124;Altitude: ?3172&#124;Elevation: 3190/{print "Page " p ": " $0}' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Summarize page-numbered candidate lines from bounded markdown. | Produced the final candidate list used for deduplication and conflict grouping. |
| 16 | `view_image` | `/Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/union/pages/page_0017/page.png` | Verify the anomalous 3170' value visually inside the allowed page set. | Visual page confirmed the field reads `3170'` and lacks a datum suffix. |
| 17 | `view_image` | `/Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/union/pages/page_0028/page.png` | Verify the C-105 completion-report KB/GR pair. | Visual page confirmed `3172'GR 3191'KB`. |
| 18 | `view_image` | `/Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/union/pages/page_0040/page.png` | Verify the RKB/ground well-details table. | Visual page supported `Ground Elevation: 3172.00` and an RKB/original-well-elevation value of 3190.50. |
| 19 | `view_image` | `/Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/union/pages/page_0045/page.png` | Verify relative Kelly bushing height. | Visual page confirmed `KELLY BUSHING ELEVATION: 18` and `ALTITUDE: 3172 Feet`. |
