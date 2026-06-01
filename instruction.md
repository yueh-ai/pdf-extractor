# Wellbore Diagram Extraction Instructions

Use this file as the required information checklist for recreating a
wellbore-diagram PDF page from source documents. This is a format guide only:
replace every placeholder with extracted values from the source files, and do
not copy values from this instruction file.

## Source Evidence To Check

- The rendered PDF page image.
- The extracted page Markdown from each available run mode.
- Nearby pages or source attachments if a label is cut off or ambiguous.

Prefer the rendered PDF page image for final verification. Markdown may omit
labels that are visible inside the figures.

## Required Source References

Every extracted data value must include where it came from. At minimum, record
the source PDF page or pages checked for that value. If the value came from a
diagram label, table, header block, nearby page, or extracted Markdown, record
that context too.

Use this value format when page-level citation is needed:

```yaml
field_name:
  value: "<extracted_value_or_not_found>"
  source_pdf_pages:
    - "<pdf_page_label_or_number>"
  source_context: "<header|diagram|table|markdown|nearby_page|other>"
  note: "<optional_note_or_uncertain_reason>"
```

If the engineer cannot find a requested value, do not guess. Use:

```yaml
field_name:
  value: "not found"
  source_pdf_pages_checked:
    - "<pdf_page_label_or_number>"
  source_context: "<where_the_engineer_checked>"
  note: "<why_it_was_not_found_if_known>"
```


## Required Well Identity Fields

Extract the well identification block as structured key-value data:

```yaml
well_identity:
  well_name: "<well_name>"
  location_description: "<section_township_range_and_footage>"
  county_state: "<county_state>"
  latitude_longitude: "<latitude>, <longitude>"
  api_number: "<api_number>"
  spud_date: "<spud_date_or_dates>"
  completion_date: "<completion_date>"
  source_references:
    - pdf_page: "<pdf_page_label_or_number>"
      source_context: "<header|markdown|nearby_page|other>"
```

## Required Diagram Data

Collect every labeled wellbore component needed to redraw the diagram.

