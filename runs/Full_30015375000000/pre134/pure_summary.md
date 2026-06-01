# Wellbore Extraction Summary

This is a cleaned, single-file summary of the extracted wellbore facts. Evidence citations, source-page columns, section-report links, and heuristic logs are intentionally omitted.

## Key Conflict Themes

- Operator sequence changes from Yates Petroleum Corporation in early drilling and completion records to EOG Resources Inc / EOG Y Resources, Inc. in later records.
- Coordinates are close but labeled differently: one source labels them as the center of proposed design, while survey records use wellhead/reference coordinates.
- Elevation datum values vary: ground/GR is mostly 3172 ft with one 3170 ft field; KB/RKB-related values appear as 3191 ft, 3190.50 ft, and about 3190 ft.
- The well plan changed materially: original TD/KOP/lateral TVD and casing depths were revised, and actual TD/casing/hole-size records differ from both original and revised plans.
- Casing, hole, cement, and plug values should be read as proposal -> revision -> actual sequence where that distinction is present.
- Formation tops differ between directional-plan markers and the formal completion table.
- Perforation and stimulation records are internally consistent; the main treatment uncertainty is a tubing pickle/acetic-acid operation with no stated depth interval.

## Deduplicated Results

### Well Identity

| Field | Value | Notes |
| --- | --- | --- |
| Well name | Jericho BKJ State Com #2H | source records source form states "Facility or well name: Jericho BKJ State Com #2H". Duplicate forms use capitalization and number variants including "JERICHO BKJ STATE COM #002H", "Jericho BKJ State Com" plus "2H", and "JERICHO BKJ STATE COM 2H". |
| Location description | Unit Letter A, Section 15, Township 25S, Range 27E, NMPM; 660 ft from the North line and 330 ft from the East line | source records source form gives the clearest complete surface location wording. This matches the APD/plats on source records and the source records location fields. |
| County and state | Eddy County, New Mexico | rendered image confirms County is "Eddy" on the C-144 form, under the State of New Mexico heading. Survey pages also state "EDDY COUNTY, NEW MEXICO". |
| Latitude and longitude | N 32.135547, W 104.170700 (NAD83) | rendered image confirms NAD 1983 is checked. The source labels this as the "Center of Proposed Design"; see coordinate uncertainty below. |
| API number | 30-015-37500 | Same API appears on APD, permit comment, sundry, and completion forms. Later C-129 forms omit dashes as "3001537500"; treated as the same API format. |
| Spud date | 2/1/2010 | source records subsequent report states the well "Spudded 12-1/4\" hole at 4:00 PM" on 2/1/10. source records also lists 2/1/2010 as the spud date. |
| Completion date | 9/20/2010 | source records C-105 completion report field 16 states "Date Completed (Ready to Produce) 9/20/10". Survey "Date Completed" values were not treated as well completion dates. |
| Operator | EOG Resources Inc | Later source forms/conditions list EOG Resources Inc as operator. Earlier drilling and completion forms list Yates Petroleum Corporation; preserved as a conflict/sequence below. |

### Elevations

| Field | Value | Notes |
| --- | --- | --- |
| Ground level elevation | 3172 ft; also stated as `3172'GR`, `Ground Elevation: 3172.00`, `Altitude:3172.00' Ground To MSL`, and `ALTITUDE: 3172 Feet` | Consolidated the recurring ground/GR datum. source records labels it `Ground Level Elevation`; source records, and 56 use `GR`; source records, and 50 state ground to MSL; source records list altitude with the same value. |
| Ground level elevation | 3170' | C-103 elevation field reads `3170'` but does not show a GR/KB/RKB/RT suffix. Kept separate because it conflicts with the repeated 3172 ground/GR value. Visual verification confirmed the page image reads `3170'`. |
| Kelly bushing elevation | 3191'KB | Completion report field 17 states `3172'GR 3191'KB`. Kept as the completion-report KB datum. |
| Kelly bushing elevation | RKB / well reference: `WELL @ 3190.50ft (Original Well Elev)`; source records labels it `RKB Elevation: Well @ 3190.50... (Original Well Elev)` | source records use the same value as TVD/MD reference; source records repeats it in the well-details table as RKB elevation. Visual verification of source records supports the 3190.50 RKB reading. |
| Kelly bushing elevation | 18.00' Kelly Bushing To Ground; also `KELLY BUSHING ELEVATION: 18` | Relative KB height above ground, not an absolute MSL elevation. With 3172 ft ground/altitude, this implies about 3190 ft KB. |
| Other datum elevation | `Elevation: 3190.00 feet` | PathFinder Magnetic & Grid Calculations coordinate elevation. Datum label is not explicit, but the value agrees with 3172 ft ground plus 18 ft Kelly bushing-to-ground reference. |

### Operation Timeline

