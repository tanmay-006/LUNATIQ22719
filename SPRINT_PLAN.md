# LunaReg: 5-Day Sprint to Working Prototype

**Team:** 3-5 people · **Deadline:** Sept 30, 2026 (5 days) · **Goal:** End-to-end registration on verified OHRC/NAC pair with PPT

---

## TL;DR

Build a minimal but complete registration pipeline: ingest OHRC + NAC → project to common grid → match features (LoFTR + SIFT fallback) → measure accuracy. Skip jitter model, relighting, and IIRS. Reuse ISIS tools for projection. One parallelizable workstream per person.

**Success Criteria (MVP):**
- ✅ Registered GeoTIFF output (source overlaid on reference)
- ✅ Match point CSV (500+ inliers, >10% coverage)
- ✅ RMSE / median error on verified pair < 5 pixels
- ✅ Code runs in <5 min per pair
- ✅ Repeatable on CLI: `python -m lunar_isis_gui.register source.cub reference.cub`
- ✅ Demo plot showing original → registered → residuals

---

## 5-Day Workstreams (Assign 1 person per workstream)

### **Workstream A: Data Pipeline & PDS4 Reader (Person 1)**
*Responsible for: .cub → Python arrays, metadata extraction, footprint clipping*

**Day 1 (Sept 25) — 4 hours**
1. Write `src/lunar_isis_gui/pds4_reader.py`:
   - Load `.cub` from `data/derived/isis/` via rasterio
   - Extract metadata: GSD, sun angles, image dims, geotransform
   - Parse XML label for sun azimuth/elevation (XPath, like current `app.py`)
   - Output: Python dict with `image` (NumPy array), `metadata` (geotransform, sun vector, GSD)
   - Test on verified pair: `ch2_ohr_ncp_20260330T2317474369_d_img_d18.cub` + `m188628884lc.cub`

2. Update `requirements/base.txt`:
   ```
   Pillow>=10.0
   rasterio>=1.3
   numpy>=2.0
   lxml>=4.9      # for XML parsing
   ```

**Day 2 (Sept 26) — 3 hours**
1. Write `src/lunar_isis_gui/footprint.py`:
   - Read GeoTIFF geotransform from rasterio
   - Find bounding box intersection (source × reference)
   - Crop both images to overlap region
   - Output: cropped arrays, overlap metadata
   - Test: verify visual overlap in QGIS or matplotlib

**Acceptance:** Both functions work on verified pair; no errors on import/crop.

---

### **Workstream B: Map Projection & Alignment (Person 2)**
*Responsible for: project reference into source coordinate system, one composed warp*

**Day 1 (Sept 25) — 5 hours**
1. Write `src/lunar_isis_gui/projection.py`:
   - Input: cropped source + reference GeoTIFFs (from Workstream A), geotransforms
   - Use ISIS `cam2map` (subprocess, like the GUI does) to project reference into source pixels
   - OR use GDAL/rasterio `Warp()` directly if camera models unavailable
   - Output: reference resampled to source grid (single Lanczos step)
   - Fallback: if camera geometry fails, use simple affine + manual grid search (slower but always works)

2. Test on verified pair:
   - Visual check: overlay source + projected reference, look for alignment
   - Metrics: image correlation before/after (should improve)

**Day 2 (Sept 26) — 2 hours**
1. Integrate with footprint tool
2. Edge case: handle poles (if needed for test data; otherwise skip)

**Acceptance:** Reference visually aligned to source; code runs <1 min per pair.

---

### **Workstream C: Feature Matching Pipeline (Person 3, lead developer)**
*Responsible for: the core matching algorithm, RANSAC, validation*

**Day 1 (Sept 25) — 6 hours**
1. Write `src/lunar_isis_gui/matching.py`:
   - Input: source array, projected reference array
   - Try LoFTR first:
     ```python
     from loftr import LoFTR
     matcher = LoFTR(pretrained='outdoor')
     kpts_src, kpts_ref, matches = matcher(source, reference)
     ```
   - Fallback to SIFT if LoFTR fails:
     ```python
     import cv2
     sift = cv2.SIFT_create()
     kpts_src, desc_src = sift.detectAndCompute(source, None)
     kpts_ref, desc_ref = sift.detectAndCompute(reference, None)
     bf = cv2.BFMatcher()
     matches = bf.knnMatch(desc_src, desc_ref, k=2)
     # Lowe's ratio test
     ```
   - Output: (N×2 array source coords, N×2 array reference coords, confidence scores)

