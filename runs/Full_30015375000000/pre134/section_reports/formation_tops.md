# Formation Tops

## Deduplicated Results

| Formation Name | Top Depth | Source PDF Page | Notes |
| --- | --- | --- | --- |
| Castille / Castile | MD/TVD 500.00 ft | 19 | Directional-plan table comment reads "Castille" on page 19; duplicate plot/table on page 20 reads "Castile". Conflicts with C-105 top on page 29. |
| TOS | MD/TVD 700.04 ft | 19 | Directional-plan abbreviation; likely top of salt based on nearby BOS and the C-105 Salt rows, but the source label is only "TOS". Duplicate on page 20. |
| BOS | MD/TVD 2100.00 ft | 19 | Directional-plan abbreviation; likely base of salt based on nearby TOS and the C-105 Salt rows, but the source label is only "BOS". Duplicate on page 20. |
| Bell Canyon | MD/TVD 2280.00 ft | 19 | Directional-plan table marker. Duplicate on page 20 plot/table. Conflicts with C-105 top on page 29. |
| Cherry Canyon | MD/TVD 3050.01 ft | 19 | Directional-plan table marker. Duplicate on page 20 plot/table. Conflicts with C-105 top on page 29. |
| Brushy Canyon | MD/TVD 4179.99 ft | 19 | Directional-plan table marker. Duplicate on page 20 plot/table; page 20 OCR lower plot misread this as "Brusley", but the page image supports Brushy. Conflicts with C-105 top on page 29. |
| Brushy Canyon Marker | MD/TVD 5530.00 ft | 19 | Directional-plan marker rather than a formal formation top. Duplicate on page 20 plot/table. |
| Bone Springs | MD 5802.76 ft; TVD 5800.04 ft | 19 | Directional-plan table comment reads "Bone Springs"; page 20 plot/table repeats TVD 5800.04 ft. Conflicts with C-105 top on page 29. |
| T. Salt | 734 ft | 29 | Formal C-105 "Indicate Formation Tops" table, Southeastern New Mexico section. Image verified. |
| B. Salt | 2117 ft | 29 | Formal C-105 "Indicate Formation Tops" table, Southeastern New Mexico section. Image verified. |
| T. Castile | 460 ft | 29 | Formal C-105 "Indicate Formation Tops" table, Southeastern New Mexico section. Image verified. |
| T. Bell Canyon | 2358 ft | 29 | Formal C-105 "Indicate Formation Tops" table, Southeastern New Mexico section. Image verified. |
| T. Cherry Canyon | 3174 ft | 29 | Formal C-105 "Indicate Formation Tops" table, Southeastern New Mexico section. Image verified. |
| T. Brushy Canyon | 4250 ft | 29 | Formal C-105 "Indicate Formation Tops" table, Southeastern New Mexico section. Image verified. |
| T. Bone Spring | 5828 ft | 29 | Formal C-105 "Indicate Formation Tops" table, Southeastern New Mexico section. Image verified. |

## Conflicts And Uncertain Data Contribution

| Field | Value A | Source PDF Page A | Value B | Source PDF Page B | Notes |
| --- | --- | --- | --- | --- | --- |
| Castile top | MD/TVD 500.00 ft; source spelling Castille/Castile | 19, 20 | 460 ft | 29 | Directional-plan marker conflicts with formal C-105 table. Page 19 spelling appears "Castille"; page 20 and page 29 use "Castile". |
| Salt top | MD/TVD 700.04 ft, labeled TOS | 19, 20 | 734 ft, labeled T. Salt | 29 | TOS expansion is inferred from abbreviation and nearby salt/base-salt context; keep source label as TOS. |
| Base Salt top | MD/TVD 2100.00 ft, labeled BOS | 19, 20 | 2117 ft, labeled B. Salt | 29 | BOS expansion is inferred from abbreviation and nearby salt/top-salt context; keep source label as BOS. |
| Bell Canyon top | MD/TVD 2280.00 ft | 19, 20 | 2358 ft | 29 | Directional-plan marker conflicts with formal C-105 table. |
| Cherry Canyon top | MD/TVD 3050.01 ft | 19, 20 | 3174 ft | 29 | Directional-plan marker conflicts with formal C-105 table. |
| Brushy Canyon top | MD/TVD 4179.99 ft | 19, 20 | 4250 ft | 29 | Directional-plan marker conflicts with formal C-105 table; page 20 OCR lower plot misread Brushy as "Brusley", corrected by page image/table. |
| Bone Spring top | MD 5802.76 ft; TVD 5800.04 ft, labeled Bone Springs | 19, 20 | 5828 ft, labeled T. Bone Spring | 29 | Directional-plan table gives separate MD/TVD; page 20 plot labels 5800.04 ft on the TVD chart. |
| Brushy Canyon Marker | MD/TVD 5530.00 ft | 19, 20 | n/a | n/a | Uncertain classification: this is a directional-plan marker, not a formal formation top. Retained because it appears in the same marker list as formation tops. |

## Deduplication Notes

Pages 19 and 20 contain the same directional-plan marker sequence. Page 19 has the cleaner table; page 20 repeats the values in an overlaid table and TVD plot. I kept one deduplicated row per marker from page 19 and noted page 20 as the duplicate/verification source.

