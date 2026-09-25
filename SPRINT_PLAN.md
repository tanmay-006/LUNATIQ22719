# LunaReg: 5-Day Solo Sprint to Working Prototype

**Team:** 1 person · **Deadline:** Sept 30, 2026 (5 days) · **Goal:** End-to-end registration on verified OHRC/NAC pair with PPT

---

## TL;DR

Build a minimal but complete registration pipeline optimized for solo execution: ingest OHRC + NAC (as .cub files) → use ISIS for projection → match features (LoFTR + SIFT fallback) → measure accuracy. Skip jitter model, relighting, and IIRS. Leverage existing ISIS integration and Conda environment.

**Success Criteria (MVP):**
- ✅ Registered GeoTIFF output (source overlaid on reference)
- ✅ Match point CSV (300+ inliers, >10% coverage)
- ✅ RMSE / median error on verified pair < 5 pixels
- ✅ Code runs in <5 min per pair
- ✅ Repeatable on CLI: `python -m lunar_isis_gui.register source.cub ref.cub outputs/`
- ✅ Demo plot showing original → registered → residuals

---

## 5-Day Sequential Plan (1 Person)

### **Day 1 (Sept 25) — Setup & CUB Reader (4 hours)**

**1.1 Update dependencies (30 min)**
```bash
# Update requirements/base.txt with:
numpy>=2.0
scipy>=1.10
opencv-python>=4.8
torch>=2.1
matplotlib>=3.7
scikit-learn>=1.3
scikit-image>=0.22
```
Note: rasterio/GDAL NOT needed — using ISIS for .cub reading + projection instead.

**1.2 Create CUB loader via ISIS (1.5 hours)**
Write `src/lunar_isis_gui/cub_loader.py`:
- Function: `load_cub_with_isis(cub_path)` — uses `gdalinfo` or `gaea` (ISIS utility) to read .cub dimensions + geotransform
- Function: `extract_cub_array(cub_path)` — convert .cub to temporary GeoTIFF via ISIS `cube2tiff` (if available) or `gdal_translate`, then read as NumPy array
- Extract metadata: GSD, sun angles from XML labels in raw product directories (reuse XPath from `app.py`)
- Output: dict with `image` (NumPy uint16 or float32), `metadata` (geotransform, sun vector, GSD)
- **Test on verified pair:** Load both `ch2_ohr_ncp_20260330T2317474369_d_img_d18.cub` + `m188628884lc.cub`

**1.3 Verify ISIS integration (1 hour)**
- Confirm `ISISROOT` + Conda env accessible
- Test `gadalinfo`, `cube2tiff` availability
- Fallback: if ISIS tools unavailable, use Python `gdal` bindings (already in most Conda-ISIS envs)

---

### **Day 2 (Sept 26) — Projection & Footprint (4 hours)**

**2.1 Map projection via ISIS (2 hours)**
Write `src/lunar_isis_gui/projection.py`:
- Function: `project_reference_via_isis(source_cub, ref_cub)` → calls ISIS `cam2map` subprocess to project reference into source coordinate system
- Alternative if `cam2map` fails: simple manual affine alignment (use image correlation to find best shift/scale)
- Output: reference resampled to source grid as NumPy array
- **Test:** visual overlap check (matplotlib plot overlay)

**2.2 Footprint & cropping (1.5 hours)**
Write `src/lunar_isis_gui/footprint.py`:
- Function: `crop_to_overlap(source_array, ref_array, source_metadata, ref_metadata)` → finds bbox intersection, crops both
- Output: cropped arrays + overlap bounds
- **Test:** verify crop is non-empty, visual check

**2.3 Integrate & test end-to-end data flow (0.5 hours)**
- Verify: load source → project reference → crop → both valid arrays
- **Checkpoint:** By EOD, `register.py` stub can import and chain steps 1–2 without errors

---

### **Day 3 (Sept 27) — Feature Matching & RANSAC (5 hours)**

