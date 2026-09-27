# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Illumination-aware image registration between Chandrayaan-2 OHRC imagery and LRO NAC reference imagery (SIH 2026, problem statement 26166). Two deliverables share one Python package `src/lunar_isis_gui/`:

- **Registration CLI** (`register.py`) — the core pipeline, run headless.
- **Tkinter GUI workbench** (`app.py`) — imports raw PDS products into ISIS cubes and runs the same pipeline in a background thread with live stage previews.

Note: `docs/lunar-registration-hybrid-architecture.md` describes an aspirational v3 design (crater-constellation matching, illumination relighting, jitter models, polar mode). The **implemented** pipeline is a simpler diagnostic subset — SIFT/LoFTR feature matching + partial-affine RANSAC. Treat the doc as design intent, not a description of current code.

## Environment

There is **no usable local virtualenv** — the checked-in `.venv/` is a stale Windows venv (paths point at `d:\SIH`). The real runtime is a conda env named `isis` that also supplies the ISIS command-line tools and GDAL:

```bash
source ~/miniforge3/etc/profile.d/conda.sh
conda activate isis
```

The pipeline shells out to external binaries and locates them via `$ISISROOT`/`$CONDA_PREFIX`/`bin` and `PATH` (see `_find_tool` in `cub_loader.py`, `_tool` in `projection.py`): `gdal_translate`, `gdalinfo`, `cube2tiff`, `cam2map`, plus `isisimport`/`pds2isis` for import. Missing tools raise `CubLoaderError` with an activation hint. Cubes are read by converting to a temporary TIFF, then reading with `osgeo.gdal` (falls back to Pillow).

## Commands

```bash
# Tests (each test file inserts src/ onto sys.path itself, so no PYTHONPATH needed)
pytest
pytest tests/test_ransac.py::test_name        # single test

# Registration CLI
PYTHONPATH=src python -m lunar_isis_gui.register SOURCE.cub REFERENCE.cub OUTPUT_DIR/
#   --method {sift,loftr,auto}            default sift; auto tries LoFTR then SIFT
#   --projection-method {fallback,auto}   default fallback; auto attempts ISIS cam2map
#   --max-dimension N                     default 2048; use 0 for native dimensions
#   --save-intermediates                  write 01_*..05_* stage checkpoints

# GUI (requires the isis conda env + display)
./launch_isis_gui.sh
```

## Pipeline architecture

`register.register()` orchestrates six stages, each a single-purpose module:

1. `cub_loader.load_cub_with_isis` — cube → array + metadata (dimensions, geotransform, gsd, sun angles from adjacent `.xml` label). `max_dimension` downsamples at GDAL-convert time to avoid loading multi-GB rasters.
2. `projection.project_reference_via_isis` — resample reference onto the source pixel grid. `cam2map` (map-projection, `auto`) or `_affine_fallback` (resize + phase correlation, `fallback`). **The fallback is diagnostic-only, not scientifically valid** — `metrics.json` records which method ran and any `cam2map` error.
3. `footprint.crop_to_overlap` — crop both to their geospatial intersection (or shared pixel extent when no geotransform).
4. `matching.match_features` — SIFT (BFMatcher + Lowe ratio, dedupes many-to-one matches) or LoFTR (kornia/torch, GPU if available). LoFTR failures fall back to SIFT with a `warning`.
5. `ransac.fit_transform` — `cv2.estimateAffinePartial2D` with RANSAC; validates against degenerate/duplicate point geometry up front.
6. `validation.measure_accuracy` — RMSE, median error, CE90, inlier ratio, coverage; supports held-out `checkpoints`.

**Fail-loud design:** the run raises (writes nothing) rather than emitting a misleading result when there are <3 matches, <3 inliers, or inlier ratio <0.5. This is expected for low-texture or poorly-overlapping inputs — don't "fix" it by loosening the thresholds without cause.

Outputs (`output.py`): `registered.tif`, `matches.csv`, `metrics.json`, `diagnostic.png`. With `--save-intermediates`, also `01_source.tif`, `02_projected_reference.tif`/`.png`, `03_overlap*`, `04_matches.png`, `05_ransac.png` (`plotting.py`).

## Conventions

- Modules are pure/functional and return `TypedDict`s (`CubProduct`, `ProjectedReference`, `FeatureMatches`, `TransformFit`, `ValidationMetrics`); the CLI and GUI both consume these. Keep new stage logic in its own module and out of `register.py`/`app.py`.
- Data lives outside the source tree and is gitignored: `data/raw/{ohrc,nac}/` (PDS products), `data/derived/isis/` (cubes/GeoTIFFs), `outputs/`. `docs/verified-test-pairs.md` lists known-good OHRC/NAC test pairs.
