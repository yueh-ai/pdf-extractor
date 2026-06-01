# Engineer-Readable Wellbore Data Collection Guide

Use this guide to collect wellbore facts from the source PDF pages. The goal is to gather enough factual data
for someone else to draw the wellbore diagram.

Do not guess. Only report data found in the source pages. If a value is visible
but unclear, report it as `uncertain` and explain why. If a requested value
cannot be found, omit that field or row from the final output.

## Source Rule

Every collected item must include:

| Item | What To Write |
| --- | --- |
| Value | The extracted value, or `uncertain` when visible but unclear |
| Source PDF page | The PDF page number where the value was found |
| Notes | Any uncertainty, conflicting values, or original wording needed for context |

Use the rendered PDF page image as the authority for that source page. Extracted
Markdown can miss text that is visible in the image.

## Document Search Order

Review pages before the finished diagram and collect facts from:

| Source Type | What It Usually Contains | Source PDF Page | Notes |
| --- | --- | --- | --- |
| Permit, completion, or sundry forms | Well identity, operation dates, TD, casing, cement, plugs, tool depths | `<pdf_page>` | `<notes>` |
| Daily or narrative operation reports | Pilot hole, plugs, KOP, directional work, casing set, cement stages | `<pdf_page>` | `<notes>` |
| Casing and cement records | Hole size, casing size, grade, weight, setting depth, cement volume | `<pdf_page>` | `<notes>` |
| Directional survey | Build section, lateral direction, measured depth, TVD | `<pdf_page>` | `<notes>` |
| Perforation and stimulation records | Perforation depths, stage intervals, acid, frac, squeeze, cement treatments | `<pdf_page>` | `<notes>` |
| Formation tops table | Formation names and top depths | `<pdf_page>` | `<notes>` |

## Well Identity

Collect the well identification facts from source forms.

| Field | Value | Source PDF Page | Notes |
| --- | --- | --- | --- |
| Well name | `<well_name>` | `<pdf_page>` | `<notes>` |
| Location description | `<location_description>` | `<pdf_page>` | `<notes>` |
| County and state | `<county_state>` | `<pdf_page>` | `<notes>` |
| Latitude and longitude | `<latitude_longitude>` | `<pdf_page>` | `<notes>` |
| API number | `<api_number>` | `<pdf_page>` | `<notes>` |
| Spud date | `<spud_date>` | `<pdf_page>` | `<notes>` |
| Completion date | `<completion_date>` | `<pdf_page>` | `<notes>` |
| Operator | `<operator>` | `<pdf_page>` | `<notes>` |

## Elevations

Collect datum elevations when stated in the source pages.

| Field | Value | Source PDF Page | Notes |
| --- | --- | --- | --- |
| Kelly bushing elevation | `<kb_elevation>` | `<pdf_page>` | `<notes>` |
| Ground level elevation | `<gl_elevation>` | `<pdf_page>` | `<notes>` |
| Other datum elevation | `<other_datum_elevation>` | `<pdf_page>` | `<notes>` |

## Operation Timeline

Collect dated events that affect the final wellbore configuration.

| Date | Operation | Depth Or Interval | Details | Source PDF Page | Notes |
| --- | --- | --- | --- | --- | --- |
| `<date>` | `<operation>` | `<depth_or_interval>` | `<details>` | `<pdf_page>` | `<notes>` |

Examples of operations to capture: pilot hole TD, plug setting, tagged cement,
kickoff, directional drilling start, casing run, float collar depth, DV tool
use, cement stages, perforating, acidizing, fracturing, and final TD/PBTD.

## Hole Sections

Collect hole sizes and drilled intervals from drilling, casing, or completion
records.

| Diameter | From Depth | To Depth | Hole Type | Source PDF Page | Notes |
| --- | --- | --- | --- | --- | --- |
| `<diameter>` | `<from_depth>` | `<to_depth>` | `<hole_type>` | `<pdf_page>` | `<notes>` |

Use `Hole Type` for plain-language distinctions such as vertical hole, pilot
hole, lateral hole, surface hole, intermediate hole, or production hole.

## Casing And Tubing Strings

Collect every casing or tubing string described in the source pages.

| Diameter | Weight | Grade | Connection | Setting Depth | String Type | Source PDF Page | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `<diameter>` | `<weight>` | `<grade>` | `<connection>` | `<setting_depth>` | `<string_type>` | `<pdf_page>` | `<notes>` |

For `String Type`, use terms from the source when available, such as surface
casing, intermediate casing, production casing, liner, tubing, or drill pipe.

## Downhole Items And Reference Depths