2. Write `src/lunar_isis_gui/ransac.py`:
   - Input: raw match points (source, reference)
   - Fit affine transform: `cv2.estimateAffinePartial2D()` or `cv2.getAffineTransform()`
   - RANSAC threshold: 3 pixels (tight for sub-pixel aim, but achievable with LoFTR)
   - Output: inlier mask, transform matrix, residuals per point
   - Metrics: inlier ratio, spatial coverage (% of grid cells with match)

**Day 2 (Sept 26) — 4 hours**
1. Write `src/lunar_isis_gui/validation.py`:
   - Input: inlier points (source, reference), held-out checkpoints (random 20%)
   - Metrics:
     - RMSE, median, 90th percentile error on held-out points
     - Inlier count & ratio
     - Coverage: % of 10×10 grid with ≥1 point
   - Output: JSON report with all metrics

2. Test on verified pair; target: >400 inliers, >15% coverage, RMSE < 5 px

**Acceptance:** Matching runs <2 min, produces >300 inliers, RMSE reported.

---

### **Workstream D: GUI Integration & Output (Person 4, if available)**
*Responsible for: plumbing everything into a runnable CLI, GeoTIFF/CSV output*

**Day 1 (Sept 25) — 4 hours**
1. Write `src/lunar_isis_gui/register.py` (main entry point):
   ```python
   import sys
   from lunar_isis_gui.pds4_reader import load_cub
   from lunar_isis_gui.footprint import crop_to_overlap
   from lunar_isis_gui.projection import project_reference
   from lunar_isis_gui.matching import match_features
   from lunar_isis_gui.ransac import fit_transform
   from lunar_isis_gui.validation import measure_accuracy
   
   def register(source_cub, reference_cub, output_dir):
       # Pipeline: read → crop → project → match → fit → validate → save
       # Return: results dict
   
   if __name__ == '__main__':
       source, ref = sys.argv[1], sys.argv[2]
       register(source, ref, 'outputs/')
   ```

2. Write `src/lunar_isis_gui/output.py`:
   - Save registered GeoTIFF (source resampled to reference grid)
   - Save match points CSV: `src_x, src_y, ref_x, ref_y, residual_x, residual_y, confidence`
   - Save metrics JSON: `{"rmse": X, "median": Y, "ce90": Z, "inliers": N, "coverage": P}`

**Day 2 (Sept 26) — 3 hours**
1. Write a simple Matplotlib plotter:
   - 4-panel figure: original source, reference, registered overlay, residual arrows
   - Save to PNG for PPT

2. Test end-to-end on verified pair; CLI should be:
   ```bash
   python -m lunar_isis_gui.register data/derived/isis/ohrc/ch2_ohr_ncp_20260330T2317474369_d_img_d18.cub data/derived/isis/nac/m188628884lc.cub outputs/
   ```

**Acceptance:** CLI works, outputs exist, no crashes.

---

### **Workstream E: Crater Detection & Landmark Fallback (Person 5, if 5-person team)**
*Responsible for: coarse alignment via landmarks, used if feature matching fails*

**Day 1 (Sept 25) — 5 hours**
1. Write `src/lunar_isis_gui/crater_detection.py`:
   - Input: source image
   - Detect craters: OpenCV Hough circle detection or simple Laplacian-of-Gaussian
   - Filter: crater radius range 5–100 pixels (tunable)
   - Output: list of (x, y, radius) for each crater

2. Write `src/lunar_isis_gui/landmark_matching.py`:
   - Build feature constellation (distance ratios, angles between craters)
   - Match via RANSAC similarity transform
   - Output: coarse affine transform (initial guess for feature matcher)

