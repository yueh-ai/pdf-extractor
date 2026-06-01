<claude-mem-context>
# Memory Context

# [pdf-extract] recent context, 2026-05-31 8:47pm CDT

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (20,334t read) | 763,724t work | 97% savings

### May 31, 2026
S95 PDF extraction project - image saving paths for correct markdown rendering (May 31 at 4:51 PM)
S94 PDF extraction project - discussing image saving paths for correct markdown rendering (May 31 at 4:51 PM)
1764 5:23p ⚖️ Migration Implemented as One-Off tmp/ Script Instead of Reusable CLI
1765 5:24p 🔵 System Uses uv run python, Not Bare python Command
1766 " 🟣 Final State: 6 Key Tests Pass; run_layout.py and CLI Run-Mode Feature Verified
1767 " 🟣 pdf-extract Run-Mode Feature: Final Clean State Verified — 31/31 Tests, No Stale References
1768 7:16p ⚖️ Reconcile Pipeline Handoff Documentation Planned
1769 7:18p 🔵 Resumable PDF Extraction Pipeline: PaddleOCR-VL + MLX Handoff Document
1770 " 🔵 pdf-extract Project Already Has Working Implementation
1771 " 🔵 Existing Planning Docs in docs/superpowers/
S96 Prepare a handoff/plan document for the pdf-extract project, grounded in the current repo state and OpenAI structured-output assumptions, to be saved under docs/superpowers/plans/ (May 31 at 7:18 PM)
1772 7:19p ⚖️ RECONCILIATION_HANDOFF.md Created: Union/Small Reconciliation Pipeline Design
1774 7:21p 🔵 Reconciliation Pipeline Design Handoff Document Read
1775 " 🔵 pdf-extract Codebase Architecture Fully Mapped
1776 7:22p 🔵 Real Dual-Mode Extraction Runs Confirmed Complete for Full_30015375000000
1777 " 🔵 Concrete Union vs Small Mode Diff Examined on Page 22
1778 " 🔵 Root Cause of Union vs Small Mode Differences Traced to Layout Block Merging in res.json
1779 7:23p 🔵 Statistical Analysis of Union vs Small Mode Differences Across All 155 Pages
1780 7:28p ⚖️ Reconciliation Design Decision: Skip OpenAI for Identical/Small Markdown Pages
1781 7:32p ⚖️ Reconciliation Prompt Design: Image + Candidate Markdown Only, No Layout Visualizations in v1
1782 7:35p 🔵 Image Diff Analysis Between Union and Small Extraction Modes on Full_30015375000000
1783 7:42p ⚖️ Reconciliation LLM Contract: No Winner Concept; Human-Review Signal is Non-Blocking in v1
1784 7:49p 🔵 PDF Q&A Capability Assessment from Extracted Artifacts
1785 7:50p 🔵 PDF Q&A Capability Planning for pdf-extract Run Artifacts
1786 " 🔵 pdf-extract Run Artifact Structure Confirmed
1787 7:51p 🔵 PDF Content Identified: New Mexico Oil Well Drilling Permit for Yates Petroleum
1788 " 🔵 Extraction Run Quality: small=100% success, union=18 failed attempts but all pages recovered
1789 7:52p 🔵 Full PDF Document Scope: Multi-form Oil Well Drilling & Completion Package with Rich Q&A-Ready Data
1790 " 🔵 small and union Variants Produce Identical per-page output.md; Key Pages Mapped to Drilling Events
1791 8:03p 🔵 Directional Survey and KOP/DV Tool Data Fully Extractable from combined.md via Keyword Search
1792 " 🔵 Per-page output.md Files Confirm Granular Q&A Retrieval; Minor Content Difference Found Between small and union for Page 23
1793 8:08p 🔵 Formation Tops Extracted for Well API 30-015-37500 (Jericho BKJ State Com #2H)
1794 8:09p 🔵 Wellbore Details and Horizontal Target (Avalon Shale) for Jericho BKJ State Com #2H
1795 8:14p 🔵 Well Diagram Data Requirements Identified from PDF Page 153
1796 " 🔵 PDF Extraction Run Directory Structure Confirmed for Full_30015375000000
1797 8:15p 🔵 Well Diagram Page 153 Data Fields Fully Extracted from Full_30015375000000
1798 8:23p 🟣 Wellbore Diagram Extraction Instruction Template Created
1799 " 🔵 instruction.md Also Exists at Project Root
1800 8:30p 🔵 Oil & Gas Tubing String Specification Query
1801 8:31p 🔵 Tubing String Data Found in Well P&A Report PDF Extract
1802 8:34p 🔵 pdf-extract Project: Wellbore Diagram Extraction Schema Includes Plugs Section
1803 " ✅ instruction.md Updated: Source Citation and "Not Found" Reporting Added to Extraction Schema
1804 8:35p 🔵 Run-Specific instruction.md Does Not Exist for Full_30015375000000
1805 " ✅ instruction.md Source Reference Fields Verified in Place at Expected Line Numbers
1806 " ✅ instruction.md Source References Extended to All Remaining Schema Sections
1807 8:39p 🟣 New Engineer-Readable Worksheet Created: instruction_engineer_readable.md
1808 " 🔵 instruction.md and instruction_engineer_readable.md Are Untracked in Git
1809 8:45p ✅ Removed "Visual Position" and similar fields from instruction_engineer_readable.md
1810 " 🔵 instruction_engineer_readable.md structure identified with "Visual Position" column locations
1811 " 🔵 instruction_engineer_readable.md is untracked in git
1812 " ✅ Removed "Visual Position" column from three tables in instruction_engineer_readable.md
1813 8:46p ✅ Removed "Visual Symbol" column from Tools And Markers table in instruction_engineer_readable.md
1814 8:47p ✅ Removed "Label" identifier columns from four tables and updated "label" wording throughout instruction_engineer_readable.md

Access 764k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>