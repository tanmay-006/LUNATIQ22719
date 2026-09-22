# Hybrid Hierarchical Lunar Image Registration Architecture

## 1. Combined technical architecture

The recommended system is a hybrid hierarchical registration pipeline:

- Metadata provides coarse geographic and scale constraints.
- Natural landmark detection provides interpretable, stable structural features.
- Graph/constellation matching estimates a reliable coarse transformation.
- LoFTR or LightGlue generates dense/fine correspondences within the reduced search area.
- RANSAC, spatial selection, and sub-pixel refinement produce the final registration.

```text
OHRC / TMC / IIRS IMAGE + LRO NAC / SELENE REFERENCE
                         |
                         v
1. DATA INGESTION
   Image reading, metadata parsing, sensor identification,
   coordinate system validation, invalid-pixel detection
                         |
                         v
2. SENSOR-AWARE PREPROCESSING
   Radiometric normalization, denoising, destriping, CLAHE,
   gradient image, edge image, phase image, valid-pixel mask
                         |
                         v
3. METADATA-BASED APPROXIMATE FOOTPRINT
   Lunar coordinates, camera geometry, GSD, solar angles,
   spacecraft position, DEM/orthorectification if available
                         |
                         v
4. REFERENCE ROI EXTRACTION
   Estimate overlap region, scale range, rotation range,
   uncertainty margin, and valid search area
                         |
                         v
5. MULTI-SCALE NATURAL LUNAR LANDMARK DETECTION
   Craters and crater rims; ridges and linear forms;
   valleys and depressions; albedo/edge boundaries;
   rocks and boulders; texture patterns; terrain junctions;
   shadow-aware structures
                         |
                         v
6. STRUCTURAL FEATURE REPRESENTATION
   Shape, scale, orientation, gradient, phase, local texture,
   crater geometry, relative distances, angles, adjacency,
   local spatial relationships, sensor-invariant descriptors
                         |
                         v
7. SPATIAL CONSTELLATION / GRAPH MATCHING
   Landmark graph construction -> candidate graph matching ->
   geometric consistency filtering -> coarse transformation
   Output: initial translation, rotation, scale, affine model,
   candidate correspondence pairs, confidence score
                         |
                         v
8. COARSE IMAGE-LEVEL REGISTRATION
   Warp source image using similarity/affine transformation,
   reduce residual search area, align image pyramids
                         |
                         v
9. FINE CORRESPONDENCE GENERATION
   Option A: LoFTR for detector-free dense matching
   Option B: SuperPoint + LightGlue for sparse robust matching
   Option C: Both, with confidence-based result fusion
                         |
                         v
10. MULTI-SOURCE CORRESPONDENCE FUSION
    Combine graph matches, LoFTR/LightGlue matches, descriptor
    confidence, geometric consistency, and local image quality
                         |
                         v
11. ROBUST GEOMETRIC ESTIMATION
    Similarity -> affine -> homography -> local deformation model
    RANSAC/MAGSAC, reprojection-error filtering, model scoring
                         |
                         v
12. SPATIALLY UNIFORM MATCH SELECTION
    Grid-based selection, Poisson-disk sampling, confidence
    ranking, minimum separation, coverage optimization
                         |
                         v
13. SUB-PIXEL REFINEMENT
    Local NCC, phase correlation, Lucas-Kanade, multi-channel
    patch optimization, uncertainty estimation
                         |
                         v
14. FINAL REGISTRATION AND VALIDATION
    Final warp, optional local deformation correction,
    held-out validation, residual vector analysis
                         |
                         v
OUTPUTS
    Registered image; source/reference match points;
    sub-pixel coordinates; transformation matrix/model;
    residual vector field; RMSE and median error;
    inlier count and ratio; spatial coverage and uniformity;
    confidence map and processing report
```

## 2. Why the combination is better

### The semantic architecture

Natural landmark and graph-based reasoning avoids depending entirely on pixel intensity. Useful structures include:

- Crater rim geometry
- Ridge orientation
- Valley intersections
- Relative distances
- Local spatial arrangements
- Terrain topology

