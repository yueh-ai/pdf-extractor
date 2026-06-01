# Engineer-Readable Wellbore Diagram Collection Guide

Use this guide when collecting information from source PDF files so another
person can redraw a wellbore diagram page. 

Do not guess. If a value cannot be found, write `not found` and list the PDF
page or pages that were checked. If a value is visible but unclear, write
`uncertain` and explain why.

## Source Rule

Every collected item must include:

| Item | What To Write |
| --- | --- |
| Value | The extracted value, `not found`, or `uncertain` |
| Source PDF page | The PDF page number where the value was found |
| Notes | Any uncertainty or conflicts |

The rendered PDF page image is the final authority. Extracted Markdown can miss
text that is visible in the images.

## Well Identity

Collect the well identification block.

| Field | Value | Source PDF Page | Notes |
| --- | --- | --- | --- |
| Well name | `<well_name>` | `<pdf_page>` | `<notes>` |
| Location description | `<location_description>` | `<pdf_page>` | `<notes>` |
| County and state | `<county_state>` | `<pdf_page>` | `<notes>` |
| Latitude and longitude | `<latitude_longitude>` | `<pdf_page>` | `<notes>` |
| API number | `<api_number>` | `<pdf_page>` | `<notes>` |
| Spud date | `<spud_date>` | `<pdf_page>` | `<notes>` |
| Completion date | `<completion_date>` | `<pdf_page>` | `<notes>` |


## Elevations

Collect datum elevations used by the diagram.

| Field | Value | Source PDF Page | Notes |
| --- | --- | --- | --- |
| Kelly bushing elevation | `<kb_elevation>` | `<pdf_page>` | `<notes>` |
| Ground level elevation | `<gl_elevation>` | `<pdf_page>` | `<notes>` |

## Hole Sections

Collect each hole section needed for the drawing.

| Diameter | From Depth | To Depth | Orientation | Source PDF Page | Notes |
| --- | --- | --- | --- | --- | --- |
| `<diameter>` | `<from_depth>` | `<to_depth>` | `<orientation>` | `<pdf_page>` | `<notes>` |

## Casing And Tubing Strings

Collect every casing or tubing string shown.

| Diameter | Weight | Grade | Setting Depth | String Type | Source PDF Page | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `<diameter>` | `<weight>` | `<grade>` | `<setting_depth>` | `<string_type>` | `<pdf_page>` | `<notes>` |

## Cement Jobs

Collect every cement description tied to a hole section, casing string, plug,
or completion interval.

| Related Component | Cement Volume | Cement Class | Top Depth | Bottom Depth | Circulation Or Return Note | Source PDF Page | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `<related_component>` | `<cement_volume>` | `<cement_class>` | `<top_depth>` | `<bottom_depth>` | `<circulation_or_return_note>` | `<pdf_page>` | `<notes>` |

## Tools And Markers

Collect every tool, marker, or depth callout.

| Depth | Marker Type | Source PDF Page | Notes |
| --- | --- | --- | --- |
| `<depth>` | `<marker_type>` | `<pdf_page>` | `<notes>` |

## Plugs

Collect plug information whenever it appears. This may include pilot-hole
plugs, cement plugs, abandonment plugs, or other plugs.

| Top Depth | Bottom Depth | Cement Volume | Cement Class | Source PDF Page | Notes |
| --- | --- | --- | --- | --- | --- |
| `<top_depth>` | `<bottom_depth>` | `<cement_volume>` | `<cement_class>` | `<pdf_page>` | `<notes>` |

## Perforations

Collect perforation intervals and any visible symbol pattern used in the
diagram.

| Field | Value | Source PDF Page | Notes |
| --- | --- | --- | --- |
| Top perforation depth | `<top_perf_depth>` | `<pdf_page>` | `<notes>` |
| Bottom perforation depth | `<bottom_perf_depth>` | `<pdf_page>` | `<notes>` |
| Perforation visual pattern | `<perf_visual_pattern>` | `<pdf_page>` | `<notes>` |

## Lateral Completion

Collect lateral and production completion details.

| Field | Value | Source PDF Page | Notes |
| --- | --- | --- | --- |
| Lateral hole diameter | `<lateral_hole_diameter>` | `<pdf_page>` | `<notes>` |
| Production casing description | `<production_casing_description>` | `<pdf_page>` | `<notes>` |
| Production casing depth | `<production_casing_depth>` | `<pdf_page>` | `<notes>` |
| Cement volume | `<cement_volume>` | `<pdf_page>` | `<notes>` |
| Total depth | `<total_depth>` | `<pdf_page>` | `<notes>` |
| Plugged-back total depth | `<plugged_back_total_depth>` | `<pdf_page>` | `<notes>` |
| Estimated top of cement | `<estimated_top_of_cement>` | `<pdf_page>` | `<notes>` |

## Pilot Hole

Collect pilot-hole details if the diagram or nearby pages include them.

| Field | Value | Source PDF Page | Notes |
| --- | --- | --- | --- |
| Pilot hole diameter | `<pilot_hole_diameter>` | `<pdf_page>` | `<notes>` |
| Pilot hole total depth or true vertical depth | `<pilot_hole_td_or_tvd>` | `<pdf_page>` | `<notes>` |
| Pilot plug interval top | `<pilot_plug_interval_top>` | `<pdf_page>` | `<notes>` |
| Pilot plug interval bottom | `<pilot_plug_interval_bottom>` | `<pdf_page>` | `<notes>` |
| Directional drilling note | `<directional_drilling_note>` | `<pdf_page>` | `<notes>` |

## Formation Tops

Copy formation tops in the order shown on the page.

| Formation Name | Top Depth | Source PDF Page | Notes |
| --- | --- | --- | --- |
| `<formation_name>` | `<top_depth>` | `<pdf_page>` | `<notes>` |

## Drawing Layout Notes

Describe enough layout information for a drafter or engineer to redraw the
page.

| Layout Item | Description | Source PDF Page | Notes |
| --- | --- | --- | --- |
| Header location | `<header_location>` | `<pdf_page>` | `<notes>` |
| Operator or logo location | `<operator_or_logo_location>` | `<pdf_page>` | `<notes>` |
| Formation table location | `<formation_table_location>` | `<pdf_page>` | `<notes>` |
| Vertical wellbore position | `<vertical_wellbore_position>` | `<pdf_page>` | `<notes>` |
| Lateral section position | `<lateral_section_position>` | `<pdf_page>` | `<notes>` |
| Pilot hole position | `<pilot_hole_position>` | `<pdf_page>` | `<notes>` |
| Cement fill style | `<cement_fill_style>` | `<pdf_page>` | `<notes>` |
| Plug symbol style | `<plug_symbol_style>` | `<pdf_page>` | `<notes>` |
| Perforation symbol style | `<perforation_symbol_style>` | `<pdf_page>` | `<notes>` |
| Casing or tubing style | `<casing_or_tubing_style>` | `<pdf_page>` | `<notes>` |

## Final Check Before Delivery

- Every requested diagram value has either an extracted value, `not found`, or
  `uncertain`.
- Every value has a source PDF page reference.
- Values from the header, diagram, and tables are all checked against the
  rendered PDF page image.
- Markdown-only extraction is not treated as complete if the page image shows
  more relevant text.
- Original source wording is preserved in notes when normalization could change
  the meaning.