Page 29 contains one formal C-105 "Indicate Formation Tops" table. I copied only the filled formation-depth pairs from the Southeastern New Mexico section and omitted blank regional template rows. No duplicate C-105 regional formation-tops table was found in pages 1-133.

I did not merge directional-plan markers into the C-105 rows because the values differ materially. Those differences are preserved in the conflict table.

## Heuristic Log

| Step | Tool | Input | Why | Result |
| --- | --- | --- | --- | --- |
| Read formation-top schema and source rules | `rg` | `rg -n -i "formation tops\|formation top\|formations?\|tops\|top depth" instruction_engineer_readable.md` | Locate the required columns and source-page rules. | Found the Formation Tops schema at lines 165-171 and the source rule near the top of the guide. |
| Inspect source-rule context | `sed` | `sed -n '1,60p' /Users/yuehu/projects/pdf-extract/instruction_engineer_readable.md` | Capture the guide's general source and image-authority rules. | Confirmed every item needs value, source PDF page, notes, and image verification when markdown is unclear. |
| Inspect formation schema | `sed` | `sed -n '160,174p' /Users/yuehu/projects/pdf-extract/instruction_engineer_readable.md` | Confirm exact Formation Tops table columns. | Confirmed columns: Formation Name, Top Depth, Source PDF Page, Notes. |
| Find formation-top header in bounded markdown | `rg` | `rg -n -i "formation tops\|formation top\|formation\|top depth\|tops" /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Search only the bounded pre134 combined markdown for obvious formation-top tables/lists. | Found the C-105 "INDICATE FORMATION TOPS" table at source page 29. |
| Inspect page 29 markdown | `sed` | `sed -n '1260,1301p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Read the full source-page table context around the page 29 hit. | Extracted filled C-105 tops: Salt, Base Salt, Castile, Bell Canyon, Cherry Canyon, Brushy Canyon, Bone Spring. |
| Check page 29 JSON table block | `jq` | `jq -r 'select(.input_path == "runs/input_vl/pages/page_0029/page.png") \| .parsing_res_list[] \| select(.block_label == "table") \| .block_content' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.jsonl` | Confirm table content from the bounded JSONL block extraction. | Confirmed the same filled C-105 table values as markdown. |
| Verify page 29 image | `view_image` | `/Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/union/pages/page_0029/page.png` with `detail: "original"` | The guide says rendered images are authoritative when markdown/OCR may be imperfect. | Confirmed the seven filled C-105 tops and that Northwestern New Mexico fields were blank. |
| Broaden bounded search for formation-marker names | `rg` | `rg -n -i "Castile\|Bell Canyon\|Cherry Canyon\|Brushy Canyon\|Bone Spring\|T\\. Salt\|B\\. Salt\|formation tops" /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Catch non-header formation lists and possible duplicates/conflicts. | Found a directional-plan marker list around source page 19 and many non-top pool-name hits; narrowed to the marker list. |
| Narrow directional-plan markers | `rg` | `rg -n -i "Castille\|\\bTOS\\b\|\\bBOS\\b\|Brushy Canyon Marker\|Bone Springs" /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Isolate the directional-plan markers without unrelated pool-name noise. | Confirmed the page 19 directional-plan marker sequence. |
| Inspect directional-plan context | `sed` | `sed -n '860,940p' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.md` | Read the source-page context before and after the directional-plan table. | Confirmed page 19 table rows for Castille, TOS, BOS, Bell Canyon, Cherry Canyon, Brushy Canyon, Brushy Canyon Marker, and Bone Springs. |
| Extract page 19 and 20 JSONL blocks | `jq` | `jq -r 'select(.input_path == "runs/input_vl/pages/page_0019/page.png" or .input_path == "runs/input_vl/pages/page_0020/page.png") \| "PAGE " + (.input_path\|capture("page_(?<p>[0-9]+)").p\|tonumber\|tostring) + "\n" + ([.parsing_res_list[].block_content] \| join("\n"))' /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/combined.jsonl` | Compare page 19 table and page 20 plot/table duplicates from bounded JSONL. | Page 20 duplicated the page 19 marker sequence but had OCR noise in some cells. |
| Verify page 19 image | `view_image` | `/Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/union/pages/page_0019/page.png` with `detail: "original"` | Resolve marker values and spellings in the directional-plan table. | Confirmed the page 19 table values and that Bone Springs row has MD 5802.76 ft and TVD 5800.04 ft. |
| Verify page 20 image | `view_image` | `/Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/union/pages/page_0020/page.png` with `detail: "original"` | Confirm whether page 20 is a duplicate and catch OCR errors. | Confirmed page 20 repeats the marker list/plot; treated it as duplicate verification rather than a separate result source. |
| Check OCR manifest for cited pages | `rg` | `rg -n "page_0019\|page_0020\|page_0029" /Users/yuehu/projects/pdf-extract/runs/Full_30015375000000/pre134/manifest.jsonl` | Verify cited pages were included in the bounded pre134 run. | Manifest shows pages 19, 20, and 29 have `status: "ok"`. |