These features can remain recognizable despite differences in sun angle, sensor type, contrast, spectral response, and image resolution.

### The registration architecture

The engineering stages add:

- Sensor-specific preprocessing
- Multi-scale matching
- Learned fine correspondence
- Outlier removal
- Uniform point distribution
- Sub-pixel refinement
- Quantitative validation
- Operational output products

Together, the architecture is both scientifically meaningful and computationally implementable.

## 3. LoFTR and LightGlue

LoFTR and LightGlue should be treated as alternative or complementary fine-matching strategies rather than mandatory sequential modules.

### Option A: LoFTR branch

```text
Coarsely aligned images -> LoFTR -> Dense or semi-dense fine correspondences
```

LoFTR is useful when there are few reliable keypoints, weak texture, significant viewpoint or appearance variation, or a need for dense correspondences.

### Option B: LightGlue branch

```text
Coarsely aligned images -> SuperPoint / SIFT / DISK -> LightGlue -> Sparse high-confidence correspondences
```

LightGlue is useful when stable keypoints can be detected, sparse high-confidence matches are sufficient, and computational efficiency is important.

### Recommended approach

```text
Graph-based landmarks
        |
        +--> LoFTR branch
        |
        +--> LightGlue branch
                |
                v
      Confidence and geometry-based fusion
```

Use the combined ensemble:

$$
M_{\text{final}} = M_{\text{graph}} \cup M_{\text{LoFTR}} \cup M_{\text{LightGlue}}
$$

Remove duplicates and retain only geometrically consistent matches before RANSAC.

## 4. Role of each feature type

### Tier 1: Most reliable

- Crater centers
- Crater rims
- Large crater intersections
- Ridge junctions
- Valley junctions
- Large-scale terrain boundaries
- Stable albedo boundaries

These should drive the coarse transformation.

### Tier 2: Moderately reliable

- Smaller crater rims
- Ridge segments
- Valley segments
- Terrain texture patterns
- Boulder fields

These are useful for fine matching and local refinement.

### Tier 3: Potentially unreliable

- Individual rocks
- Small boulders
- Shadow boundaries
- Isolated bright or dark spots

These can change significantly with sun angle, resolution, sensor response, and viewing direction. They should not be primary landmarks unless confidence is high.

## 5. Landmark graph representation

Represent each image as a graph:

$$
G = (V,E)
$$

where $V$ represents detected landmarks and $E$ represents relationships between landmarks.

Each node can contain:

```text
Node:
    x, y
    landmark_type
    scale
    orientation
    shape_descriptor
    confidence
    local_texture_descriptor
```

Each edge can contain:

```text
Edge:
    distance_between_nodes
    relative_angle
    orientation_difference
    landmark_type_pair
    local terrain relationship
```

For three landmarks $v_i, v_j, v_k$, use geometric invariants such as:

$$
r_{ij} = \frac{d(v_i,v_j)}{d(v_i,v_k)}
$$

and

$$
\theta_{ijk} = \angle(v_i-v_j,\;v_k-v_j)
$$

These ratios and angles are more robust to scale and rotation than raw image coordinates.

A graph match is valid when:

- Landmark types are compatible.
- Relative distances are consistent.
- Relative angles are consistent.
- The resulting transformation agrees with neighboring matches.

## 6. Recommended matching logic

1. Detect semantic and structural landmarks.
2. Construct source and reference landmark graphs.
3. Match graph constellations using scale- and rotation-invariant relations.
4. Estimate the initial similarity or affine transformation.
5. Warp the source image approximately.
6. Run LoFTR and/or LightGlue in the reduced search area.
7. Fuse all candidate correspondences.
8. Apply geometric verification with RANSAC.
9. Select spatially uniform inlier matches.
10. Refine selected matches to sub-pixel accuracy.
11. Estimate the final transformation.
12. Generate registered products and quality metrics.

This is preferable to running LoFTR or LightGlue directly on full images because the graph stage reduces the search space, improves robustness to large scale differences, provides an explainable initial alignment, helps avoid false matches in repetitive crater regions, and makes fine matching faster.