**3.1 Feature matching (2 hours)**
Write `src/lunar_isis_gui/matching.py`:
- Function: `match_features(source_array, ref_array)` → try LoFTR, fallback to SIFT
- LoFTR: `from loftr import LoFTR; matcher = LoFTR(pretrained='outdoor')`
- SIFT fallback: OpenCV SIFT + BFMatcher + Lowe's ratio test (threshold 0.7)
- Output: (N, 2) arrays for source & reference keypoint coords, plus confidence scores
- **Target:** >100 raw matches
- **Test:** plot keypoint matches on source + reference (matplotlib)

**3.2 RANSAC outlier rejection (2 hours)**
Write `src/lunar_isis_gui/ransac.py`:
- Function: `fit_transform(source_pts, ref_pts)` → RANSAC affine via `cv2.estimateAffinePartial2D()`
- Threshold: 3 pixels (tight but achievable with LoFTR)
- Output: inlier mask, transform matrix (2×3), residuals per point
- **Target:** >300 inliers, inlier ratio >30%
- **Test:** overlay original + aligned reference (visual check)

**3.3 Validation metrics (1 hour)**
Write `src/lunar_isis_gui/validation.py`:
- Function: `measure_accuracy(inliers, checkpoints)` → splits 20% as hold-out, computes RMSE/median/CE90
- Output: JSON dict with `rmse`, `median`, `ce90`, `inliers_count`, `inliers_ratio`, `coverage_pct`
- **Test:** compute on verified pair

---

### **Day 4 (Sept 28) — Output, Plotting & Full Integration (4 hours)**

**4.1 CLI orchestrator (1 hour)**
Write `src/lunar_isis_gui/register.py`:
```python
def register(source_cub, ref_cub, output_dir):
    # 1. Load + project
    # 2. Crop to overlap
    # 3. Match + RANSAC
    # 4. Validate
    # 5. Save outputs
    # Return metrics dict

if __name__ == '__main__':
    register(sys.argv[1], sys.argv[2], sys.argv[3] or 'outputs/')
```

**4.2 Output export (1 hour)**
Write `src/lunar_isis_gui/output.py`:
- Save registered GeoTIFF (source warped to reference grid)
- Save matches.csv: `src_x, src_y, ref_x, ref_y, confidence, inlier`
- Save metrics.json: `{"rmse": ..., "median": ..., "ce90": ..., "inliers": ..., "coverage": ...}`

**4.3 Visualization (1.5 hours)**
Write `src/lunar_isis_gui/plotting.py`:
- Function: `plot_4panel(source, ref, registered, residuals)` → 4-panel figure (original source, reference, overlay, residuals with arrows)
- Save to PNG for PPT

**4.4 Full E2E test (0.5 hours)**
```bash
python -m lunar_isis_gui.register data/derived/isis/ohrc/ch2_ohr_ncp_20260330T2317474369_d_img_d18.cub data/derived/isis/nac/m188628884lc.cub outputs/
```
- Verify all outputs exist (GeoTIFF, CSV, JSON, PNG)
- **Target metrics by EOD:** RMSE < 10 px (refined on Day 5), >300 inliers, >10% coverage

---

### **Day 5 (Sept 29) — Refinement & PPT (3 hours)**

**5.1 Parameter tuning (1 hour)**
- Adjust RANSAC threshold, LoFTR confidence threshold, SIFT parameters
- Re-run on verified pair, aim for RMSE < 5 px
- Document best-achieved metrics

**5.2 Test on 2nd pair (1 hour)**
- Re-run full pipeline on `m1185136706lc.cub` (if verified correspondence exists)
- Verify reproducibility + metrics consistency

**5.3 PPT + documentation (1 hour)**
- Document methods: ISIS projection, LoFTR/SIFT matching, RANSAC, metrics
- Finalize 4-panel plot + metrics table for presentation
- Write README with CLI usage example
- Code cleanup + comments

**Acceptance:** CLI works end-to-end, RMSE achieved (or best documented), PPT ready

---

## Sequential Execution Timeline (1 Person)