```yaml
wellbore_diagram:
  datum_elevations:
    kb_elevation_ft: "<kb_elevation_ft>"
    gl_elevation_ft: "<gl_elevation_ft>"
    source_references:
      - pdf_page: "<pdf_page_label_or_number>"
        source_context: "<diagram|markdown|nearby_page|other>"

  hole_sections:
    - label: "<hole_section_label>"
      diameter_in: "<diameter_in>"
      from_depth_ft: "<from_depth_ft>"
      to_depth_ft: "<to_depth_ft>"
      orientation: "<vertical|curve|lateral|pilot>"
      visual_position: "<left|center|right|bottom|other>"
      source_references:
        - pdf_page: "<pdf_page_label_or_number>"
          source_context: "<diagram|markdown|nearby_page|other>"

  casing_strings:
    - label: "<casing_label>"
      outer_diameter_in: "<outer_diameter_in>"
      weight_lb_per_ft: "<weight_lb_per_ft>"
      grade: "<grade>"
      setting_depth_ft: "<setting_depth_ft>"
      string_type: "<surface|intermediate|production|tubing|other>"
      visual_position: "<left|center|right|lateral|other>"
      source_references:
        - pdf_page: "<pdf_page_label_or_number>"
          source_context: "<diagram|markdown|nearby_page|other>"

  cement_jobs:
    - related_component: "<hole_or_casing_label>"
      cement_volume_sacks: "<cement_volume_sacks>"
      cement_class: "<cement_class>"
      top_depth_ft: "<top_depth_ft>"
      bottom_depth_ft: "<bottom_depth_ft>"
      returns_or_circulation_note: "<returns_or_circulation_note>"
      source_references:
        - pdf_page: "<pdf_page_label_or_number>"
          source_context: "<diagram|markdown|nearby_page|other>"

  tools_and_markers:
    - label: "<tool_or_marker_label>"
      depth_ft: "<depth_ft>"
      marker_type: "<dv_tool|kop|tag|toc|td|pbtd|other>"
      visual_symbol: "<symbol_description_if_visible>"
      visual_position: "<left|center|right|lateral|other>"
      source_references:
        - pdf_page: "<pdf_page_label_or_number>"
          source_context: "<diagram|markdown|nearby_page|other>"

  plugs:
    - label: "<plug_label>"
      top_depth_ft: "<top_depth_ft>"
      bottom_depth_ft: "<bottom_depth_ft>"
      cement_volume_sacks: "<cement_volume_sacks>"
      cement_class: "<cement_class>"
      note: "<plug_note>"
      source_references:
        - pdf_page: "<pdf_page_label_or_number>"
          source_context: "<diagram|markdown|nearby_page|other>"

  perforations:
    top_perf_depth_ft: "<top_perf_depth_ft>"
    bottom_perf_depth_ft: "<bottom_perf_depth_ft>"
    visual_pattern: "<perf_symbol_or_pattern_description>"
    source_references:
      - pdf_page: "<pdf_page_label_or_number>"
        source_context: "<diagram|markdown|nearby_page|other>"

  lateral_completion:
    lateral_hole_diameter_in: "<lateral_hole_diameter_in>"
    production_casing_description: "<production_casing_description>"
    production_casing_to_depth_ft: "<production_casing_to_depth_ft>"
    cement_volume_sacks: "<cement_volume_sacks>"
    total_depth_ft: "<total_depth_ft>"
    plugged_back_total_depth_ft: "<plugged_back_total_depth_ft>"
    estimated_top_of_cement_ft: "<estimated_top_of_cement_ft>"
    source_references:
      - pdf_page: "<pdf_page_label_or_number>"
        source_context: "<diagram|markdown|nearby_page|other>"

  pilot_hole:
    pilot_hole_diameter_in: "<pilot_hole_diameter_in>"
    pilot_hole_td_ft_or_tvd: "<pilot_hole_td_ft_or_tvd>"
    plug_interval_top_ft: "<plug_interval_top_ft>"
    plug_interval_bottom_ft: "<plug_interval_bottom_ft>"
    directional_drilling_note: "<directional_drilling_note>"
    source_references:
      - pdf_page: "<pdf_page_label_or_number>"
        source_context: "<diagram|markdown|nearby_page|other>"
```

## Required Formation Tops Table

Extract the formation tops as a table. Preserve the formation names and depths
in the order shown on the page.

```yaml
formation_tops:
  - formation_name: "<formation_name>"
    top_depth_ft: "<top_depth_ft>"
    source_references:
      - pdf_page: "<pdf_page_label_or_number>"
        source_context: "<formation_tops_table|markdown|nearby_page|other>"
```

## Drawing Notes To Preserve

When recreating the page, capture enough layout information to draw the same
kind of diagram:

- Whether the page is marked as not-to-scale or drawn to scale.
- The relative placement of the header block, operator/logo, title, diagram,
  formation-tops table, and signature/date box.
- The relationship between vertical wellbore, curve/lateral section, pilot
  hole, casing strings, cement blocks, plugs, tools, perforations, and TD/PBTD
  labels.
- The visual symbols used for plugs, perforations, cement fill, casing, tubing,
  and open-hole sections.
- Labels that appear inside the diagram image even if they are missing from the
  Markdown output.

## Quality Checks

- Every visible label on the rendered page image is represented in the
  structured extraction.
- Header table fields are not lost when one extraction mode omits them.
- Diagram-image labels are checked manually against the rendered PDF page.
- Units are normalized but the original source text is preserved where useful.
- Each extracted value or list item includes source PDF page references.
- Ambiguous or unreadable fields are marked as `"<uncertain: reason>"` instead
  of guessed.
- Missing fields are marked as `"not found"` with the checked PDF pages noted.