## 7. Transformation estimation strategy

Use a hierarchical model-selection strategy:

```text
Graph correspondences -> Similarity transformation
                      -> Affine transformation
                      -> Homography, if justified
                      -> Local deformation, if necessary
```

Do not start directly with a homography or thin-plate spline. A flexible model can produce a visually aligned but physically incorrect result.

For each model, calculate:

- Inlier count
- Inlier ratio
- RMSE
- Spatial coverage
- Validation error
- Model complexity penalty

A suitable model score is:

$$
S = w_1N_{\text{inlier}} + w_2R_{\text{inlier}} + w_3C_{\text{coverage}} - w_4RMSE - w_5P_{\text{complexity}}
$$

Select the simplest model that gives acceptable residual error.

## 8. Recommended implementation phases

### Phase 1: Baseline

Implement:

- Metadata parsing
- Image normalization
- Gradient and phase images
- SIFT or AKAZE matching
- RANSAC affine estimation
- Grid-based uniform match selection
- Local NCC refinement
- RMSE and inlier metrics

This provides a working benchmark.

### Phase 2: Natural landmark module

Add:

- Crater detection
- Crater rim extraction
- Ridge and valley extraction
- Landmark confidence scoring
- Graph construction
- Graph-based coarse alignment

This is the key scientific contribution.

### Phase 3: Learned fine matching

Add either LoFTR or SuperPoint + LightGlue. Start with one model. LoFTR may be simpler conceptually for the first learned implementation because it does not require a separate keypoint detector.

### Phase 4: Hybrid fusion

Combine:

- Graph matches
- Learned matches
- Classical descriptors
- Geometric confidence
- Local correlation confidence

### Phase 5: Sub-pixel and local correction

Add:

- Sub-pixel patch refinement
- Local affine correction
- Thin-plate spline or B-spline deformation only where justified
- Uncertainty estimation

## 9. Proposal-ready architecture statement

> The proposed system uses a metadata-assisted, hierarchical, multi-modal image-registration architecture. First, approximate image footprints and scale ranges are estimated using spacecraft and sensor metadata. Sensor-specific radiometric and geometric preprocessing is then applied to generate illumination-invariant representations. Natural lunar landmarks such as crater rims, ridges, valleys, albedo boundaries, and terrain junctions are detected and represented using shape, gradient, texture, and spatial-relation descriptors. A spatial constellation or graph-matching module establishes robust coarse correspondences using scale- and rotation-invariant geometric relationships. The resulting transformation initializes a fine correspondence stage based on LoFTR and/or LightGlue. Candidate correspondences from semantic graph matching, learned matching, and classical descriptors are fused and verified using robust RANSAC/MAGSAC estimation. Spatially uniform inlier points are selected using grid- or Poisson-disk-based sampling, followed by local sub-pixel refinement using normalized cross-correlation and phase-based optimization. Finally, the source image is registered, and the system generates match points, transformation parameters, confidence maps, RMSE, inlier ratio, spatial coverage, and registration-quality reports.

## 10. Final recommendation

Retain the natural landmark and graph-based architecture as the scientific core, and extend it with:

```text
Your architecture:
    Natural landmarks
    Structural representation
    Graph matching
    Coarse transformation

Added engineering modules:
    Sensor preprocessing
    Metadata-assisted ROI
    Multi-scale processing
    LoFTR/LightGlue fine matching
    RANSAC/MAGSAC
    Uniform match selection
    Sub-pixel refinement
    Validation and product generation
```

The strongest final design is:

```text
Metadata-assisted coarse localization
        +
Natural lunar landmark graph matching
        +
Learned fine correspondence
        +
Robust geometric verification
        +
Spatially uniform sampling
        +
Sub-pixel refinement
        +
Quantitative validation
```

This hybrid design is more robust, explainable, and suitable for the Chandrayaan-2 multi-modal registration problem than either a purely handcrafted graph approach or a purely deep-learning-based matcher.