| Date | Operation | Depth Or Interval | Details | Notes |
| --- | --- | --- | --- | --- |
| 2010-01-05 / 2010-01-06 | Original proposed drilling and casing plan | Proposed TD 11,375'; pilot hole to 8,500'; proposed production casing to 11,375' | APD proposed 13-3/8" surface casing at 400', 9-5/8" intermediate casing at 2,400', and 5-1/2" production casing at 11,375'. Permit comments proposed a vertical pilot hole to 8,500', plugback with a kickoff plug near 6,483', directional drilling to 7,233' MD, then lateral drilling to 11,375' MD. | Proposed plan only; later revised and not the final actual configuration. |
| 2010-02-01 | Spud | 12-1/4" hole to 10' | Spudded 12-1/4" hole at 4:00 PM and drilled to 10'. | C-105 later reports RH spud date as 2/1/10 and RT date as 6/18/10. |
| 2010-02-19 through 2010-05-24 | Incremental new-hole reports | 12-1/4" hole from 15' TD to 40' TD | Six repeated sundries report 5' new-hole increments: 2/19/10 to 15', 3/10/10 to 20', 3/29/10 to 25', 4/16/10 to 30', 5/5/10 to 35', and 5/24/10 to 40'. | Compressed because each report is the same operation pattern and only advances shallow hole depth by 5'. |
| 2010-06-11 | Revised change-plan request | Planned TD 10,200' MD; planned kickoff near 5,647'; contingency DV tool/cut depth 5,600' | Operator requested target-formation change and attached revised directional/casing plan. Revised plan proposed 8-3/4" hole from intermediate casing drillout through the pilot hole, plugback/kickoff near 5,647', 8-3/4" hole to 6,400' MD, 7-7/8" hole to 10,200' MD, and 5-1/2" casing; contingency plan used 7" casing at 6,400' and 4-1/2" casing to 10,200' with DV tool/cut depth around 5,600'. | Proposed/revised plan only; actual TD and production casing depth were later reported as 10,495' and 10,490'. |
| 2010-06-11 | Set conductor | 20" conductor to 40' | Set 40' of 20" conductor at 1:30 PM. | Actual operation; C-105 later summarizes 20" conductor at 40'. |
| 2010-06-18 | Resume drilling, run surface casing, cement surface casing | 17-1/2" hole to 470'; 13-3/8" casing at 470' | Resumed drilling at 7:30 AM, TD'd 17-1/2" hole to 470', set 13-3/8" 48# H-40 ST&C casing at 470', cemented with 165 sx Class C lead plus 200 sx Class C tail, circulated 120 sx to pit, tested casing to 600 psi for 30 min, waited on cement, reduced hole to 12-1/4", and resumed drilling. | C-105/C-104 summaries confirm 13-3/8" casing at 470' with 365 sx circulated. |
| 2010-06-21 | Run intermediate casing and cement | 12-1/4" hole to 2,232'; 9-5/8" casing at 2,232' | TD'd 12-1/4" hole to 2,232', set 9-5/8" 36# J-55 LT&C casing at 2,232', cemented with 560 sx 35:65:6 Poz C blend plus 200 sx Class C tail, circulated 140 sx to pit, tested casing to 1,200 psi for 30 min, waited on cement, reduced hole to 8-3/4", and resumed drilling. | C-105/C-104 summaries confirm 9-5/8" casing at 2,232' with 760 sx circulated. |
| 2010-06-28 | Reach pilot-hole TD | Pilot hole TD 8,500' | TD'd the pilot hole to 8,500' at 6:00 PM. | Actual pilot-hole depth matches the original plan, not the later 10,200' revised lateral TD. |
| 2010-06-30 | Set isolation and kickoff plugs; start directional drilling | Isolation plug 6,600'-6,815'; kickoff plug 5,380'-5,880'; tagged cement 5,569'; slid to 5,710' | Set isolation plug with 120 sx Class H with additives; set kickoff plug with 300 sx Class H with additives; waited on cement; tagged cement at 5,569'; slid to 5,710' and started directionally drilling. | Actual directional start differs from proposed kickoff depths in earlier plans. |
| 2010-07-11 | Reach final TD | 8-3/4" hole TD 10,495' | Reached TD of the 8-3/4" hole at 10,495'. | source records rendered image confirms Date T.D. Reached as 7/11/10; OCR text OCR read it as 7/1/10. |
| 2010-07-13 | Run production casing and cement in two stages | 5-1/2" 17# L-80 LT&C 8rd casing at 10,490'; float collar at 10,444' | Set 5-1/2" production casing at 10,490'; float collar at 10,444'. Cemented stage 1 with 700 sx PVL blend and circulated 107 sx off DV tool; cemented stage 2 with 680 sx 35:65:6 Poz C blend. | C-105 summarizes 1,380 sx and estimated TOC 1,700'. |
| 2010-07-14 | Rig released | Final drilled wellbore after TD/casing | C-105 reports rig released 7/14/10. | Summary date; no separate detailed C-103 operation row found. |
| 2010-07-26 | Drill cement and DV tool; pressure test casing | Tagged 5,374'; drilled cement to 5,496'; DV tool at 5,496' | Tagged up at 5,374', drilled cement down to 5,496', began drilling and then drilled out DV tool, circulated clean, and pressured casing to 3,000 psi for 15 min. | This prepares the cased wellbore for completion operations. |
| 2010-07-27 | Tag PBTD, pickle tubing, acid spot, clean DV tool | PBTD 10,440'; DV tool 5,496' | Tagged PBTD at 10,440', pickled tubing with 1,000 gal 15% NEFE HCL, spotted 1,500 gal 10% acetic acid, and cleaned up DV tool at 5,496'. | C-105 reports plugback measured depth as 10,440'. |
| 2010-07-28 | Test casing, perforate upper Bone Spring interval, and frac | Perfs at 9,984', 10,134', 10,284', and 10,434'; interval 9,984'-10,434' | Tested casing to 3,000 psi; estimated TOC 1,700'. Perforated four Bone Spring depths with 9 shots each, then frac'd with 30# borate gel, 66,508# Ottawa 40/70, 73,044# Super LC 20/40, and 38,655# into formation. | source records duplicates the perforation/treatment interval without dates. |
| 2010-09-10 | Acid spot, perforate, and frac middle Bone Spring stages | 9,834'-9,384' and 9,234'-8,734'; acid spots at 9,854' and 9,250' | Spotted 1,500 gal 7-1/2% HCL acid at 9,854', perforated 9,834', 9,684', 9,534', and 9,384' with 9 shots each, and frac'd. Then spotted acid at 9,250', perforated 9,234', 9,084', 8,934', and 8,734' with 9 shots each, and frac'd. | source records duplicates the same treatment ranges without dates. |
| 2010-09-11 | Acid spot, perforate, frac lower Bone Spring stages; install completion hardware | 8,634'-6,384' perf depths; flow-through plugs at 6,854', 7,454', 8,054', 8,654', 9,250', and 9,854'; tubing/packer at 5,600' | Completed four additional acid/perforation/frac groups covering 8,634'-8,184', 8,034'-7,584', 7,434'-6,984', and 6,834'-6,384'. Flowed through plugs at listed depths. Left AS-1 packer with 2.25" S-lok in place and 2-7/8" 6.5# L-80 tubing at 5,600'. | C-105 tubing record confirms 2-7/8" tubing and packer depth at 5,600'; source records duplicates treatment ranges without dates. |
| 2010-09-20 | Completed and ready to produce | Producing interval 6,384'-10,434'; TD 10,495'; PBTD 10,440' | C-104/C-105 report ready/completed-to-produce date of 9/20/10 with final producing interval 6,384'-10,434' Bone Spring. | Summary completion date, after the dated stimulation operations. |
| 2010-09-21 | First production and gas delivery | Producing interval 6,384'-10,434' | C-104/C-105 report Date New Oil / Date First Production and Gas Delivery Date as 9/21/10. | Production start; included as completion endpoint. |

### Hole Sections

| Diameter | From Depth | To Depth | Hole Type | Notes |
| --- | --- | --- | --- | --- |
| 12-1/4" | surface / spud | 40' | early spud/new-hole interval | C-103 spud/new-hole reports start a 12-1/4" hole on 2/1/10 to 10' and later report 5' increments to TD 40'. This appears tied to the RH spud sequence and conflicts with the later 26" conductor-hole completion record for the 0'-40' conductor interval. |
| 26" | surface | 40' | conductor hole | Completion and C-105 casing records list 20" conductor set at 40' in a 26" hole. source records separately reports 40' of 20" conductor set on 6/11/10. |
| 17-1/2" | surface / below 40' conductor | 470' | surface hole | Subsequent report says TD 17-1/2" hole to 470' and set 13-3/8" casing at 470'. Completion/casing records repeat 13-3/8" casing at 470' with 17-1/2" hole size. |
| 12-1/4" | 470' | 2,232' | intermediate hole | Actual surface/intermediate casing report says the hole was reduced to 12-1/4" after surface casing, then TD 12-1/4" hole to 2,232' and set 9-5/8" casing. Completion/casing records repeat 9-5/8" casing at 2,232' with 12-1/4" hole size. |
| 8-3/4" | 2,232' | 8,500' | pilot hole | Actual report says the hole was reduced to 8-3/4" after the 12-1/4" intermediate hole; production-casing report says TD pilot hole to 8,500' on 6/28/10. Directional survey paperwork identifies the pilot-hole survey and verifies projected bit depth of 8,500'. |
| 8-3/4" | 5,710' | 10,495' | directional production/lateral hole | Actual report says cement was tagged at 5,569', the assembly slid to 5,710', and directional drilling started; it then reached TD 8-3/4" hole to 10,495'. Completion/casing records list TD 10,495', 5-1/2" casing at 10,490', and 8-3/4" hole size. Directional survey pages carry the 10,495' measured-depth endpoint. |
| 17.5" | surface | 400' | proposed surface hole | Original C-101 proposed casing/cement program lists Surf hole size 17.5 with 13.375 casing setting depth 400'. Superseded by actual 17-1/2" hole to 470'. |
| 12.25" | 400' | 2,400' | proposed intermediate hole | Original C-101 proposed casing/cement program lists Int1 hole size 12.25 with 9.625 casing setting depth 2,400'. Superseded by actual 12-1/4" hole to 2,232'. |
| 7.875" | 2,400' | 11,375' | original proposed production hole | Original C-101 proposed casing/cement program lists Prod hole size 7.875 with 5.5 casing setting depth 11,375'. Later drilling plans and actual records changed both depth and diameter. |
| 8-3/4" | approx. 6,483' KOP | 7,233' MD | original proposed kickoff/build hole | Permit comments say the pilot hole would be drilled vertically to 8,500', plugged back, and directionally drilled at 12 degrees per 100' with an 8-3/4" hole to 7,233' MD. |
| 6-1/8" | 7,233' MD | 11,375' MD | original proposed contingency lateral hole | Permit comments and contingency casing design describe a 6-1/8" hole to 11,375' MD if 7" casing was set at 7,233' MD. This was a planned contingency, not the final completion record. |
| 7-7/8" | 7,233' MD | 11,375' MD | original proposed no-7" casing lateral hole | Permit comments say that if 7" casing was not set, hole size would be reduced to 7-7/8" and drilled to 11,375' MD where 5-1/2" casing would be set. This was later revised. |
| 8-3/4" | drill-out of intermediate casing / approx. 5,647' KOP | 6,400' MD | revised proposed pilot/build hole | Revised plan says production hole size would be 8-3/4" from drill-out of intermediate casing to pilot-hole TD, then plugged back and kicked off at about 5,647' with 8-3/4" hole to 6,400' MD. Directional plan page lists KOP near 5,647.54' and EOC near 6,397.53'. |
| 7-7/8" | 6,400' MD | 10,200' MD | revised proposed production/lateral hole | Revised plan says hole size would be reduced to 7-7/8" and drilled to 10,200' MD where 5-1/2" casing would be run and cemented; directional plan ends near 10,200'. Actual records instead report 8-3/4" hole to 10,495'. |
| 6-1/8" | 6,400' MD | 10,200' MD | revised contingency lateral hole | Revised contingency plan says if 7" casing was set at 6,400' MD, a 6-1/8" hole would then be drilled to 10,200' MD for 4-1/2" casing. This contingency was not the final completion record. |