```
SEPT 25 (Day 1): 4 hours
  └─ Setup + CUB loader
     ├─ Update requirements (30 min)
     ├─ Write cub_loader.py (1.5 hours)
     └─ Test on verified pair (1 hour)
     OUTPUT: Can load .cub files + extract metadata

SEPT 26 (Day 2): 4 hours
  └─ Projection + Footprint
     ├─ ISIS projection (2 hours) → projection.py
     ├─ Footprint cropping (1.5 hours) → footprint.py
     └─ E2E chain test (0.5 hours)
     OUTPUT: Can load, project, crop → ready for matching

SEPT 27 (Day 3): 5 hours
  └─ Feature Matching + RANSAC
     ├─ LoFTR/SIFT matching (2 hours) → matching.py
     ├─ RANSAC transform fitting (2 hours) → ransac.py
     └─ Validation metrics (1 hour) → validation.py
     OUTPUT: Can extract features, fit transform, compute RMSE

SEPT 28 (Day 4): 4 hours
  └─ Output + Integration
     ├─ CLI orchestrator (1 hour) → register.py
     ├─ Save outputs (1 hour) → output.py
     ├─ Plotting (1.5 hours) → plotting.py
     └─ Full E2E test (0.5 hours)
     OUTPUT: Full pipeline runs: python -m lunar_isis_gui.register ... 
     TARGET: >300 inliers, RMSE ~10 px (acceptable, will refine)

SEPT 29 (Day 5): 3 hours
  └─ Refinement + PPT
     ├─ Tune parameters (1 hour)
     ├─ Test on 2nd pair (1 hour)
     └─ PPT + docs (1 hour)
     OUTPUT: RMSE < 5 px achieved, PPT ready, all metrics documented
```

---

## Critical Files to Create (7 modules + 1 config update)

**Modules to create (8 total, ~1000 lines of code):**
```
src/lunar_isis_gui/
├── __init__.py                 (update version to 0.2.0)
├── app.py                      (existing; no changes)
├── cub_loader.py               (NEW: load .cub + extract metadata via ISIS)
├── projection.py               (NEW: project reference via ISIS cam2map)
├── footprint.py                (NEW: crop to overlap region)
├── matching.py                 (NEW: LoFTR/SIFT feature extraction)
├── ransac.py                   (NEW: RANSAC fitting + inlier selection)
├── validation.py               (NEW: RMSE, CE90, coverage metrics)
├── output.py                   (NEW: GeoTIFF, CSV, JSON export)
├── register.py                 (NEW: main CLI orchestrator)
└── plotting.py                 (NEW: 4-panel demo figure)

requirements/
├── base.txt                    (MODIFY: add numpy, opencv, torch, scipy, etc.)
└── gpu.txt                     (no change)

outputs/                        (NEW: runtime directory)
├── registered.tif
├── matches.csv
├── metrics.json
└── diagnostic.png
```

**Key simplification:** No rasterio/GDAL/complex projection. Instead:
- Use ISIS `cam2map` (subprocess) for projection (like existing GUI does)
- Use `cube2tiff` or `gdal_translate` to convert .cub → temporary GeoTIFF
- Use Python `gdal` bindings (included in ISIS Conda env) for array I/O
- Use existing app.py XPath logic to extract sun angles from XML labels

**Unchanged:**
- `app.py` (Phase 1 GUI, off-limits)
- `data/` (read-only)
- `docs/` (reference only)

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

1. **Start with Day 1:** Update requirements.txt, create cub_loader.py
2. **Daily targets:** Complete each day's modules in order (Days 1-5)
3. **Test EOD:** Each day ends with end-to-end test (can import all modules)
4. **Save & commit:** Commit working code after each day
5. **Adapt as needed:** If any module takes longer, adjust next day's scope

---

## Team Roles

## Execution Notes (1 Person)

- **No parallelization:** Follow Days 1-5 sequence
- **No team coordination:** Work solo, run E2E test at end of each day
- **ISIS subprocess pattern:** Copy from existing `app.py` for projection + format conversion
- **Error handling:** Implement graceful fallbacks (e.g., SIFT if LoFTR fails, affine if ISIS fails)
- **Minimal UI:** CLI only; save PPT plots at end
- **Testing strategy:** Test on verified OHRC/NAC pair at end of Day 2, refinements Days 3-5
---

**Plan locked. Ready to code!**
