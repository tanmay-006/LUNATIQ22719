# LunaReg Implementation Status Tracker

**Last Updated:** Sept 25, 2026 · **Days Remaining:** 5 (until Sept 30)  
**Team Size:** 1 person (solo) · **Status:** Implementation Starting

---

## Workstream Assignment & Progress

## Daily Progress Tracking

| Day | Target Modules | Hours | Status | Blockers | Notes |
|---|---|---|---|---|---|
| **Sept 25 (Day 1)** | cub_loader.py, requirements | 4 | ✅ COMPLETE | ISISROOT is unset in the shell | Loader uses the configured ISIS Conda interpreter and verified both OHRC and NAC cubes |
| **Sept 26 (Day 2)** | projection.py, footprint.py, matching.py, ransac.py, validation.py | 4 | 🟡 IN PROGRESS | cam2map invocation depends on local ISIS map configuration | Projection and overlap cropping added; matching/RANSAC/metrics remain |
| **Sept 27 (Day 3)** | register.py, output.py, plotting.py | 4 | ⏳ WAITING FOR DAY 2 | — | Integration + CLI |
| **Sept 28 (Day 4)** | Parameter tuning, 2nd pair validation | 3 | ⏳ WAITING FOR DAY 3 | — | Refinement |
| **Sept 29 (Day 5)** | PPT + docs, code cleanup | 2 | ⏳ WAITING FOR DAY 4 | — | Final prep |
---

## File Checklist (13 modules to create + 1 config update)

### Day 1 (Sept 25) — Setup + CUB Loader
- [x] Update `requirements/base.txt` — add numpy, opencv, torch, scipy, scikit-image, scikit-learn, matplotlib
- [x] Create `src/lunar_isis_gui/cub_loader.py`
  - `load_cub_with_isis(path)` → loads .cub via ISIS commands, extracts metadata
  - `extract_cub_array(path)` → convert .cub → temp GeoTIFF → NumPy array
  - Test on verified pair: `ch2_ohr_ncp_20260330T2317474369_d_img_d18.cub` + `m188628884lc.cub`

### Day 2 (Sept 26) — Projection, Footprint, Feature Matching
- [x] Create `src/lunar_isis_gui/projection.py`
  - `project_reference_via_isis(source_cub, ref_cub)` → use ISIS `cam2map` subprocess
  - Fallback: simple affine alignment if ISIS unavailable
  - Test: visual overlap check
- [x] Create `src/lunar_isis_gui/footprint.py`
  - `crop_to_overlap(source_arr, ref_arr, source_meta, ref_meta)` → find & crop intersection
- [ ] Create `src/lunar_isis_gui/matching.py` (~200 lines)
  - `match_features(source, reference)` → LoFTR primary, SIFT fallback
- [ ] Create `src/lunar_isis_gui/ransac.py` (~100 lines)
  - `fit_transform(source_pts, ref_pts)` → RANSAC affine, returns inliers + transform
- [ ] Create `src/lunar_isis_gui/validation.py` (~120 lines)
  - `measure_accuracy(inliers, checkpoints)` → RMSE, median, CE90, coverage

### Day 3 (Sept 27) — CLI Integration, Output, Plotting
- [ ] Create `src/lunar_isis_gui/register.py` (~100 lines)
  - Main orchestrator: load → project → crop → match → RANSAC → validate → save
  - CLI: `python -m lunar_isis_gui.register source.cub ref.cub outputs/`
- [ ] Create `src/lunar_isis_gui/output.py` (~80 lines)
  - Save: registered GeoTIFF, match_points CSV, metrics JSON
- [ ] Create `src/lunar_isis_gui/plotting.py` (~150 lines)
  - `plot_4panel(source, ref, registered, residuals)` → PNG for PPT
- [ ] Update `src/lunar_isis_gui/__init__.py` → version 0.2.0
- [ ] Full E2E test on verified OHRC/NAC pair

### Days 4-5 — Refinement & PPT (Optional modules)
- [ ] `src/lunar_isis_gui/crater_detection.py` — (OPTIONAL if time permits)
- [ ] `src/lunar_isis_gui/landmark_matching.py` — (OPTIONAL if time permits)
- [ ] PPT content + documentation
- [ ] Create `src/lunar_isis_gui/landmark_matching.py` (~150 lines)
  - `match_craters(craters_src, craters_ref)` → constellation graph + RANSAC
  - Returns coarse affine transform

### Supporting
- [ ] Create `outputs/` directory for results
- [ ] Update `src/lunar_isis_gui/__init__.py` — bump version to 0.2.0

---

## Verification Checkpoints

### End of Day 1 (Sept 25, 5 PM)
```
✅ Expected Status:
- [ ] All modules import without errors
- [ ] PDS4 reader loads verified pair (OHRC + NAC)
- [ ] Projection outputs aligned reference
- [ ] LoFTR/SIFT produces >100 raw matches
- [ ] RANSAC produces inlier mask + transform
- [ ] register.py skeleton compiles
```

### End of Day 2 (Sept 26, 5 PM)
```
✅ Expected Status:
- [ ] Full pipeline runs: python -m lunar_isis_gui.register source.cub ref.cub outputs/
- [ ] Outputs exist: registered.tiff, match_points.csv, metrics.json, demo.png
- [ ] Metrics reported: RMSE, median, inliers, coverage on verified pair
- [ ] No crashes on E2E test
```

### End of Day 3 (Sept 27, 5 PM)
```
✅ Expected Status:
- [ ] RMSE < 5 px achieved (or best documented)
- [ ] Inliers > 400, coverage > 15%
- [ ] 4-panel demo plot ready for PPT
- [ ] No crashes on 2nd pair (if tested)
```