**Day 2 (Sept 26) — 2 hours**
1. Integration: use landmark transform as initial guess for feature matching refinement (if available)
2. Test on verified pair; verify craters are detected

**Acceptance:** Craters detected, coarse alignment produced (visual check).

*Note: If 4-person team, defer Workstream E to post-demo. Fallback: feature matching alone is sufficient for MVP.*

---

## Parallel Execution Timeline

```
DAY 1 (Sept 25, 8 hours)
├─ A1: PDS4 reader        [Person 1, 4h]  → source/ref arrays
├─ B1: Projection         [Person 2, 5h]  → aligned reference
├─ C1: LoFTR/SIFT + RANSAC [Person 3, 6h] → match points + transform
├─ D1: CLI scaffolding    [Person 4, 4h]  → register.py stub
└─ E1: Crater detection   [Person 5, 5h, if available] → coarse alignment
    *Outputs integrated nightly*

DAY 2 (Sept 26, 8 hours)
├─ A2: Footprint clipping [Person 1, 3h]  → cropped arrays
├─ B2: Projection + edges [Person 2, 2h]  → final projected reference
├─ C2: Validation + metrics [Person 3, 4h] → RMSE, inliers, coverage
├─ D2: Output + plots     [Person 4, 3h]  → GeoTIFF, CSV, PNG
└─ E2: Landmark integration [Person 5, 2h, if available] → fallback pipeline
    *End of day: full pipeline runnable; test on verified pair*

DAY 3 (Sept 27, 6 hours) — REFINEMENT
├─ All: Test end-to-end, fix bugs
├─ All: Tune RANSAC threshold, LoFTR params on verified pair
├─ All: Verify RMSE < 5 px, inliers > 400, coverage > 15%
└─ All: Generate 4-panel demo plot

DAY 4 (Sept 28, 4 hours) — VALIDATION & DOCUMENTATION
├─ Person 3: Test on 2nd verified pair (if available), cross-check metrics
├─ Person 1: Document data flow, metadata extraction
├─ Person 2: Document projection methodology
├─ All: Write README with usage example
└─ All: Create PPT content (methods, results, metrics)

DAY 5 (Sept 29, 2 hours) — FINAL CHECKS & PPT
├─ Compile results, finalize PPT
├─ Last run-through on demo pair
└─ Code cleanup, comments
```

---

## Critical Files to Create / Modify

**New files (9 total):**
```
src/lunar_isis_gui/
├── __init__.py                 (update version to 0.2.0)
├── app.py                      (existing; no changes for MVP)
├── pds4_reader.py              (NEW: load .cub, extract metadata)
├── footprint.py                (NEW: overlap cropping)
├── projection.py               (NEW: map projection via ISIS/GDAL)
├── matching.py                 (NEW: LoFTR/SIFT feature extraction)
├── ransac.py                   (NEW: RANSAC fitting + inlier selection)
├── validation.py               (NEW: RMSE, CE90, coverage metrics)
├── crater_detection.py         (NEW: crater detection + constellation, OPTIONAL)
├── landmark_matching.py        (NEW: landmark constellation, OPTIONAL)
├── output.py                   (NEW: GeoTIFF, CSV, JSON export)
├── register.py                 (NEW: main CLI entry point)
└── plotting.py                 (NEW: 4-panel demo figure)

requirements/
├── base.txt                    (MODIFY: add numpy, rasterio, opencv, torch, etc.)
└── gpu.txt                     (no change; already has torch CUDA path)

outputs/                        (NEW: runtime directory for results)
├── registered.tiff
├── match_points.csv
├── metrics.json
└── demo.png
```

**Unchanged:**
- `app.py` (existing GUI) — keep as Phase 1; don't alter
- `data/` (raw/derived) — only read from
- `docs/` — add results to PPT separately

---

## Verification Checkpoints (Daily)

**End of Day 1:**
- [ ] PDS4 reader loads verified pair into arrays (no rasterio errors)
- [ ] Projection outputs projected reference (visual check in QGIS/matplotlib)
- [ ] LoFTR/SIFT produces match points (>100 raw matches)
- [ ] RANSAC outputs inliers + transform matrix

