# spektrafilm-Table validation — 2026-11-09

Validated on Windows with an isolated `.venv` using Python 3.13.13, Qt/PySide
6.12.0 and napari 0.6.6. Installation used the upstream dependency constraints.

## Automated checks

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
.venv/Scripts/python.exe -m pytest tests/gui tests/test_topology.py tests/test_scan_progress.py tests/test_runtime_api.py tests/test_raw_smoke.py tests/test_raw_file_processor.py tests/test_pipeline_smoke.py -q --disable-warnings
```

**206 passed.** Coverage includes catalog tests for recursive discovery,
duplicate imports, Unicode/space-containing paths, persistence, relocation
conflicts, non-destructive removal, thumbnail caching, corrupt files, independent
photo edits, asynchronous load races and stale simulation results. New coverage
also checks v1 catalog migration, shared folder filtering, module restoration,
import selection/cancel/error paths, embedded RAW thumbnails, preset directory
fallback and successful-operation-only location memory. Filmstrip layout/size
persistence and SCAN callbacks are tested; enabling callbacks produces identical
pixels, and a failed step does not report completion.

The pre-existing layout test used an outdated layout/widget stub. Its stub now
accepts the stretch argument and models the existing action bar/container; no
production layout or simulation code was changed for that fix.

`compileall` and `git diff --check` also passed.

## Desktop end-to-end checks

- Created and displayed the actual Qt/napari application, library and filmstrip.
- Imported JPEG, PNG and float TIFF inputs; inspected generated thumbnails.
- Loaded a JPEG, ran the original film simulation and exported a readable JPEG.
- Imported a real Kodak DC50 KDC RAW (768 × 512), generated a thumbnail, decoded
  it using the original RAW processor, simulated a 128-pixel preview and exported
  a readable 128 × 85 JPEG through the original save action.
- Closed and recreated the actual application with the same catalog; two photos
  independently restored their different crop centers and rotation states.
- Inspected editor screenshots after the upstream paper-development animation
  completed. The animation initially displays a bright frame; the final image
  and exported pixels display normally.
- Verified the installed `spektrafilm-table.exe` launcher exists.
- Exercised the source-folder preview dialog, checked imports, shared folder tree,
  Library / Develop navigation, and real GUI-parameter save/load operations.
- Inspected the full-width filmstrip at 240 pixels height and 180-pixel thumbnails.
- Ran an actual SCAN with progress updates from preparation through all six
  processing stages and display preparation; verified the final Complete status.
- Inspected a real KDC RAW in the new import-preview window without importing it.

Local scripts, screenshots, exports, test catalogs and the external RAW fixture
are under ignored `.temp/`; they are not part of the distributed source. The RAW
fixture came from rawpy's test directory, whose README attributes it to
rawsamples.ch under CC BY-NC-SA 4.0. It is used for local verification only.

## Known upstream baseline failures

`tests/test_regression_baselines.py` reports **2 passed, 3 failed**:

- `print_rgb_portra_endura_gray_ramp16`
- `print_rgb_fuji_crystal_gray_ramp16`
- `print_rgb_portra_endura_green_patch8`

The same three numerical snapshot mismatches were reproduced from an unmodified
`git archive HEAD` copy of upstream commit `3bb2c2d`, using this same environment.
The cause has not been diagnosed; this is not a claim that all upstream numerical
regressions pass. Snapshot data, tolerances, film profiles and the physical
simulation algorithms were left unchanged. The optional progress observer only
adds notifications around existing stages; it does not modify their calculations.

Real RAW verification covers one camera sample, not every camera/RAW variant.
Large-library stress tests and production packaging are outside this first pass.


## 2026-11-12 — Import and live white balance validation

- `python -m pytest tests/gui -q`: **178 passed, 1 skipped** (optional real CUDA test).
- Added multi-folder selection/restoration, recursive discovery, disabled thumbnail
  decoding, last photo-directory, cached live sliders, preview/full-size consistency,
  original-pixel preservation, and duplicate-SCAN cancel/continue tests.
- Compared encoded-space white balance against the original RAW adaptation/tint
  operations; also compared the real Kodak DC50 KDC result at 4200 K / tint 1.1.
- Real Qt/napari window smoke check completed 1/8 RAW preview after slider movement,
  then completed full SCAN of a small RGB image, persisted its successful signature,
  and verified declining the duplicate prompt starts no worker.
- Inspected MAIN controls and the Preview size selector in a rendered window capture.
  Local script and capture: `.temp/live-controls-20261112/` (ignored test artifacts).
- RAW coverage remains one KDC sample; no claim of fixed-rate interactive rendering
  on all machines or camera formats. Existing corrupt-image tests emit expected
  OpenImageIO decoder diagnostics.
