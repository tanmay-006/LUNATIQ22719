# LunaReg: Illumination-Aware Lunar Image Registration — Architecture v3

SIH 2026 · Problem Statement ID 26166 · Team LUNATIQ22719 (Team ID 122202)

> Multi-modal, sun-angle- and scale-invariant image correspondence between Chandrayaan-2 optical images (OHRC, TMC-2, IIRS) and lunar reference images (LRO NAC, SELENE TC), with sub-pixel accuracy and uniformly distributed match points.

## 0. What changed from v2

| Area | v2 | v3 |
| --- | --- | --- |
| Landmark (crater) matching | Fallback only | **Core pillar**: always runs and provides the coarse alignment |
| Illumination | Relighting from DEM as the main idea | **Closest-sun reference selection first**, then relighting only at DEM-supported resolution, or invariant features; shadow masking |
| Resampling | Project, resample and orthorectify in separate steps | **One composed warp**, applied to the reference only; the source is resampled once, at the very end |
| Pushbroom correction | Along-track polynomial or piecewise-affine, per tile | **Global line-dependent jitter model** fitted to all tie points; per-tile RANSAC only rejects outliers |
| Hold-out | Mentioned at validation | **Split before any fitting**; checkpoints bypass RANSAC and model fitting entirely |
| Failure handling | Not defined | **Fail → re-align via landmarks, or flag low confidence** |
| Poles | Not handled | **Polar mode**: polar stereographic projection, shadow masking, shadow-edge matching |
| Wording | "learned matcher" | "pre-trained feature-matching algorithm" (no model is trained by us) |

## 1. Design principles

1. **Two core ideas.** (a) Match the lighting; (b) match crater and landmark constellations. Everything else is standard, well-tested registration engineering.
2. **The source image is never modified** until the single final warp. Only a temporary copy of the reference is relit or resampled.
3. **One interpolation per image.** Geometric steps are composed into one transform before resampling, to avoid cascading interpolation artefacts.
4. **The pipeline knows when it has failed.** Accuracy is measured on held-out checkpoints, never on the points used for fitting.
5. **The DEM is optional and resolution-aware.** It helps where its resolution supports the matching scale; the pipeline still runs without it.

## 2. Scope and sensor pairing

Each Chandrayaan-2 source is paired with a reference of similar resolution, so no pair has more than about a 2× gap in native resolution (IIRS is the exception; only its reference is downsampled).

| Source (Chandrayaan-2) | Source GSD | Reference | Reference GSD | Notes |
| --- | --- | --- | --- | --- |
| OHRC | ~0.25 m | LRO NAC | ~0.5 m | Hardest pair: sub-pixel on the source needs ~0.5 px on the NAC grid |
| TMC-2 | ~5 m | SELENE TC | ~10 m | |
| IIRS (PCA band) | ~80 m | SELENE TC, downsampled | ~10 m → 80 m | ~250 spectral bands reduced to one (first PCA component or best high-SNR band) |

- Sub-pixel accuracy is always defined in **source pixels**.
- Coarse stages run at a common pyramid level; fine refinement runs at source resolution.
- Optional IIRS fallback: chained registration (IIRS → already-registered TMC-2), flagged in the report.

## 3. Pipeline