### Casing And Tubing Strings

| Diameter | Weight | Grade | Connection | Setting Depth | String Type | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 20" | not stated | not stated | not stated | 40' | Actual conductor | source records reports 40' of 20" conductor set. source records C-105 casing record repeats 20" conductor at 40' in a 26" hole with Redi-mix cement. |
| 13-3/8" | 48# | H-40 | ST&C | 470' | Actual surface casing | source records subsequent report gives full string details and cement job. source records completion report repeats the 13-3/8" casing at 470'. |
| 9-5/8" | 36# | J-55 | LT&C | 2,232' | Actual intermediate casing | source records subsequent report gives full string details and cement job. source records completion report repeats the 9-5/8" casing at 2,232'. |
| 5-1/2" | 17# | L-80 | LT&C 8rd | 10,490' | Actual production casing | source records reports the production casing set with float collar at 10,444'. source records completion report repeats 5-1/2" casing at 10,490'. |
| 2-7/8" | 6.5# | L-80 | not stated | 5,600' | Actual tubing | source records states "2-7/8" 6.5# L-80 tubing at 5600'"; source records rendered C-105 table shows tubing size 2-7/8", depth set 5,600', and packer set 5,600'. The "2.25" S-lok" wording on source records belongs to the AS-1 packer, not a tubing connection. |
| 13.375" | 48 lb/ft | not stated | not stated | 400' | Original proposed surface casing | Original C-101 proposed casing and cement program, type "Surf"; 17.5" hole, 425 sx cement, estimated TOC 0. |
| 9.625" | 36 lb/ft | not stated | not stated | 2,400' | Original proposed intermediate casing | Original C-101 proposed casing and cement program, type "Int1"; 12.25" hole, 825 sx cement, estimated TOC 0. |
| 5.5" | 17 lb/ft | not stated | not stated | 11,375' | Original proposed production casing | Original C-101 proposed casing and cement program, type "Prod"; 7.875" hole, 2,075 sx cement, estimated TOC 1,900'. |
| 7" | 26 #/ft | J-55 | LT&C | 0-100 ft section; string set at 7,233' MD | Original contingency 2nd intermediate casing | Original contingency design: if hole conditions dictated, 7" casing would be set at 7,233' MD (6,960' TVD). rendered image checked. |
| 7" | 23 #/ft | J-55 | LT&C | 100-5,800 ft section; string set at 7,233' MD | Original contingency 2nd intermediate casing | Same original contingency 7" casing design; middle section total 5,700 ft. rendered image checked. |
| 7" | 26 #/ft | J-55 | LT&C | 5,800-7,233 ft section; string set at 7,233' MD | Original contingency 2nd intermediate casing | Same original contingency 7" casing design; lower section total 1,433 ft. rendered image checked. |
| 4.5" | 11.6 #/ft | HCP-110 | LT&C | 0-11,375 ft | Original contingency production casing | Original contingency design: 4-1/2" casing would be set and cemented if 7" casing was used; source says casing would be cut and pulled at 6,400' after completion. rendered image checked. |
| 5.5" | 17 #/ft | P-110 | LT&C | 0-6,400 ft section; revised string planned to 10,200' MD | Revised proposed production casing | June 2010 change-plan production design; source states 5-1/2" casing would be run and cemented to 10,200' MD. rendered image checked. |
| 5.5" | 17 #/ft | L-80 | LT&C | 6,400-10,200 ft section; revised string planned to 10,200' MD | Revised proposed production casing | Lower section of same revised 5-1/2" production casing design. rendered image checked. |
| 7" | 26 #/ft | J-55 | LT&C | 0-100 ft section; string set at 6,400' MD | Revised contingency 2nd intermediate casing | Revised contingency design: if hole conditions dictated, 7" casing would be set at 6,400' MD (6,125' TVD). rendered image checked. |
| 7" | 23 #/ft | J-55 | LT&C | 100-5,900 ft section; string set at 6,400' MD | Revised contingency 2nd intermediate casing | Same revised contingency 7" casing design; OCR read one connection as "LT&G", but rendered image shows LT&C. |
| 7" | 26 #/ft | J-55 | LT&C | 5,900-6,400 ft section; string set at 6,400' MD | Revised contingency 2nd intermediate casing | Same revised contingency 7" casing design; lower section total 500 ft. rendered image checked. |
| 4.5" | 11.6 #/ft | HCP-110 | LT&C | 0-10,200 ft | Revised contingency production casing | Revised contingency design: 4-1/2" casing would be set and cemented if 7" casing was used; source says casing would be cut and pulled at 5,600' after completion. rendered image checked. |

### Downhole Items And Reference Depths

| Item Type | Depth Or Interval | Details | Notes |
| --- | --- | --- | --- |
| Proposed TD / proposed production casing setting depth | 11,375' MD | Initial APD proposed depth and 5-1/2" production casing setting depth. | Initial design only; later revised and actual depths differ. |
| Pilot-hole TD | 8,500' | Pilot hole planned and drilled vertically to 8,500'. Initial comments describe this as the deepest TVD in the well. | Actual operation on source records reports TD pilot hole to 8,500'. |
| Initial planned kick-off plug / KOP reference | 400'-500' plug at approx. 6,483' | Initial APD plan to plug back and kick off after drilling the pilot hole. | Superseded by later revised KOP and actual kick-off operations. |
| Revised KOP | approx. 5,647'; directional plan KOP 5,647.54' MD / 5,647.54' TVD | Revised plan after the target formation change. | Rendered source records confirms the KOP label as 5,647.54'; one markdown table instance OCRs this as 5,847.54'. |
| Revised EOC | 6,397.53' MD / 6,125.00' TVD | Directional plan end of curve / Avalon Shale target reference. | Revised plan reference. |
| Revised EOL / revised planned TD | 10,200.07' MD / 6,125.01' TVD | Directional plan end of lateral. Narrative revised plan also states TD of 10,200' MD and 6,125' TVD. | Actual TD later reported as 10,495'. |
| Conductor casing shoe | 40' | 20" conductor set. | Repeated in completion casing records. |
| Surface casing shoe | 470' | 13-3/8" 48# H-40 ST&C casing set at 470'; 17-1/2" hole TD also reported as 470'. | Initial APD proposed 400'. |
| Intermediate casing shoe | 2,232' | 9-5/8" 36# J-55 LT&C casing set at 2,232'; 12-1/4" hole TD also reported as 2,232'. | Initial APD proposed 2,400'. |
| Revised contingency 7" casing shoe | 6,400' MD / 6,125' TVD | Revised contingency casing plan for 7" casing. | Earlier contingency plan used 7,233' MD / 6,960' TVD. |
| Production casing shoe | 10,490' | 5-1/2" 17# L-80 LT&C 8rd production casing set at 10,490'. | Revised plan targeted 10,200'; actual TD is 10,495'. |
| Float collar | 10,444' | Float collar in the 5-1/2" production casing string. | No float shoe reference found in allowed pages. |
| Actual TD | 10,495' | Reached TD in 8-3/4" hole; completion records repeat total measured depth. | Final reported TD in allowed pages. |
| PBTD | 10,440' | Plug-back measured depth / tagged PBTD. | Consistent across completion reports and workover narrative. |
| Isolation plug | 6,600'-6,815' | Isolation plug set with 120 sx Class H cement plus additives. | Downhole reference item from actual operations. |
| Kick-off plug | 5,380'-5,880' | Kick-off plug set with 300 sx Class H cement plus additives. | Actual plug interval used before directional drilling. |
| Tagged cement / directional start | Tagged at 5,569'; slid to 5,710' | Tagged cement, slid, and started directional drilling. | Practical actual kick-off/start reference. |
| Cement tag / DV drill-out | Tagged at 5,374'; drilled cement down to 5,496' | Tagged cement during post-cement cleanup, drilled to the DV tool, and began drilling the DV tool. | Separate from the kick-off-plug tag on source records. |
| DV tool | approx. 5,600' planned; 5,496' actual cleanup/drill-out reference | Revised plan places the DV tool around 5,600'; actual narrative reports drilling/cleaning up the DV tool at 5,496'. | source records has an earlier contingency DV/cut-pull reference around 6,400'. |
| TOC | Estimated 1,700' | Estimated production casing top of cement in completion and casing records. | Initial APD production TOC was 1,900'; revised contingency TOC was 5,600' for an alternate 4-1/2" contingency string. |
| Top perforation | 6,384' | Shallowest Bone Spring perforation in final interval/list. | source records summarize the producing interval as 6,384'-10,434'; source records gives the full perforation list. |
| Bottom perforation | 10,434' | Deepest Bone Spring perforation in final interval/list. | source records contains the first perforation group including 10,434'. |
| Flow-through plugs | 6,854'; 7,454'; 8,054'; 8,654'; 9,250'; 9,854' | Flow-through plugs referenced after frac stages. | No bridge plug, retainer, CIBP, or cast-iron bridge plug reference found in allowed pages. |
| AS-1 packer / tubing depth reference | 5,600' | AS-1 packer with 2.25" S-lok in place and 2-7/8" L-80 tubing at 5,600'. | Treated as a downhole reference item because it is a repeated completion depth. |