Collect named downhole items and important reference depths from source text.
They should come from forms, reports, tables, or operation notes.

| Item Type | Depth Or Interval | Details | Source PDF Page | Notes |
| --- | --- | --- | --- | --- |
| `<item_type>` | `<depth_or_interval>` | `<details>` | `<pdf_page>` | `<notes>` |

Examples of item types: KOP, DV tool, float collar, float shoe, tagged cement,
TOC, TD, PBTD, pilot hole TD, top perforation, bottom perforation, and casing
shoe.

## Cement Jobs

Collect every cement job tied to casing, plugs, squeeze work, or completion
treatments.

| Cemented Item | Cement Volume | Cement Class Or Blend | Top Depth | Bottom Depth | Return Or Circulation Note | Source PDF Page | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `<cemented_item>` | `<cement_volume>` | `<cement_class_or_blend>` | `<top_depth>` | `<bottom_depth>` | `<return_or_circulation_note>` | `<pdf_page>` | `<notes>` |

Preserve additives, slurry descriptions, yield, weight, and circulated cement
amounts in `Notes` when they are available.

## Plugs

Collect plug information whenever it appears in operations or cement records.

| Plug Type | Top Depth | Bottom Depth | Cement Volume | Cement Class Or Blend | Source PDF Page | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `<plug_type>` | `<top_depth>` | `<bottom_depth>` | `<cement_volume>` | `<cement_class_or_blend>` | `<pdf_page>` | `<notes>` |

Examples of plug types: pilot-hole plug, isolation plug, kickoff plug, cement
plug, abandonment plug, bridge plug, or retainer.

## Perforations And Treatments

Collect perforation depths and any treatment intervals associated with them.

| Field | Value | Source PDF Page | Notes |
| --- | --- | --- | --- |
| Top perforation depth | `<top_perf_depth>` | `<pdf_page>` | `<notes>` |
| Bottom perforation depth | `<bottom_perf_depth>` | `<pdf_page>` | `<notes>` |
| Perforation list or intervals | `<perforation_list_or_intervals>` | `<pdf_page>` | `<notes>` |
| Acid, frac, squeeze, or cement treatment intervals | `<treatment_intervals>` | `<pdf_page>` | `<notes>` |

If a source page lists many perforation shots or treatment stages, preserve the
full list or summarize the range and note that the full list is on the cited
page.

## Directional And Lateral Details

Collect directional and lateral information from directional surveys and
operation narratives.

| Field | Value | Source PDF Page | Notes |
| --- | --- | --- | --- |
| Kickoff point | `<kickoff_point>` | `<pdf_page>` | `<notes>` |
| Directional drilling note | `<directional_drilling_note>` | `<pdf_page>` | `<notes>` |
| Pilot hole diameter | `<pilot_hole_diameter>` | `<pdf_page>` | `<notes>` |
| Pilot hole total depth or true vertical depth | `<pilot_hole_td_or_tvd>` | `<pdf_page>` | `<notes>` |
| Lateral hole diameter | `<lateral_hole_diameter>` | `<pdf_page>` | `<notes>` |
| Lateral measured depth range | `<lateral_md_range>` | `<pdf_page>` | `<notes>` |
| Lateral true vertical depth range | `<lateral_tvd_range>` | `<pdf_page>` | `<notes>` |
| Lateral direction or azimuth | `<lateral_direction_or_azimuth>` | `<pdf_page>` | `<notes>` |
| Total depth | `<total_depth>` | `<pdf_page>` | `<notes>` |
| Plugged-back total depth | `<plugged_back_total_depth>` | `<pdf_page>` | `<notes>` |

## Formation Tops

Copy formation tops in the order shown on the source page.

| Formation Name | Top Depth | Source PDF Page | Notes |
| --- | --- | --- | --- |
| `<formation_name>` | `<top_depth>` | `<pdf_page>` | `<notes>` |

## Conflicts And Uncertain Data

If two source pages disagree, try you best to decide which is the correct one, if uncertain, keep both values and cite both pages.

| Field | Value A | Source PDF Page A | Value B | Source PDF Page B | Notes |
| --- | --- | --- | --- | --- | --- |
| `<field>` | `<value_a>` | `<pdf_page_a>` | `<value_b>` | `<pdf_page_b>` | `<notes>` |

## Final Check Before Delivery

- Every reported value has an extracted value or is marked `uncertain`.
- Requested values with no source data are omitted from the final output.
- Every value has a source PDF page reference.
- Values from extracted Markdown were checked against the rendered source page
  image when the value is unclear or suspicious.
- Original source wording is preserved in notes when normalization could change
  the meaning.