```text
INPUTS
  CH-2 source (OHRC / TMC-2 / IIRS, PDS4 + metadata)
  Reference candidates (LRO NAC / SELENE TC, many acquisitions)
  Optional lunar DEMs (SLDEM2015, LOLA incl. polar DEMs, TMC-2 / NAC DTMs)
                              |
                              v
1. INGEST & METADATA
   PDS4 read; sun azimuth/elevation, footprint, GSD, invalid-pixel mask;
   IIRS band reduction (PCA / best band)
                              |
                              v
2. ROI FROM FOOTPRINTS
   Overlap region + uncertainty margin; crop BEFORE heavy processing
                              |
                              v
3. CLOSEST-SUN REFERENCE SELECTION
   Choose the reference acquisition whose sun azimuth/elevation best
   matches the source  -> removes much of the lighting gap up front
                              |
                              v
4. ONE COMPOSED WARP (reference only)
   Map projection + orthorectification composed into a single transform
   into the SOURCE geometry; one Lanczos resampling. Source untouched.
   Polar mode (|lat| > ~70 deg): polar stereographic projection
                              |
                              v
5. TILING & PYRAMIDS
   Large OHRC scenes split into tiles; multi-resolution levels
                              |
                              v
6. ILLUMINATION HANDLING                         <-- CORE IDEA 1
   6a. If DEM resolution supports the current pyramid level:
       relight a COPY of the reference under the source sun vector
   6b. Otherwise: illumination-invariant representations
       (phase congruency, gradient orientation mod pi)
   6c. Shadow masking: cast shadows + permanently shadowed regions excluded
   6d. Polar extra (future work): shadow-edge matching vs DEM ray-cast shadows
                              |
                              v
7. LANDMARK CONSTELLATION MATCHING               <-- CORE IDEA 2
   Detect craters, ridges, terrain junctions (rim-shape check rejects
   shadow artefacts) -> constellation graph -> crater-triangle matching
   (distance ratios + angles) + RANSAC -> coarse similarity transform
   + confidence; verified by phase correlation
                              |
                              v
8. TILED LoFTR MATCHING
   Pre-trained feature-matching algorithm, guided by the coarse transform
   (small search window per tile); optional LightGlue branch
                              |
                              v
9. SPLIT 20% HOLD-OUT CHECKPOINTS  -----------------------------+
   Set aside BEFORE any fitting                                 |
                              |                                 |
                              v                                 |
10. RANSAC / MAGSAC                                             |
    Per-tile, loose threshold: outlier rejection only           |
                              |                                 |
                              v                                 |
11. UNIFORM GRID SELECTION                                      |
    Best match per grid cell, minimum separation                |
                              |                                 |
                              v                                 |
12. SUB-PIXEL REFINEMENT                                        |
    Phase correlation on invariant / relit patches              |
                              |                                 |
                              v                                 |
13. GLOBAL PUSHBROOM JITTER MODEL                               |
    Smooth function of image line fitted to ALL tie points      |
    (regularised polynomial / few sinusoids) + residual filter  |
                              |                                 |
                              v                                 |
14. VALIDATION  <-----------------------------------------------+
    RMSE / median / CE90 on held-out checkpoints
        FAIL -> re-align via landmarks (step 7) or flag low confidence
        PASS -> 15
                              |
                              v
15. FINAL WARP
    Source resampled ONCE onto the reference grid
                              |
                              v
OUTPUTS
    Registered GeoTIFF | sub-pixel match points (CSV: source/reference
    coords, confidence) | transformation + jitter model | residual vector
    field | RMSE, median, CE90 | inlier count & ratio | spatial coverage &
    uniformity | per-point confidence map | processing report
```

## 4. Core idea 1: illumination handling

**Closest-sun reference selection.** LRO NAC has imaged most regions, and the poles especially, many times under different sun geometries. Picking the reference whose sun azimuth and elevation are closest to the source often removes most of the lighting difference before any modelling.

**Relighting (when the DEM supports it).** A copy of the reference is re-shaded under the source's sun vector:

$$
I_{\text{relit}}(x,y) = \max\big(0,\; \mathbf{n}(x,y)\cdot\mathbf{s}_{\text{source}}\big)\cdot \rho(x,y)
$$

where $\mathbf{n}$ is the surface normal from the DEM, $\mathbf{s}_{\text{source}}$ is the source sun direction and $\rho$ is the reference albedo. Cast shadows are added by ray-casting along the sun elevation.

**Resolution constraint.** Global DEMs cannot predict metre-scale shadows. SLDEM2015 is ~60 m/px, TMC-2 DTMs ~10 m, and LOLA polar DEMs ~5–20 m. Relighting is therefore applied only at pyramid levels the DEM supports: full resolution for TMC-2 and IIRS, coarse levels only for OHRC. Site-specific high-resolution DTMs (e.g. LROC NAC stereo DTMs) are used where available.

**Illumination-invariant representations (otherwise).**
- Phase congruency: structure and edges independent of contrast.
- Gradient orientation mod π: survives brightness reversal when a slope is lit from opposite sides.

**Shadow masking.** Cast shadows and permanently shadowed regions carry no usable signal and are excluded from matching; spatial uniformity is then reported over the lit area only.

## 5. Core idea 2: landmark constellation matching

Crater geometry is stable under any lighting, and relative positions between craters are invariant to scale and rotation. This stage always runs and provides the coarse alignment.