### Cement Jobs

| Cemented Item | Cement Volume | Cement Class Or Blend | Top Depth | Bottom Depth | Return Or Circulation Note | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 13-3/8 in surface casing, proposed APD | 425 sx | Not stated | 0 ft estimated TOC | 400 ft setting depth | Estimated TOC at surface | Initial proposed casing/cement program. |
| 9-5/8 in intermediate casing, proposed APD | 825 sx | Not stated | 0 ft estimated TOC | 2,400 ft setting depth | Estimated TOC at surface | Initial proposed casing/cement program. |
| 5-1/2 in production casing, proposed APD | 2,075 sx | Not stated | 1,900 ft estimated TOC | 11,375 ft setting depth | Estimated TOC 1,900 ft | Initial proposed casing/cement program. |
| 7 in second intermediate casing, original contingency proposal | 760 sx lead plus 125 sx tail | Lead Lite crete; tail PVL | Surface | 7,233 ft MD | TOC = surface | Proposed if hole conditions required 7 in casing. Notes from image: lead YLD 2.66, wt 9.9; tail YLD 1.41, wt 13. |
| 4-1/2 in production casing, original contingency proposal | 675 sx | PVL | 6,400 ft | 11,375 ft MD | One stage up to DV tool at approx. 6,400 ft | Image verification corrected the markdown: page states DV tool, and cemented with 675 sx PVL, YLD 1.41, wt 13, TOC 6,400 ft. |
| 7 in second intermediate casing, revised contingency proposal | 450 sx lead plus 125 sx tail | Lead Lite crete; tail PVL | 1,900 ft | 6,400 ft MD | TOC = 1,900 ft | Revised change-plan contingency. Lead YLD 2.66, wt 9.9; tail YLD 1.41, wt 13. |
| 4-1/2 in production casing, revised contingency proposal | 625 sx | PVL | 5,600 ft | 10,200 ft MD | One stage up to DV tool at approx. 5,600 ft | Revised change-plan contingency. PVL YLD 1.41, wt 13; TOC 5,600 ft. |
| 20 in conductor casing, actual completion record | Redi-mix, volume not stated | Redi-mix | Surface | 40 ft | To surface | C-105 casing record. Same record also appears on source records. |
| 13-3/8 in surface casing, actual | 365 sx total: 165 sx lead plus 200 sx tail | Class C lead and Class C tail | Surface | 470 ft | Circulated 120 sx to pit | Lead additives: 0.125 lb/sx D130, 4% D20, 2% S1, 0.2% D46, yld 1.96, wt 12.9. Tail: 0.5% S1, yld 1.34, wt 14.8. Final C-105 summarizes as 365 sx (circ). |
| 9-5/8 in intermediate casing, actual | 760 sx total: 560 sx lead plus 200 sx tail | 35:65:6 Poz C lead and Class C tail | Surface | 2,232 ft | Circulated 140 sx to pit | Lead additives: 0.125 lb/sx D130, 2 lb/sx D142, 6% D20, 5% D44, 0.2% D46, yld 2.08, wt 12.6. Tail Class C yld 1.33, wt 14.8. Final C-105 summarizes as 760 sx (circ). |
| Isolation plug, actual | 120 sx | Class H with additives | 6,600 ft | 6,815 ft | WOC; no returns stated | Set after pilot hole TD. Additives not itemized in source. |
| Kickoff plug, actual | 300 sx | Class H with additives | 5,380 ft set interval; tagged cement at 5,569 ft | 5,880 ft | WOC; no returns stated | Set after isolation plug. Source says tagged cement at 5,569 ft, slid to 5,710 ft, then started directional drilling. |
| 5-1/2 in production casing, actual stage 1 | 700 sx | PVL | DV tool, approx. 5,496 ft | 10,490 ft casing shoe | Circulated 107 sx cement off DV tool | Float collar at 10,444 ft. Additives: 0.2% D112, 30% D151, 2% D174, 0.01 GPS D177, 0.2% D46, 0.8% D800, 0.5% D079; yld 1.83, wt 13. source records later says DV tool cleaned up at 5,496 ft. |
| 5-1/2 in production casing, actual stage 2 | 680 sx | 35:65:6 Poz C | 1,700 ft estimated TOC | DV tool, approx. 5,496 ft | No stage-2 returns stated; overall TOC estimated 1,700 ft | Additives: 0.2% D13, 0.125 lb/sx D130, 0.01 GPS D177, 6% D20, 2 lb/sx D42, 5% D44, 0.2% D46; yld 2.07, wt 12.6. Final C-105 summarizes production casing as 1,380 sx, TOC 1,700 ft estimated. |
| Tubing pickle and acetic acid spot, completion treatment | 1000g 15% NEFE HCL; 1500g 10% acetic acid | Acid treatment, not cement | Not stated | Not stated | No returns stated | Included because completion treatments were requested. No cement or squeeze material stated. |
| Bone Spring frac treatment | 66,508 lb Ottawa 40/70; 73,044 lb Super LC 20/40; 38,655 lb into formation | 30 lb borate gel | 9,984 ft | 10,434 ft | No returns stated | source records duplicates and clarifies the completion-treatment table. No cement or squeeze material stated. |
| Acid spot completion treatment | 1500g 7-1/2% HCL acid | Acid treatment, not cement | 9,854 ft | 9,854 ft | No returns stated | Associated with the 9,384 ft to 9,834 ft frac sequence. |
| Bone Spring frac treatment | 1500g 7-1/2% HCL acid; 59,417 lb Ottawa 40/70; 120,000 lb Ottawa 20/40; 80,000 lb Super LC 20/40 | 30 lb borate gel | 9,384 ft | 9,834 ft | No returns stated | No cement or squeeze material stated. |
| Acid spot completion treatment | 1500g 7-1/2% HCL acid | Acid treatment, not cement | 9,250 ft | 9,250 ft | No returns stated | Associated with the 8,734 ft to 9,234 ft frac sequence. |
| Bone Spring frac treatment | 1500g 7-1/2% HCL acid; 65,013 lb 40/70; 124,965 lb Ottawa 20/40; 78,743 lb Super LC 20/40 | 30 lb borate gel | 8,734 ft | 9,234 ft | No returns stated | No cement or squeeze material stated. |
| Acid spot completion treatment | 1500g 7-1/2% HCL acid | Acid treatment, not cement | 8,654 ft | 8,654 ft | No returns stated | Associated with the 8,184 ft to 8,634 ft frac sequence. |
| Bone Spring frac treatment | 1500g 7-1/2% HCL acid; 64,803 lb Ottawa 40/70; 122,448 lb Ottawa 20/40; 81,814 lb Super LC 20/40 | 30 lb borate gel | 8,184 ft | 8,634 ft | No returns stated | No cement or squeeze material stated. |
| Acid spot completion treatment | 1500g 7-1/2% HCL acid | Acid treatment, not cement | 8,054 ft | 8,054 ft | No returns stated | Associated with the 7,584 ft to 8,034 ft frac sequence. |
| Bone Spring frac treatment | 1500g 7-1/2% HCL acid; 62,996 lb Ottawa 40/70; 118,657 lb Ottawa 20/40; 81,550 lb Super LC 20/40 | 30 lb borate gel | 7,584 ft | 8,034 ft | No returns stated | No cement or squeeze material stated. |
| Acid spot completion treatment | 1500g 7-1/2% HCL acid | Acid treatment, not cement | 7,454 ft | 7,454 ft | No returns stated | Associated with the 6,984 ft to 7,434 ft frac sequence. |
| Bone Spring frac treatment | 1500g 7-1/2% HCL acid; 62,528 lb Ottawa 40/70; 118,125 lb Ottawa 20/40; 82,525 lb Super LC 20/40 | 30 lb borate gel | 6,984 ft | 7,434 ft | No returns stated | No cement or squeeze material stated. |
| Acid spot completion treatment | 1500g 7-1/2% HCL acid | Acid treatment, not cement | 6,854 ft | 6,854 ft | No returns stated | Associated with the 6,384 ft to 6,834 ft frac sequence. Flow-through plugs later noted at 6,854 ft, 7,454 ft, 8,054 ft, 8,654 ft, 9,250 ft, and 9,854 ft. |
| Bone Spring frac treatment | 1500g 7-1/2% HCL acid; 23,248 lb Ottawa 40/70; 91,828 lb Ottawa 20/40; 71,106 lb Super LC 20/40 | 30 lb borate gel | 6,384 ft | 6,834 ft | No returns stated | No cement or squeeze material stated. |