**End of Day 2:**
- [ ] Full pipeline runs: `python register.py source.cub ref.cub outputs/`
- [ ] GeoTIFF, CSV, JSON, PNG all written to `outputs/`
- [ ] Metrics computed on verified pair (report RMSE, median, inliers, coverage)

**End of Day 3:**
- [ ] RMSE < 5 px on verified pair
- [ ] Inliers > 400, coverage > 15%
- [ ] 4-panel demo plot ready for PPT
- [ ] No crashes on second pair (if tested)

---

## Scope Exclusions (To Stay On Time)

**NOT doing in 5 days:**
- ❌ Pushbroom jitter model (simple affine sufficient)
- ❌ Relighting & DEM resampling (feature matching alone works)
- ❌ Crater constellation as primary (is fallback only)
- ❌ Polar stereographic (test data not polar)
- ❌ IIRS chained registration
- ❌ LightGlue variant
- ❌ Streamlit UI (CLI + PPT plots only)
- ❌ Batch processing multiple pairs
- ❌ Production error handling (logs only)

**Post-demo (Phase 2, if time):**
- Relighting when DEM available
- Pushbroom jitter model
- Streamlit UI
- Batch pipeline

---

## Success Metrics for PPT

1. **Technical:**
   - ✅ RMSE < 5 px (or best achievable on verified pair)
   - ✅ >400 inliers, >15% coverage
   - ✅ Runtime <5 min per pair
   - ✅ Reproducible: same inputs → same outputs

2. **Presentation:**
   - ✅ 4-panel demo (source, reference, registered overlay, residuals)
   - ✅ Metrics table (RMSE, median, inliers, coverage)
   - ✅ 1-slide architecture diagram (steps 1-14, no jitter)
   - ✅ Live demo if time (CLI run on beamer)

3. **Code:**
   - ✅ Modular, readable, no `any` types
   - ✅ Each module independently testable
   - ✅ README with usage example

---

## Risk Mitigations

| Risk | Likelihood | Mitigation |
|------|------------|-----------|
| **LoFTR slow/OOM on OHRC** | Medium | Downscale to ~512×512 tiles; use SIFT fallback |
| **Projection via ISIS fails** | Low | Have GDAL fallback ready (simpler affine) |
| **Crater detection noisy** | Medium | Tune Hough params; make it optional (landmark fallback) |
| **5 px RMSE not achieved** | Medium | Accept best achievable; document in PPT |
| **Feature matcher finds too few matches** | Low | Adjust RANSAC threshold downward; relax outlier criterion |
| **Geotransform mismatch** | Low | Manually verify on verified pair; hardcode if needed |

---

## Quick Reference: Dependencies to Add

Update `requirements/base.txt` with:
```
Pillow>=10.0
numpy>=2.0
rasterio>=1.3
lxml>=4.9
scipy>=1.10
scikit-image>=0.22
opencv-python>=4.8
scikit-learn>=1.3
torch>=2.1
matplotlib>=3.7
```

---

## Next Steps

1. **Assign workstreams** to team members (A, B, C, D, E)
2. **Create Git branches:** `feature/workstream-A`, `feature/workstream-B`, etc.
3. **Daily standup:** 30 min sync, report blockers
4. **Nightly integration:** merge working code; test full pipeline
5. **Code review:** each PR reviewed before merge

---

## Team Roles

| Person | Workstream | Modules | Start Time |
|--------|-----------|---------|-----------|
| 1 | A: Data Pipeline | `pds4_reader.py`, `footprint.py` | Sept 25, 8 AM |
| 2 | B: Projection | `projection.py` | Sept 25, 8 AM |
| 3 | C: Feature Matching (Lead) | `matching.py`, `ransac.py`, `validation.py` | Sept 25, 8 AM |
| 4 | D: CLI & Output | `register.py`, `output.py`, `plotting.py` | Sept 25, 8 AM |
| 5 | E: Landmarks (Optional) | `crater_detection.py`, `landmark_matching.py` | Sept 25, 8 AM |

---

**Plan locked. Ready to code!**