- **Detection:** craters (classical Hough / contour methods with a rim-shape check that rejects shadow-only artefacts), ridges and terrain junctions. Shortcut: detect craters in the source only and match them against the published global lunar crater catalogue (Robbins 2019) for the reference area.
- **Constellation graph:** landmarks as nodes; for landmarks $v_i, v_j, v_k$:

$$
r_{ij} = \frac{d(v_i,v_j)}{d(v_i,v_k)}, \qquad \theta_{ijk} = \angle\big(v_i-v_j,\; v_k-v_j\big)
$$

- **Matching:** crater triangles with consistent ratios and angles vote for a similarity transform (RANSAC), in the same way star trackers match star patterns.
- **Check:** the transform is verified by phase correlation, which also gives a confidence score.
- **Role:** crater centroids are accurate to a few pixels, so they **guide** the fine matcher and are **not** mixed into the final sub-pixel fit.

Feature tiers:
- **Tier 1** (large craters, junctions, large terrain boundaries): constellation matching.
- **Tier 2** (smaller craters, ridge segments, texture): left to the fine feature-matching algorithm.
- **Tier 3** (rocks, small boulders, shadow edges): not used as landmarks.

Feature-poor maria: landmarks extend beyond craters (ridges, rilles, albedo boundaries), and the detector-free LoFTR matcher handles low texture.

## 6. Transformation and distortion model

Hierarchy: similarity → affine → affine + global pushbroom jitter model.

- **No homography.** It assumes a planar scene seen through a frame camera; after orthorectification that assumption doesn't hold.
- **Global jitter model.** OHRC and TMC-2 are pushbroom (line-scanning) cameras. Spacecraft jitter depends only on image line (time) and is the same across all columns, while terrain parallax depends on elevation and is removed by orthorectification. Jitter is therefore fitted as one regularised smooth function of line number using all tie points, not tile by tile, to avoid overfitting terrain differences.
- **Model selection:** the simplest model whose held-out error is acceptable; AIC/BIC as a tiebreaker.

## 7. Challenges and strategies

| Type | Challenge | Strategy |
| --- | --- | --- |
| Sun angle | Shadows flip, features change | Closest-sun reference, relighting at DEM-supported scale, invariant features |
| Sun angle | Shadows mimic or hide craters | Rim-shape check at multiple scales; reject shadow-only detections |
| Viewpoint | Camera tilt and terrain relief | Orthorectification in one composed warp (single resampling) |
| Viewpoint | Pushbroom jitter distortion | Global line-dependent jitter model; RANSAC only rejects outliers |
| Scale | >100× resolution range across sensors | Sensor-matched references (~2× gap per pair), reference-only resampling, pyramids |
| Scale | Unknown scale / rotation | Crater constellation distance ratios and angles (invariant) |
| Polar | Low sun, permanent shadows | Closest-sun reference, shadow masking, polar stereographic, shadow-edge matching (future) |
| Data | Feature-poor maria | Landmarks beyond craters (ridges, rilles) + detector-free LoFTR |
| Data | Matchers built for Earth images | Validate LoFTR on synthetic relit lunar pairs; classical matching as fallback |
| Data | No DEM for a scene | DEM is optional; invariant features only |

## 8. Validation and evaluation

**Ground truth**
1. **Synthetic pairs:** real or simulated terrain, a known transform, and relighting at a different sun angle. Error is measured against the known transform; this is the direct evidence for sub-pixel accuracy.
2. **Held-out checkpoints:** a random 20% of matches, split before fitting and used only for error measurement.
3. **Manual checkpoints:** a small set of hand-picked point pairs on real images.

**Metrics:** RMSE, median error and CE90 on checkpoints · inlier count and ratio · spatial uniformity (% of grid cells with a match, convex-hull area ratio) · runtime per pair.

**Stratified results:** by sun-angle difference (0–15°, 15–45°, >45°), by sensor pair, and polar vs non-polar.

**Early evidence (synthetic demo):** on simulated cratered terrain lit from opposite sides, SIFT + RANSAC found **0 correct matches out of 41 candidates**; after relighting the reference to the source sun, it found **444 correct matches**, spread across the image. With a deliberately degraded (smoothed + noisy) DEM, the relit case still gave 43 correct matches.

**Ablation table (to fill)**

| Method | RMSE (px) | Inlier ratio | Coverage |
| --- | --- | --- | --- |
| SIFT + RANSAC (baseline) | | | |
| Raw LoFTR | | | |
| + Closest-sun reference | | | |
| + Relighting / invariant features | | | |
| + Landmark constellation coarse alignment | | | |
| Full pipeline (+ jitter model) | | | |