### Plugs

| Plug Type | Top Depth | Bottom Depth | Cement Volume | Cement Class Or Blend | Notes |
| --- | --- | --- | --- | --- | --- |
| Proposed pilot-hole/kickoff plugback plug | approx. 6483' plug/KOP depth | not stated | not stated | not stated | Original permit comments state the pilot hole would be drilled vertically to 8500' and the well "plugged back with 400'-500' kick off plug at approx. 6483'." Kept as original proposed plan, not actual execution. |
| Revised planned plugback/kickoff plug | approx. 5647' plugback/KOP depth | not stated | not stated | not stated | Revised production plan says the hole would be plugged back and kicked off at approx. 5647' after drilling from intermediate casing to pilot-hole TD. No cement volume or blend stated. |
| Isolation plug | 6600' | 6815' | 120 sx | Class "H" with additives | Subsequent report says 6/30/10: set isolation plug from 6600'-6815' after TD pilot hole to 8500'. |
| Kickoff plug | 5380' | 5880' | 300 sx | Class "H" with additives | Subsequent report says 6/30/10: set kick off plug from 5380'-5880', WOC, tagged cement at 5569', slid to 5710', and started directional drilling. |
| Cement at/near DV tool drillout - uncertain plug-like cement | 5374' tagged top | 5496' drilled-to depth | not stated | not stated | Completion operations say 7/26/10: tagged up at 5374', started drilling cement down to 5496', then began drilling DV tool. This is not explicitly called a plug, so it is retained separately from the 6/30/10 kickoff plug. |
| Flow-through frac plugs | 6854', 7454', 8054', 8654', 9250', 9854' | not stated | not stated | not stated | Completion continuation states "Flow thru plugs at 6854', 7454', 8054', 8654', 9250' and 9854'." No size, material, top/bottom interval, or cement details stated. |

### Perforations And Treatments

| Field | Value | Notes |
| --- | --- | --- |
| Top perforation depth | 6,384 ft | Completion summary gives perforations/producing interval as 6,384-10,434 ft Bone Spring; attached C-105 continuation lists 6,384 ft (9) as the shallowest perforation entry. |
| Bottom perforation depth | 10,434 ft | Completion summary gives perforations/producing interval as 6,384-10,434 ft Bone Spring; attached C-105 continuation lists 10,434 ft (9) as the deepest perforation entry. |
| Perforation list or intervals | Full attached perforation list: 10,434 ft (9); 10,284 ft (9); 10,134 ft (9); 9,984 ft (9); 9,834 ft (9); 9,684 ft (9); 9,534 ft (9); 9,384 ft (9); 9,234 ft (9); 9,084 ft (9); 8,934 ft (9); 8,734 ft (9); 8,634 ft (9); 8,484 ft (9); 8,334 ft (9); 8,184 ft (9); 8,034 ft (9); 7,884 ft (9); 7,734 ft (9); 7,584 ft (9); 7,434 ft (9); 7,284 ft (9); 7,134 ft (9); 6,984 ft (9); 6,834 ft (9); 6,684 ft (9); 6,534 ft (9); 6,384 ft (9). | source records repeat the same perforations in dated operations by frac stage; source records is the structured attached perforation record. |
| Acid, frac, squeeze, or cement treatment intervals | 7/27/10 no interval stated: pickled tubing with 1,000 gal 15% NEFE HCL and spotted 1,500 gal 10% acetic acid; 9,984-10,434 ft: frac with 30# borate gel, 66,508 lb Ottawa 40/70, 73,044 lb Super LC 20/40, 38,655 lb into formation; 9,854 ft: spotted 1,500 gal 7-1/2% HCL acid; 9,384-9,834 ft: frac with 30# borate gel, 1,500 gal 7-1/2% HCL acid, 59,417 lb Ottawa 40/70, 120,000 lb Ottawa 20/40, 80,000 lb Super LC 20/40; 9,250 ft: spotted 1,500 gal 7-1/2% HCL acid; 8,734-9,234 ft: frac with 30# borate gel, 1,500 gal 7-1/2% HCL acid, 65,013 lb 40/70, 124,965 lb Ottawa 20/40, 78,743 lb Super LC 20/40; 8,654 ft: spotted 1,500 gal 7-1/2% HCL acid; 8,184-8,634 ft: frac with 30# borate gel, 1,500 gal 7-1/2% HCL acid, 64,803 lb Ottawa 40/70, 122,448 lb Ottawa 20/40, 81,814 lb Super LC 20/40; 8,054 ft: spotted 1,500 gal 7-1/2% HCL acid; 7,584-8,034 ft: frac with 30# borate gel, 1,500 gal 7-1/2% HCL acid, 62,996 lb Ottawa 40/70, 118,657 lb Ottawa 20/40, 81,550 lb Super LC 20/40; 7,454 ft: spotted 1,500 gal 7-1/2% HCL acid; 6,984-7,434 ft: frac with 30# borate gel, 1,500 gal 7-1/2% HCL acid, 62,528 lb Ottawa 40/70, 118,125 lb Ottawa 20/40, 82,525 lb Super LC 20/40; 6,854 ft: spotted 1,500 gal 7-1/2% HCL acid; 6,384-6,834 ft: frac with 30# borate gel, 1,500 gal 7-1/2% HCL acid, 23,248 lb Ottawa 40/70, 91,828 lb Ottawa 20/40, 71,106 lb Super LC 20/40. | source records is the structured treatment table; source records provide dated operation sequence and match the interval/material list. No squeeze interval or cement-treatment interval was found in this section's perforation/treatment records. |