### End of Day 4 (Sept 28, 5 PM)
```
✅ Expected Status:
- [ ] Cross-pair validation (2+ pairs tested)
- [ ] README written with usage examples
- [ ] Code documented with inline comments
- [ ] PPT content drafted (methods, results, metrics)
```

### End of Day 5 (Sept 29, 5 PM)
```
✅ Expected Status:
- [ ] Final PPT ready for presentation
- [ ] Code cleanup + no warnings
- [ ] Last E2E test run successful
- [ ] All modules merged to main
```

---

## Critical Path (What Blocks What)

```
START (Sept 25)
│
├─ A1: PDS4 reader ──────────┐
│                            ├─ B1: Projection ────┐
└─ A2: Footprint ────────────┘                     ├─ C1: Matching ─┐
                                                   │                ├─ D1: Register
                                                   └─ RANSAC ───────┘

START (Sept 26)
│
├─ C2: Validation ──────┐
│                       ├─ D2: Output + Plotting
└─ B2: Refinement ──────┘

RESULT (Sept 26 EOD): Full pipeline runnable
```

**Critical blockers:**
- 🔴 If A1 fails → B1, C1, D1 all blocked
- 🔴 If B1 fails → C1, D1 blocked (but fallback to simple affine)
- 🔴 If C1 fails → switch to SIFT immediately
- 🔴 If D1 fails → no way to run pipeline

---

## Daily Standup Template

**Time:** 5 PM each day (end of shift)  
**Duration:** 15 min  
**Participants:** All 5 people (or 4 if no Person 5)

```
Person 1 (Data Pipeline):
  ✅ What I finished today:
  ⚠️  Blockers:
  📅 Tomorrow's plan:

Person 2 (Projection):
  ✅ What I finished today:
  ⚠️  Blockers:
  📅 Tomorrow's plan:

[Person 3, 4, 5...]
```

---

## Success Metrics (Final)

| Metric | Target | Evidence |
|--------|--------|----------|
| **Accuracy** | RMSE < 5 px | metrics.json on verified pair |
| **Matches** | >400 inliers | match_points.csv line count |
| **Coverage** | >15% spatial | validation report |
| **Speed** | <5 min/pair | logged runtime |
| **Reproducibility** | Same input → same output | re-run on verified pair |
| **Code Quality** | Modular, readable, typed | GitHub review |
| **Presentation** | 4-panel + metrics table | PNG + JSON for PPT |

---

## Git Workflow

**Branch naming:**
```
feature/workstream-A   (Person 1)
feature/workstream-B   (Person 2)
feature/workstream-C   (Person 3)
feature/workstream-D   (Person 4)
feature/workstream-E   (Person 5)
```

**Commit convention:**
```
feat:     new feature (add pds4_reader.py)
fix:      bug fix (RANSAC threshold)
test:     add tests or E2E validation
refactor: code improvement without behavior change
chore:    dependencies, version bump
docs:     README or comments only
```

**Example commits:**
```
git commit -m "feat: add PDS4 reader via rasterio"
git commit -m "test: validate projection on verified pair"
git commit -m "feat: add LoFTR + SIFT fallback matching"
git commit -m "chore: update requirements with numpy, rasterio, opencv"
```

**Merge policy:**
- Every module gets one commit (e.g., `pds4_reader.py` = one commit)
- Each module is PR-reviewed before merge
- Daily nightly integration test (full pipeline)

---

## Key Resources

| Resource | Location | Purpose |
|----------|----------|---------|
| **Architecture** | `docs/lunar-registration-hybrid-architecture.md` | Algorithm reference, pipeline steps |
| **Test data (verified)** | `data/derived/isis/{ohrc,nac}/*.cub` | Use for validation |
| **ISIS tools** | Conda env (launched via `launch_isis_gui.sh`) | Map projection fallback |
| **Plan** | `SPRINT_PLAN.md` (this dir) | Read for scope + timeline |
| **Status** | `IMPLEMENTATION_STATUS.md` (this dir) | Update daily |

---

## Common Pitfalls (Avoid These)

❌ **Don't:**
- Skip unit tests until Day 2 (test modules daily)
- Commit untested code (test locally first)
- Change `app.py` (it's Phase 1, off-limits)
- Hardcode file paths (use arguments + config)
- Ignore rasterio/GDAL warnings (fix them immediately)
- Wait until Day 2 to integrate (integrate daily)

✅ **Do:**
- Test each module incrementally
- Commit after each working module
- Communicate blockers early (daily standup)
- Document edge cases (especially projection fallbacks)
- Ask for help when stuck (don't wait)
- Verify on verified pair early and often

---

## Troubleshooting Quick Links

| Problem | Solution |
|---------|----------|
| Rasterio can't read .cub | Check if converted via ISIS; confirm in data/derived/ |
| Projection fails | Try GDAL fallback; check geotransform parsing |
| LoFTR OOM | Downscale images to 512×512 tiles; use SIFT fallback |
| RANSAC inliers = 0 | Lower threshold from 3 to 5 pixels; check match points are valid |
| RMSE < 5 px not achieved | Document best achievable; optimize params on Day 3 |
| Import errors | Verify requirements installed: `pip install -r requirements/base.txt` |

---

## Timeline Overview

```
Sept 25 (Day 1):  Module coding sprint (all workstreams in parallel)
Sept 26 (Day 2):  Integration + full pipeline E2E test
Sept 27 (Day 3):  Refinement + parameter tuning
Sept 28 (Day 4):  Cross-pair validation + documentation
Sept 29 (Day 5):  Final checks + PPT compilation
Sept 30 (Demo):   DEADLINE — presentation ready
```

**Current time:** Sept 25, morning  
**Status:** 🟢 READY TO START  
**Next action:** Assign workstreams, create Git branches, begin coding
