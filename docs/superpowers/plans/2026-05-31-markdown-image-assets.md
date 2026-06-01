# Markdown Image Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve PaddleOCR-generated image crops so per-page Markdown and root-level `combined.md` render image blocks correctly.

**Architecture:** PaddleOCR writes Markdown image references relative to the Markdown file, usually under `imgs/`. The page bundle saver should copy that generated asset directory out of its temporary workspace before cleanup, the combined-output writer should rewrite page-local image links so they are relative to the run directory, and resume completeness should treat pages with missing referenced image assets as incomplete.

**Tech Stack:** Python 3.10, pathlib/shutil, pytest, existing `pdf_extract` package helpers.

---

### Task 1: Preserve Page Markdown Image Assets

**Files:**
- Modify: `tests/test_outputs.py`
- Modify: `pdf_extract/paddle_output.py`

- [ ] **Step 1: Write the failing test**

Add a fake PaddleOCR result that writes `output.md` with an HTML image reference and creates `imgs/picture.jpg` in the current working directory. Assert that `save_page_result_bundle()` copies the `imgs` directory into the final page bundle.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `uv run pytest tests/test_outputs.py::test_save_page_result_bundle_contains_markdown_image_assets -q`

Expected: FAIL because `page_dir/imgs/picture.jpg` is missing.

- [ ] **Step 3: Implement the minimal code**

Copy `tmp_dir / "imgs"` to `page_dir / "imgs"` in `save_page_result_bundle()` using the existing `_replace_tree_if_present()` helper, matching how `files/` side effects are already handled.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `uv run pytest tests/test_outputs.py::test_save_page_result_bundle_contains_markdown_image_assets -q`

Expected: PASS.

### Task 2: Rewrite Image Links In Combined Markdown

**Files:**
- Modify: `tests/test_outputs.py`
- Create: `pdf_extract/markdown_assets.py`
- Modify: `pdf_extract/combine.py`

- [ ] **Step 1: Write the failing test**

Add a combined-output test where page Markdown contains both `<img src="imgs/picture.jpg">` and `![](imgs/diagram.png)`. Assert that `combined.md` contains `pages/page_0001/imgs/picture.jpg` and `pages/page_0001/imgs/diagram.png`.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `uv run pytest tests/test_outputs.py::test_write_combined_outputs_rewrites_page_local_image_paths -q`

Expected: FAIL because links remain `imgs/...`.

- [ ] **Step 3: Implement the minimal code**

Add a small helper in `pdf_extract/combine.py` that rewrites Markdown image links and HTML `src` attributes whose values start with `imgs/` to `pages/page_NNNN/imgs/...` before appending page Markdown to `combined.md`.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `uv run pytest tests/test_outputs.py::test_write_combined_outputs_rewrites_page_local_image_paths -q`

Expected: PASS.

### Task 3: Make Resume Detect Missing Markdown Assets

**Files:**
- Modify: `tests/test_manifest.py`
- Modify: `pdf_extract/manifest.py`
- Use: `pdf_extract/markdown_assets.py`

- [ ] **Step 1: Write the failing test**

Add a manifest test where the core bundle files exist and `output.md` references both an HTML image and Markdown image under `imgs/`, but one referenced file is missing. Assert `is_page_complete()` is false until every referenced asset exists.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `uv run pytest tests/test_manifest.py::test_is_page_complete_requires_referenced_markdown_image_assets -q`

Expected: FAIL because the existing completeness check ignores Markdown image references.

- [ ] **Step 3: Implement the minimal code**

Move the page-local image reference parsing into `pdf_extract/markdown_assets.py`, reuse it from `combine.py`, and call it from `manifest.py` after the normal core-artifact checks pass.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `uv run pytest tests/test_manifest.py::test_is_page_complete_requires_referenced_markdown_image_assets -q`

Expected: PASS.

### Task 4: Regression Verification

**Files:**
- Verify: full repository tests

- [ ] **Step 1: Run output tests**

Run: `uv run pytest tests/test_outputs.py -q`

Expected: all output tests pass.

- [ ] **Step 2: Run the full suite**

Run: `uv run pytest -q`

Expected: all tests pass.