### Directional And Lateral Details

| Field | Value | Notes |
| --- | --- | --- |
| Kickoff point | Original permit plan: approx. 6,483 ft after plugging back the pilot hole. Revised directional plan: approx. 5,647 ft / 5,647.54 ft MD. Actual operations: kick-off plug set 5,380-5,880 ft, cement tagged at 5,569 ft, slid to 5,710 ft and started directional drilling. | The 5,647 and 5,647.54 values are the same revised planned KOP rounded differently. The actual operation narrative does not state one exact KOP, so the tag/slide depths are preserved as operational evidence. |
| Directional drilling note | Original plan: drill pilot hole vertically to 8,500 ft, plug back with a 400-500 ft kick-off plug near 6,483 ft, then drill directionally at 12 degrees/100 ft with an 8-3/4 in hole to 7,233 ft MD / 6,960 ft TVD; continue to 11,375 ft MD at 6,960 ft TVD using either 6-1/8 in or 7-7/8 in hole depending on casing contingency. Revised plan: plug back/kick off near 5,647 ft, drill 8-3/4 in hole to 6,400 ft MD / 6,125 ft TVD, then reduce to 7-7/8 in to 10,200 ft MD / 6,125 ft TVD. Actual operations: after plugging/tagging, slid to 5,710 ft and started directional drilling; reached TD in 8-3/4 in hole at 10,495 ft. | Kept as original/revised/actual because later pages materially changed the target formation and directional plan, and the actual hole did not follow the 7-7/8 in reduced-hole detail. |
| Pilot hole diameter | 8-3/4 in actual pilot/production hole after intermediate casing drill-out to pilot-hole TD. | source records states production hole size would be 8-3/4 in from drill-out of intermediate casing to pilot-hole TD; source records reports reducing to 8-3/4 in after the 9-5/8 in casing; source records reports TD pilot hole to 8,500 ft. |
| Pilot hole total depth or true vertical depth | 8,500 ft pilot-hole TD; pilot-hole survey projection shows 8,496.69 ft TVD on the final straight projection. | Permit comments and actual operations agree on 8,500 ft pilot-hole TD. The survey projection is a TVD value, not a competing MD TD. |
| Lateral hole diameter | Original plan: 6-1/8 in if 7 in casing was set, otherwise 7-7/8 in to 11,375 ft MD. Revised plan: 7-7/8 in from 6,400 ft to 10,200 ft MD after 8-3/4 in build section. Actual final hole: 8-3/4 in to 10,495 ft with 5-1/2 in casing set at 10,490 ft. | The actual completion/casing records show 8-3/4 in hole for the final production interval, so the reduced 7-7/8 in revised-plan hole was not treated as final actual. |
| Lateral measured depth range | Original plan: about 7,233-11,375 ft MD after the 8-3/4 in build section. Revised plan: 6,400-10,200 ft MD, with directional-plan EOC at 6,397.53 ft MD and EOL at 10,200.07 ft MD. Actual: directional drilling started after sliding to 5,710 ft; near-horizontal survey interval begins by about 6,451 ft MD and continues to BHL/TD at 10,495 ft MD; completed producing interval is 6,384-10,434 ft. | Actual range is stated with both the operational directional start and the survey-based near-horizontal interval because the actual report does not label a single "lateral start" row. |
| Lateral true vertical depth range | Original plan: 6,960 ft TVD lateral. Revised plan: 6,125 ft TVD lateral. Actual survey: about 6,147.81 ft TVD at 6,451 ft MD to 6,124.09 ft TVD at 10,495 ft MD. | Revised plan and actual BHL TVD are close; original plan targeted a materially deeper lateral TVD. |
| Lateral direction or azimuth | Revised plan: westward, VS azimuth 270.00 degrees, target E/W -4,280 ft. Actual BHL survey: azimuth 269.19 degrees, E/W -4,541.61 ft, TVD 6,124.09 ft at 10,495 ft MD. | Direction is effectively west in both revised plan and actual survey. |
| Total depth | Original proposed TD: 11,375 ft MD. Revised planned TD: 10,200 ft MD / 10,200.07 ft EOL. Actual TD: 10,495 ft MD. | Final actual TD is supported by the operations narrative, C-104/C-105 completion forms, and final directional survey. |
| Plugged-back total depth | Actual PBTD: 10,440 ft. | source records reports tagging PBTD at 10,440 ft; source records report PBTD 10,440 ft on completion forms. |

### Formation Tops

| Formation Name | Top Depth | Notes |
| --- | --- | --- |
| Castille / Castile | MD/TVD 500.00 ft | Directional-plan table comment reads "Castille" on source records; duplicate plot/table on source records reads "Castile". Conflicts with C-105 top on source records. |
| TOS | MD/TVD 700.04 ft | Directional-plan abbreviation; likely top of salt based on nearby BOS and the C-105 Salt rows, but the source label is only "TOS". Duplicate on source records. |
| BOS | MD/TVD 2100.00 ft | Directional-plan abbreviation; likely base of salt based on nearby TOS and the C-105 Salt rows, but the source label is only "BOS". Duplicate on source records. |
| Bell Canyon | MD/TVD 2280.00 ft | Directional-plan table marker. Duplicate on source records plot/table. Conflicts with C-105 top on source records. |
| Cherry Canyon | MD/TVD 3050.01 ft | Directional-plan table marker. Duplicate on source records plot/table. Conflicts with C-105 top on source records. |
| Brushy Canyon | MD/TVD 4179.99 ft | Directional-plan table marker. Duplicate on source records plot/table; source records OCR lower plot misread this as "Brusley", but the page image supports Brushy. Conflicts with C-105 top on source records. |
| Brushy Canyon Marker | MD/TVD 5530.00 ft | Directional-plan marker rather than a formal formation top. Duplicate on source records plot/table. |
| Bone Springs | MD 5802.76 ft; TVD 5800.04 ft | Directional-plan table comment reads "Bone Springs"; source records plot/table repeats TVD 5800.04 ft. Conflicts with C-105 top on source records. |
| T. Salt | 734 ft | Formal C-105 "Indicate Formation Tops" table, Southeastern New Mexico section. Image verified. |
| B. Salt | 2117 ft | Formal C-105 "Indicate Formation Tops" table, Southeastern New Mexico section. Image verified. |
| T. Castile | 460 ft | Formal C-105 "Indicate Formation Tops" table, Southeastern New Mexico section. Image verified. |
| T. Bell Canyon | 2358 ft | Formal C-105 "Indicate Formation Tops" table, Southeastern New Mexico section. Image verified. |
| T. Cherry Canyon | 3174 ft | Formal C-105 "Indicate Formation Tops" table, Southeastern New Mexico section. Image verified. |
| T. Brushy Canyon | 4250 ft | Formal C-105 "Indicate Formation Tops" table, Southeastern New Mexico section. Image verified. |
| T. Bone Spring | 5828 ft | Formal C-105 "Indicate Formation Tops" table, Southeastern New Mexico section. Image verified. |

## Conflicts And Uncertain Data

### Well Identity

| Field | Value A | Value B | Notes |
| --- | --- | --- | --- |
| Operator | Yates Petroleum Corporation | EOG Y Resources, Inc.; EOG Resources Inc | Early APD, C-144, sundry, and C-105 completion forms list Yates. Later change-operator/C-129 material lists EOG variants, including explicit "Operator: EOG RESOURCES INC" on source records. This appears to be an operator succession rather than a simple OCR conflict. |
| Latitude and longitude | N 32.135547, W 104.170700 (NAD83; center of proposed design) | LAT 32.8.7.9146 N, LON 104.10.14.5000 W (survey reference/wellhead) | The values are close but not identical, and the labels differ. source records is an official source form coordinate for the design center; source records is a survey wellhead/reference coordinate. |
| Spud date | 2/1/2010 | Date Spudded field shows "RH 2/1/10" and "RT 6/18/10" | source records is the clearest actual spud report. source records's completion-report field carries two sublabels/dates; 6/18/10 was not used as the spud date. |
| Completion date | 9/20/2010, Date Completed (Ready to Produce) | 06/21/2010 and 06/28/2010, "Date Completed" on survey reports | The survey report dates are completion dates for survey deliverables/control reports, not the well's ready-to-produce completion date. They were treated as search false positives, not alternate well completion dates. |