## 9. Implementation plan

| Phase | Content | Status target |
| --- | --- | --- |
| 1. Baseline | Map-projected inputs, SIFT + RANSAC, RMSE and inlier metrics | Before finale |
| 2. Landmarks | Crater / ridge detection, constellation (triangle) matching | Before finale |
| 3. Illumination | Closest-sun selection, relighting, invariant features, shadow masks | Before finale |
| 4. Fine matching | Tiled LoFTR, MAGSAC, grid selection, sub-pixel phase correlation, simple jitter model | Core |
| 5. Benchmark & demo | Synthetic ground truth, ablation, GeoTIFF/CSV outputs, Streamlit demo | Core |

**Minimum viable product (must work):** map-projected inputs · closest-sun reference · relighting or phase features · crater-triangle coarse alignment · LoFTR (SIFT fallback) · MAGSAC · grid selection · sub-pixel phase correlation · held-out RMSE · GeoTIFF + CSV outputs.

**Extensions (presented as future work):** full orthorectification from camera models (SPICE) · high-fidelity spacecraft jitter modelling · polar shadow-edge matching · LightGlue branch · chained IIRS registration.

**Key risks and mitigations**
- **Data preparation** is the biggest time risk: use map-projected / ortho products (LROC, SELENE, ISSDC derived products) instead of building orthorectification from raw geometry.
- **LoFTR on lunar images is unproven:** test it early on 2–3 real pairs; the pipeline falls back to classical matching plus phase-correlation refinement.
- **OHRC sub-pixel target** needs ~0.5 px accuracy on the NAC grid: verify on the synthetic benchmark.

## 10. Technology stack

| Tool | Use |
| --- | --- |
| Python + GDAL / rasterio | PDS4 reading, lunar map projections, GeoTIFF output |
| OpenCV / scikit-image | Crater detection (Hough / contours), phase correlation, RANSAC / MAGSAC |
| PyTorch + Kornia | Pre-trained LoFTR / LightGlue feature-matching algorithms (GPU) |
| NumPy / SciPy | Constellation graph matching, relighting, jitter model |
| scikit-learn | PCA for IIRS band reduction |
| Streamlit | Demo UI: upload, register, view residual arrow maps |

## 11. Data sources

- Chandrayaan-2 OHRC, TMC-2, IIRS: ISRO ISSDC — https://chmapbrowse.issdc.gov.in/
- LRO NAC: https://lroc.im-ldi.com/images/downloads/ · LROC QuickMap: https://quickmap.lroc.im-ldi.com/
- SELENE (Kaguya) Terrain Camera: JAXA DARTS — https://darts.isas.jaxa.jp/planet/pdap/selene/
- Lunar DEMs: SLDEM2015 (Barker et al., Icarus, 2016); LOLA via PDS Geosciences Node — https://pds-geosciences.wustl.edu/
- Crater catalogue: Robbins, *A global lunar crater database*, JGR Planets, 2019

## 12. Proposal-ready architecture statement

> LunaReg is an illumination-aware, landmark-guided registration pipeline for Chandrayaan-2 optical imagery. For each source image (OHRC, TMC-2, IIRS), it selects the resolution-matched reference acquisition (LRO NAC or SELENE TC) whose sun geometry is closest to the source, crops to the footprint overlap, and maps the reference into the source geometry with a single composed projection-and-orthorectification warp, so each image is interpolated only once. It is built on two core ideas. First, the lighting difference is reduced by relighting a copy of the reference under the source's sun angle where the terrain model's resolution supports it, or by using illumination-invariant representations otherwise, with shadows masked out. Second, craters, ridges and terrain junctions are matched as a constellation graph using scale- and rotation-invariant distance ratios and angles, giving a robust coarse alignment. This alignment guides a pre-trained feature-matching algorithm (LoFTR) tile by tile. Twenty percent of matches are held out before any fitting; the rest are filtered with MAGSAC, selected for uniform coverage, refined to sub-pixel precision by phase correlation, and corrected with a global pushbroom jitter model. Accuracy is measured on the held-out checkpoints; results that fail are re-aligned or flagged, and results that pass are produced with a single final warp. Outputs include registered GeoTIFFs, sub-pixel match points, transformation models, residual vector fields, RMSE, inlier statistics and spatial coverage metrics.