# Illumination-Aware Hierarchical Lunar Image Registration — v2

## 1. Scope and sensor pairing

Each Chandrayaan-2 source image is registered to a lunar reference image. The reference is always resampled to the source's GSD before any matching.

| Source (Chandrayaan-2) | GSD | Reference | Matching resolution |
| --- | --- | --- | --- |
| OHRC | ~0.25 m | LRO NAC (~0.5 m) | ~0.5 m (OHRC downsampled) |
| TMC-2 | ~5 m | SELENE TC (~10 m) | ~10 m |
| IIRS | ~80 m | SELENE TC, downsampled | ~80 m |

For IIRS, the ~250 spectral bands are reduced to one input, either the first PCA component or a single high-SNR band.

Optional fallback for IIRS: chained registration (IIRS → registered TMC-2). It is used only when direct matching fails, and the report flags it.

## 2. Pipeline

```text
CH-2 SOURCE (OHRC / TMC-2 / IIRS)  +  REFERENCE (LRO NAC / SELENE TC)
                 +  OPTIONAL DEM (TMC-2 DTM / SLDEM / LOLA)
                              |
                              v
1. DATA INGESTION
   PDS4 reading, metadata parsing (sun azimuth/elevation,
   spacecraft geometry, GSD, footprint), invalid-pixel mask,
   IIRS band reduction (PCA / best band)
                              |
                              v
2. MAP PROJECTION & RESAMPLING
   Project source and reference to a common lunar map projection.
   With DEM: true orthorectification (removes terrain parallax).
   Without DEM: projection onto lunar sphere (R = 1737.4 km).
   Resample reference to source GSD.
   -> Removes most scale and rotation differences
                              |
                              v
3. REFERENCE ROI EXTRACTION
   Footprint overlap + uncertainty margin from metadata
                              |
                              v
4. SENSOR-AWARE PREPROCESSING
   Radiometric normalization, denoising, destriping only where
   needed (sensor-specific), valid-pixel mask
                              |
                              v
5. ILLUMINATION HANDLING   <-- core contribution
   5a. [If DEM] Relight reference: render hillshade from DEM
       using the SOURCE sun azimuth/elevation, blend with
       reference albedo -> "illumination-matched reference"
   5b. [Always] Illumination-robust representations:
       phase congruency, gradient orientation (mod pi),
       for use in matching and refinement
                              |
                              v
6. COARSE ALIGNMENT CHECK
   Phase correlation on robust representations
   -> residual translation estimate + confidence
                              |
              +---------------+----------------+
              | confidence OK                  | low confidence
              |                                | (poor metadata, large offset)
              |                                v
              |          7. FALLBACK: LANDMARK GRAPH MATCHING
              |             Tier 1 landmarks only (large crater
              |             centers, ridge/valley junctions)
              |             Graph with scale/rotation-invariant
              |             distance ratios and angles
              |             -> similarity transform
              +---------------+----------------+
                              |
                              v
8. FINE CORRESPONDENCE (tiled)
   LoFTR (or RoMa if GPU allows) on source vs.
   illumination-matched reference, within reduced search area
   Evaluated / fine-tuned on synthetic relit lunar pairs
                              |
                              v
9. ROBUST GEOMETRIC ESTIMATION
   MAGSAC/RANSAC
   Model hierarchy: similarity -> affine -> affine + local
   pushbroom correction (along-track polynomial / piecewise
   affine). NO homography.
   Model selection by held-out checkpoint error (or AIC/BIC)
                              |
                              v
10. SPATIALLY UNIFORM MATCH SELECTION
    Grid-based selection (best match per cell), minimum
    separation, coverage maximization
                              |
                              v
11. SUB-PIXEL REFINEMENT
    Phase correlation / NCC on gradient-orientation images
    or illumination-matched reference (never raw intensity
    across different sun angles). Per-point uncertainty.
                              |
                              v
12. FINAL REGISTRATION & VALIDATION
    Final warp to reference geometry
    Metrics on HELD-OUT checkpoints (not fitting inliers)
                              |
                              v
OUTPUTS
   Registered GeoTIFF | match points CSV (source/reference,
   sub-pixel coords, confidence) | transform model |
   residual vector field | RMSE, median error, CE90 |
   inlier count & ratio | grid coverage & uniformity |
   confidence map | processing report
```

## 3. Illumination handling

This section is the core contribution, and it maps directly onto the problem statement's headline challenge.

**Mode A: with a DEM (best accuracy).** The DEM gives the slope and aspect of every point on the surface. From these, compute the shading the terrain would have under the source image's sun vector:

$$
I_{\\text{relit}}(x,y) = \\max\\big(0,; \\mathbf{n}(x,y)\\cdot\\mathbf{s}_{\\text{source}}\\big)
$$

Here **n** is the surface normal from the DEM and **s** is the source sun direction. Cast shadows are added using sun elevation. The result is blended with the reference's albedo. The source is then matched against this relit reference, which turns a cross-illumination problem into a same-illumination one.

**Mode B: without a DEM (generic fallback).** Match on representations that are largely unaffected by shading:

- **Phase congruency:** picks out edges and structure while ignoring contrast.
- **Gradient orientation mod π:** survives brightness reversal, where a slope is lit on one side in one image and on the other side in the other side in the other image.

The DEM is optional input. The system runs in Mode B without it, and results are reported for both modes.

## 4. Role of landmark graph matching (fallback)

Graph matching is used only when metadata-based coarse alignment is unreliable, for example with a large offset or a low phase-correlation peak.

- **Nodes:** Tier 1 landmarks only, meaning large crater centers and ridge/valley junctions. These are the features most stable across illumination.
- **Edge invariants** for landmarks $v_i, v_j, v_k$:

$$
r_{ij} = \\frac{d(v_i,v_j)}{d(v_i,v_k)}, \\qquad \\theta_{ijk} = \\angle(v_i-v_j,; v_k-v_j)
$$

- **Output:** an initial similarity transform only.

Crater centroids are accurate to only a few pixels, so they **initialize** the transform and are **not** mixed into the final sub-pixel fit.

Feature tiers:

- **Tier 1** (large craters, junctions, large terrain boundaries): used for coarse and fallback alignment.
- **Tier 2** (smaller craters, ridge segments, texture): left to the learned fine matcher.
- **Tier 3** (rocks, small boulders, shadow edges): **not used as landmarks.**

## 5. Transformation model

The hierarchy is: similarity → affine → affine plus local pushbroom correction.

- **No homography.** It assumes a planar scene seen through a frame camera. After orthorectification that assumption doesn't hold, and it can produce alignments that look right but are physically wrong.
- **Pushbroom correction.** OHRC and TMC-2 are line scanners, so their leftover errors vary line by line (spacecraft jitter). These are modeled with a low-order polynomial along track or a piecewise-affine warp.
- **Model selection:** pick the simplest model whose error on held-out checkpoints is acceptable. AIC/BIC can serve as a tiebreaker.

## 6. Validation and evaluation

**Ground truth**

1. **Synthetic pairs:** take a real image, apply a known transform plus DEM relighting at a different sun angle, then register. The error is measured against the known transform. This is the only direct evidence of sub-pixel accuracy.
2. **Held-out checkpoints:** a random 20% of the matches are excluded from fitting and used only for error measurement.
3. **Manual checkpoints:** a small set of hand-picked point pairs on real image pairs.

**Metrics**

- RMSE, median error and CE90, computed on checkpoints.
- Inlier count and inlier ratio.
- Spatial uniformity: the percentage of grid cells containing a match, plus the convex-hull area ratio.
- Runtime per image pair.

**Stratified results:** error broken down by sun-angle difference (0–15°, 15–45°, >45°) and by sensor pair.

**Ablation table**

| Method | RMSE | Inlier ratio | Coverage |
| --- | --- | --- | --- |
| SIFT + RANSAC (baseline) |  |  |  |
| Raw LoFTR |  |  |  |
| Ours, no DEM (Mode B) |  |  |  |
| Ours, with DEM relighting (Mode A) |  |  |  |
| Ours, with graph fallback forced |  |  |  |

## 7. Implementation phases

1. **Baseline:** PDS4 ingestion, map projection, resampling, SIFT + RANSAC affine, and metrics. This is the benchmark everything else is compared against.
2. **Illumination module:** DEM hillshade relighting plus phase-congruency and gradient-orientation representations. Show the improvement over the baseline; this is the key demo result.
3. **Fine matching:** tiled LoFTR, grid-based uniform selection, and sub-pixel refinement.
4. **Evaluation:** synthetic ground-truth benchmark and ablation table.
5. **Fallback and extensions:** landmark graph matching, pushbroom local correction, and chained IIRS registration.
6. **Packaging:** GeoTIFF and CSV outputs, a report generator, and a Streamlit demo UI.

Phases 1–4 are enough for a complete, competitive submission. Phase 5 is a bonus.

## 8. Proposal-ready architecture statement

> The proposed system is an illumination-aware, metadata-assisted, hierarchical registration pipeline for Chandrayaan-2 optical imagery. Source images (OHRC, TMC-2, IIRS) and reference images (LRO NAC, SELENE TC) are first projected into a common lunar map frame and resampled to a common ground sample distance, removing most scale and rotation differences. To address sun-angle variation, the core challenge, the system renders an illumination-matched reference by relighting the terrain with the source image's solar geometry using an optional digital elevation model. When no DEM is available, it matches on illumination-robust representations such as phase congruency and gradient orientation. Residual offsets are estimated by phase correlation, with a scale- and rotation-invariant lunar landmark graph matcher as a fallback for poor metadata. Dense correspondences are generated with a learned matcher (LoFTR) in the reduced search area, verified with MAGSAC, and fitted with a physically motivated model hierarchy that includes along-track correction for pushbroom sensors. Spatially uniform matches are selected by grid sampling and refined to sub-pixel accuracy. Performance is evaluated on held-out checkpoints and synthetic ground-truth pairs, with results reported by sun-angle difference and sensor pair. Outputs include registered GeoTIFFs, sub-pixel match points, transformation models, residual fields, RMSE, inlier statistics and spatial coverage metrics.