### Elevations

| Field | Value A | Value B | Notes |
| --- | --- | --- | --- |
| Ground level / GR elevation | 3172 ft / `3172'GR` / `3172.00' Ground To MSL` | 3170' | source records lacks a datum suffix but is in the same C-103 elevation field. Treat as an unresolved conflict rather than a duplicate. |
| Kelly bushing / RKB absolute elevation | 3191'KB | `WELL @ 3190.50ft (Original Well Elev)` / RKB elevation 3190.50 | Completion report KB is 0.5 ft higher than the directional-plan RKB/original-well-elevation reference. |
| Kelly bushing / RKB absolute elevation | 3190.50 ft | 3190.00 ft, or 18.00' Kelly Bushing To Ground plus 3172.00' Ground To MSL | Survey/tie-in/magnetic-calculation sources imply or state 3190.00 ft, 0.5 ft lower than the 3190.50 ft RKB reference and 1 ft lower than the completion-report 3191'KB. |

### Operation Timeline

| Field | Value A | Value B | Notes |
| --- | --- | --- | --- |
| TD reached date OCR uncertainty | OCR text extraction showed C-105 Date T.D. Reached as 7/1/10 | rendered image shows 7/11/10; source records sundry also says 7/11/10 | Resolved by page image authority; use 7/11/10. |
| Spud date terminology | Spudded 12-1/4" hole on 2/1/10; C-105 lists RH 2/1/10 | C-105 also lists RT 6/18/10 | Not treated as an unresolved conflict. The completion forms distinguish rat-hole/original spud from rotary/resumed drilling. |
| Proposed versus actual TD and production casing | Original APD/proposed plan used 11,375' TD and production casing to 11,375' | Actual final TD was 10,495' and 5-1/2" casing was set at 10,490' | Proposed plan was superseded; preserve as historical/proposed only. |
| Revised plan versus actual kickoff/TD | Revised June plan proposed kickoff near 5,647', lateral TD 10,200' MD, and 5-1/2" casing to 10,200' | Actual operations tagged cement at 5,569', slid to 5,710' and started directional drilling, reached TD 10,495', and set casing at 10,490' | Actual reports should control final configuration. |

### Hole Sections

| Field | Value A | Value B | Notes |
| --- | --- | --- | --- |
| 0'-40' upper-hole diameter | 12-1/4" hole reported from spud/new-hole sequence to TD 40' | 26" hole for 20" conductor set at 40' | The 12-1/4" reports appear tied to the early RH spud/new-hole sequence, while completion records assign the conductor interval to a 26" hole. Keep both because they may describe different early-work holes or a reporting inconsistency. |
| surface-hole setting depth | Proposed 17.5" hole to 400' | Actual 17-1/2" hole to 470' | Planned surface casing depth changed before/as drilled. Actual records consistently report 470'. |
| intermediate-hole setting depth | Proposed 12.25" hole to 2,400' | Actual 12-1/4" hole to 2,232' | Planned intermediate casing depth changed before/as drilled. Actual records consistently report 2,232'. |
| production-hole size and TD | Original C-101 proposed 7.875" production hole to 11,375' | Actual completion records show 8-3/4" hole with TD 10,495' and 5-1/2" casing set at 10,490' | Original permit program was superseded by revised drilling plan and actual drilling records. |
| original plan vs revised plan lateral program | Original plan: 8-3/4" to 7,233' MD, then 6-1/8" or 7-7/8" to 11,375' MD | Revised plan: 8-3/4" to 6,400' MD, then 6-1/8" or 7-7/8" to 10,200' MD | Revision lowered the target TVD/MD and moved the casing/hole-size change point from 7,233' to 6,400'. |
| revised plan vs actual lateral diameter | Revised plan reduces after 6,400' MD to 7-7/8" or contingency 6-1/8" through 10,200' MD | Actual records report reaching TD 8-3/4" hole to 10,495' | Final completion appears to have stayed 8-3/4" to TD rather than using the planned size reduction. |
| kickoff/start of directional drilling depth | Revised plan KOP about 5,647' | Actual report: tagged cement at 5,569', slid to 5,710', and started directional drilling | Treat 5,710' as the actual directional-drilling start for the final lateral row; keep the planned 5,647' KOP as a plan value. |

### Casing And Tubing Strings

| Field | Value A | Value B | Notes |
| --- | --- | --- | --- |
| Surface casing setting depth | Original proposed 13.375", 48 lb/ft at 400' | Actual 13-3/8", 48# H-40 ST&C at 470' | Not an unresolved conflict: the later actual casing report supersedes the original proposal. source records repeats the actual 470' depth. |
| Intermediate casing setting depth | Original proposed 9.625", 36 lb/ft at 2,400' | Actual 9-5/8", 36# J-55 LT&C at 2,232' | Not an unresolved conflict: the later actual casing report supersedes the original proposal. source records repeats the actual 2,232' depth. |
| Production casing setting depth | Original proposed 5.5", 17 lb/ft at 11,375' | Actual 5-1/2", 17# L-80 LT&C 8rd at 10,490' | Actual production casing differs from both the original proposal and the revised 10,200' design on source records. source records repeats the actual 10,490' depth. |
| Revised production casing grade plan versus actual | Revised plan: 5.5", 17#/ft P-110 from 0-6,400 ft and L-80 from 6,400-10,200 ft | Actual report: 5-1/2", 17# L-80 LT&C 8rd casing at 10,490' | Treat as plan-versus-actual change, not a same-time data conflict. |
| Tubing record OCR alignment | Rendered C-105 table shows 2-7/8" tubing, depth set 5,600', packer set 5,600' | Narrative states 2-7/8" 6.5# L-80 tubing at 5,600' with AS-1 packer and 2.25" S-lok in place | No value conflict found. The extracted Markdown for source records shifted the tubing row, so the rendered image was used as authority. |

### Downhole Items And Reference Depths

| Field | Value A | Value B | Notes |
| --- | --- | --- | --- |
| TD / planned depth revision | Initial APD proposed TD and production casing setting depth: 11,375' MD. | Revised planned TD / EOL: 10,200' MD, with directional plan EOL at 10,200.07' MD / 6,125.01' TVD. | The revised directional plan supersedes the initial APD design after a target formation change. |
| Actual TD versus revised plan | Revised planned TD / EOL: 10,200' MD. | Actual TD: 10,495'. | Final reported TD is 295' deeper than the revised planned TD. |
| KOP / kick-off depth | Initial planned kick-off plug at approx. 6,483'. | Revised KOP approx. 5,647'; directional plan KOP 5,647.54' MD / 5,647.54' TVD. | source records rendered image supports 5,647.54'. Actual kick-off operations on source records use plug/tag references around 5,380'-5,880', 5,569', and 5,710'. |
| Revised KOP versus actual kick-off operations | Revised KOP: 5,647.54' MD / TVD. | Actual kick-off plug 5,380'-5,880'; tagged cement 5,569'; slid to 5,710' and started directional drilling. | These are related but not identical reference types; preserve all because they may affect diagram placement. |
| Surface casing shoe | APD proposed 13-3/8" casing at 400'. | Actual 13-3/8" casing at 470'. | Actual surface shoe is 70' deeper than proposed. |
| Intermediate casing shoe | APD proposed 9-5/8" casing at 2,400'. | Actual 9-5/8" casing at 2,232'. | Actual intermediate shoe is 168' shallower than proposed. |
| Production casing shoe | APD proposed 5-1/2" casing at 11,375'. | Actual 5-1/2" casing at 10,490'. | Revised plan targeted 10,200'; actual casing was set 290' deeper than revised plan and 885' shallower than the initial APD. |
| Contingency 7" casing shoe | Initial contingency 7" casing at 7,233' MD / 6,960' TVD. | Revised contingency 7" casing at 6,400' MD / 6,125' TVD. | This is a plan revision, not an actual-versus-actual conflict. |
| DV tool / cut-pull reference | Initial contingency DV/cut-pull reference around 6,400'. | Revised DV/cut-pull reference around 5,600'; actual DV cleanup/drill-out at 5,496'. | The actual DV cleanup reference is about 104' above the revised planned DV depth and about 904' above the initial contingency reference. |
| TOC | Initial APD production casing estimated TOC: 1,900'. | Actual production casing estimated TOC: 1,700'. | Revised contingency plan also has TOC 5,600' for an alternate 4-1/2" contingency string; that value belongs to a different scenario. |
| Directional survey depth coverage | Completion and operations report final TD: 10,495'. | Last deviation survey station visible in allowed pages: 10,414' MD. | The survey table stops short of the final completion TD in the allowed pages. This is a coverage uncertainty, not a replacement TD. |

