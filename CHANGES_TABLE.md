# spektrafilm-Table changes

## 2026-11-08 — Initial photo library

Based on Andrea Volpato's spektrafilm, upstream commit `3bb2c2d`.

- Added a separate Table desktop entry point, library grid and editing filmstrip.
- Added a local SQLite catalog, background thumbnails and image loading.
- Added per-photo parameter/rotation persistence and stale simulation protection.
- Added import, filename search, missing-file relocation and catalog-only removal.
- Preserved the upstream runtime, package names, original entry points, author
  credits, LICENSE, CITATION.cff and SPEKTRAFILM_LICENSE.txt.

Table additions are GPLv3. No film profiles or LUT data have been modified.

## 2026-11-08 — Workspace and import improvements

- Replaced hierarchical navigation with persistent Library / Develop tabs.
- Added shared folder navigation, per-folder recent-photo restoration, missing
  folder indicators and automatic v1-to-v2 catalog migration.
- Added cancellable import previews with source browsing, subfolder selection,
  per-photo checkboxes and duplicate detection before catalog insertion.
- Added an optional presets directory and a Table-specific shared save/load
  location, updated only after a successful operation.
- Added workspace, migration, preview and preset-path regression tests.

## 2026-11-09 — Adjustable filmstrip and scan progress

- Moved the filmstrip below both workspace columns, with a draggable vertical
  splitter and a persistent 80–256 pixel thumbnail-size slider.
- Added SCAN stage/step progress and elapsed time, including failure and stale
  result handling. Runtime process APIs accept an optional `on_progress` callback;
  existing calls retain their behavior and numerical processing is unchanged.
- Letterboxed cached thumbnail icons to preserve photo proportions across Qt styles.


## 2026-11-12 — CPU / NVIDIA CUDA execution

- Added an execution backend protocol and explicit injection into the runtime stages.
- Added optional float64 CUDA acceleration for camera/enlarger diffusion and CAM16-UCS output compression, with lazy capability probing and visible CPU fallback.
- Added the Table Compute selector, persistent application preference, background initialization, backend-aware stale-result checks and actual execution status.
- Added optional CUDA component-wheel dependencies, numerical/failure/UI regression tests and a production-backend benchmark script.
- Retained CPU-only startup and existing photo/preset formats. Other GPU platforms remain future backends.
- See GPU_IMPLEMENTATION.md for scope, validation and limitations.


## 2026-11-12 — Import selection and live editing

- Folder import supports Ctrl/Shift multi-selection and remembers selected folders,
  recursion and thumbnail-preview preferences. Photo import remembers its directory.
- Import thumbnail decoding can be disabled while retaining the selectable file list.
- Table MAIN has a separate White balance section with temperature/tint sliders.
  RAW camera-balanced and daylight bases are decoded once per open; subsequent edits
  operate on cached previews in linear light, without reprocessing the RAW file.
  The same adjustment is applied to full-resolution SCAN input. Original files and
  the existing per-photo/preset white-balance fields are preserved.
- Preview size offers Auto, 1/1, 1/2, 1/4, 1/8 and 1/16 and persists independently
  of photo edits. SCAN remains full resolution.
- Successful SCAN signatures persist in the catalog. Repeating a photo/source-file,
  rotation, processing-parameter and backend combination asks before recalculating,
  defaulting to No; preview size and auto-preview do not affect the signature.
- Initial RAW loading retains two decoded bases and therefore uses more time/memory;
  slider updates avoid RAW I/O and full-resolution resampling. Film simulation remains
  asynchronous, so its refresh speed depends on preview size and selected effects.

## Develop tools (2026-11-13)

- RAW opens using camera/as-shot white balance. Temperature and tint display camera-derived equivalent values fitted to the cached camera/daylight decodes; these are approximate editor values, not guaranteed to match a vendor's EXIF Kelvin display. Selecting as_shot restores these values. Custom edits remain per photo.
- MAIN > White balance > Eyedropper temporarily shows the input image. Click a neutral midtone area to calibrate; click the button again to cancel. A 5x5 source patch is sampled in the input color space; black/clipped samples are rejected.
- Develop's left sidebar shows an RGB histogram of the white-balanced input preview, above Folders.
- Adjustments continue to autosave into the application SQLite catalog, including on photo switches and close. No sidecars are written next to originals.
- Settings > Cache offers directory selection, thumbnail disk usage, an automatic size limit (default 1024 MiB, checked each minute while idle), and Clear cache now. Only generated thumbnail files are removed. Changing directory does not move or erase the old cache. The photo database stays in the application data directory.
- Config schema_version 2 separates white_balance from load_raw (lens correction). Legacy flat/nested configs remain readable; subsequent saves use v2.
- Filmstrip supports Windows Ctrl toggle and Shift range selection. Right-click a thumbnail to copy its parameters; Paste parameters to selected photos applies to the selected group. Rotation and display preferences stay local.

Validation: 191 GUI/RAW processor tests passed, 1 optional CUDA test skipped. A native Windows Qt startup/import/Develop screenshot smoke check passed with isolated catalog/settings. White-balance fitting was checked with synthetic known transforms; no real RAW camera file was available for this update's validation.

## Develop fixes and Chinese interface (2026-11-13)

- Eyedropper uses its own temporary, correctly scaled RGB display layer with explicit 0–1 contrast limits. Queued preview refreshes and simulation completions keep it visible. Cancel/sample restores prior layer visibility and selection; rotation cancels sampling.
- Preview size now appears immediately after reset view in the image footer, with the same original resolution choices and persistence.
- Settings > Language / 设置 > 语言 switches between English and 简体中文 immediately and remembers the selection. A new installation defaults to Chinese. Main panels, parameter labels/tooltips, white-balance modes, common dialogs and cache/import controls are translated. Profile identifiers, color-space names and algorithm identifiers retain their stable technical names.
- Enum editors now store internal values separately from translated display text, so language changes do not alter image parameters or config files.
- Validation: 193 GUI/RAW processor tests passed; 1 optional CUDA test skipped. Native Windows smoke verified visible picker pixels before/after preview refresh, successful grey sampling, footer placement, and Chinese/English switching. Reproduce with `python scripts/smoke_develop_ui.py` using native Qt; it uses temporary settings/catalog and writes screenshots to a temporary folder.