### Cement Jobs

| Field | Value A | Value B | Notes |
| --- | --- | --- | --- |
| Surface casing cement program | Proposed: 425 sx on 13-3/8 in casing set at 400 ft, TOC 0 ft | Actual: 365 sx on 13-3/8 in casing set at 470 ft, circulated 120 sx to pit | Actual report supersedes proposed APD for final wellbore. |
| Intermediate casing cement program | Proposed: 825 sx on 9-5/8 in casing set at 2,400 ft, TOC 0 ft | Actual: 760 sx on 9-5/8 in casing set at 2,232 ft, circulated 140 sx to pit | Actual report supersedes proposed APD for final wellbore. |
| Production casing cement program | Proposed APD: 2,075 sx on 5-1/2 in casing set at 11,375 ft, estimated TOC 1,900 ft | Actual: 1,380 sx on 5-1/2 in casing set at 10,490 ft, estimated TOC 1,700 ft | The well was drilled shorter than the original proposed MD and cemented with two actual stages. |
| 7 in contingency casing cement | Original contingency: 760 sx Lite crete plus 125 sx PVL, TOC surface, bottom 7,233 ft MD | Revised contingency: 450 sx Lite crete plus 125 sx PVL, TOC 1,900 ft, bottom 6,400 ft MD | This appears to be a plan revision, not an actual run string. |
| 4-1/2 in contingency production casing cement | Original contingency: 675 sx PVL, TOC 6,400 ft, bottom 11,375 ft MD | Revised contingency: 625 sx PVL, TOC 5,600 ft, bottom 10,200 ft MD | Image verification was needed for source records because combined markdown missed the 675 sx line. This appears to be a plan revision, not an actual run string. |
| Kickoff plug top depth | Set interval top reported as 5,380 ft | Tagged cement at 5,569 ft | Treat 5,380 ft to 5,880 ft as the set interval and 5,569 ft as the post-WOC tag/top-of-cement observation. |
| Stage 1 production-casing top depth | Stage 1 circulated cement off DV tool, but source records does not state the DV tool depth | DV tool cleaned up at 5,496 ft | Top depth for stage 1 is inferred from the later DV-tool cleanup depth. |

### Plugs

| Field | Value A | Value B | Notes |
| --- | --- | --- | --- |
| Kickoff/plugback location | approx. 6483' with 400'-500' kick off plug | approx. 5647' plugback/KOP depth | Original permit comments and revised plan differ. The actual kickoff plug later appears as 5380'-5880' with tag at 5569' and slide to 5710' on source records. |
| Kickoff plug execution reference | 5380'-5880' kick off plug, tagged cement at 5569', slide to 5710' | 5374' tagged top and cement drilled down to 5496' near DV tool | These are likely different operational contexts: source records is the pre-directional kickoff plug; source records is later completion drillout around the DV tool. Kept separate because the later cement is not explicitly called a plug. |
| Flow-through frac plugs | Plug depths listed at 6854', 7454', 8054', 8654', 9250', 9854' | Top/bottom intervals, material, and setting method not stated | The source gives single depths only. Treated as point-depth flow-through plugs, not cement plugs. |

### Perforations And Treatments

| Field | Value A | Value B | Notes |
| --- | --- | --- | --- |
| Acid/pickle operation interval | 7/27/10 tubing pickle with 1,000 gal 15% NEFE HCL and 1,500 gal 10% acetic acid spotted | No depth interval stated for this acid operation | Kept as a no-interval treatment operation. The same note says the DV tool was cleaned up at 5,496 ft, but it does not explicitly make 5,496 ft the acid placement interval. |

### Directional And Lateral Details

| Field | Value A | Value B | Notes |
| --- | --- | --- | --- |
| Kickoff point | Original permit plan: approx. 6,483 ft | Revised directional plan: approx. 5,647 ft / 5,647.54 ft MD | This is a true plan revision, not a duplicate. Actual operations give a kick-off plug interval 5,380-5,880 ft, cement tag 5,569 ft, and slide-to/start-directional depth 5,710 ft on source records. |
| Actual kickoff marker | Revised planned KOP: 5,647.54 ft MD | Actual operational markers: tagged cement at 5,569 ft; slid to 5,710 ft and started directional drilling | The actual narrative does not name one exact KOP, so treating 5,569 ft or 5,710 ft as "the" actual KOP would be interpretive. |
| Total depth | Original proposed TD: 11,375 ft MD | Revised planned TD: 10,200 ft MD / 10,200.07 ft EOL | The revised plan superseded the original permit depth target. |
| Total depth | Revised planned TD: 10,200 ft MD | Actual TD: 10,495 ft MD | Actual well was drilled 295 ft beyond the revised planned TD. |
| Lateral true vertical depth | Original planned lateral TVD: 6,960 ft | Revised planned lateral TVD: 6,125 ft | Actual BHL survey TVD was 6,124.09 ft, aligning with the revised target rather than the original. |
| Lateral/final hole diameter | Revised plan after 6,400 ft MD: reduce to 7-7/8 in; original contingency also mentioned 6-1/8 in | Actual final production hole: 8-3/4 in to 10,495 ft | Completion and casing records show the actual hole did not follow the reduced 7-7/8 in or 6-1/8 in planned alternatives. |

### Formation Tops

| Field | Value A | Value B | Notes |
| --- | --- | --- | --- |
| Castile top | MD/TVD 500.00 ft; source spelling Castille/Castile | 460 ft | Directional-plan marker conflicts with formal C-105 table. source records spelling appears "Castille"; source records and source records use "Castile". |
| Salt top | MD/TVD 700.04 ft, labeled TOS | 734 ft, labeled T. Salt | TOS expansion is inferred from abbreviation and nearby salt/base-salt context; keep source label as TOS. |
| Base Salt top | MD/TVD 2100.00 ft, labeled BOS | 2117 ft, labeled B. Salt | BOS expansion is inferred from abbreviation and nearby salt/top-salt context; keep source label as BOS. |
| Bell Canyon top | MD/TVD 2280.00 ft | 2358 ft | Directional-plan marker conflicts with formal C-105 table. |
| Cherry Canyon top | MD/TVD 3050.01 ft | 3174 ft | Directional-plan marker conflicts with formal C-105 table. |
| Brushy Canyon top | MD/TVD 4179.99 ft | 4250 ft | Directional-plan marker conflicts with formal C-105 table; source records OCR lower plot misread Brushy as "Brusley", corrected by page image/table. |
| Bone Spring top | MD 5802.76 ft; TVD 5800.04 ft, labeled Bone Springs | 5828 ft, labeled T. Bone Spring | Directional-plan table gives separate MD/TVD; source records plot labels 5800.04 ft on the TVD chart. |
| Brushy Canyon Marker | MD/TVD 5530.00 ft | n/a | Uncertain classification: this is a directional-plan marker, not a formal formation top. Retained because it appears in the same marker list as formation tops. |
