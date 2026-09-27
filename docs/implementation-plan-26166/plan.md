# Implementation Plan: Uniform, Robust Lunar Image Correspondence

**Date**: 2026-09-27 | **Spec**: [problem-statement-26166.md](../problem-statement-26166.md)

## Summary

Strengthen the existing OHRC/LRO registration pipeline so accepted correspondences are
spatially distributed before RANSAC, while preserving the current SIFT/LoFTR matching,
partial-affine fitting, fail-loud thresholds, and quality metrics. The plan captures the
problem statement as explicit requirements because the source statement does not provide
REQ identifiers.

## Technical Context

**Language/Version**: Python 3
**Primary Dependencies**: NumPy, OpenCV, optional Kornia/torch, GDAL/ISIS command-line tools
**Storage**: File-based ISIS cubes, GeoTIFF products, CSV match points, JSON metrics
**Testing**: pytest with synthetic image and point fixtures
**Target Platform**: Headless registration CLI and Tkinter GUI workbench
**Performance Goals**: Bound raster dimensions before feature extraction and keep selection
linear in the number of candidate matches.
**Constraints**: Source imagery must not be silently altered; projection failures and
insufficient correspondences must remain explicit; optional LoFTR must continue to fall
back to SIFT with a warning.

## Constitution Check

*GATE: Must pass. Re-check after implementation.*

- Preserve existing six-stage pipeline boundaries: **PASS**.
- Keep source/reference point arrays aligned and typed: **PASS**.
- Fail explicitly for invalid inputs and low-confidence registration: **PASS**.
- Avoid new mandatory runtime dependencies: **PASS**.
- Keep scientific limitations of fallback projection documented: **PASS**.

## Applied Guidelines

No repository-specific migration guideline applies. The implementation follows existing
functional module boundaries, `TypedDict` contracts, NumPy arrays, and pytest patterns.

## Implementation Steps

### Step 1: [Cross-cutting] Establish executable correspondence requirements
- **Requirements**: REQ-001, REQ-002, REQ-003, REQ-004
- **Design inputs**: Existing `matching.py`, `register.py`, `ransac.py`,
  `validation.py`, and `README.md`.
- **Description**: Use the current pipeline as the baseline; define uniformity as
  deterministic best-confidence selection with at most one match per grid cell and
  optional minimum source-point separation. Do not loosen RANSAC or validation gates.

### Step 2: [Cross-cutting] Add uniform correspondence selection
- **Requirements**: REQ-001, REQ-002
- **Design inputs**: `FeatureMatches` contract in `matching.py`.
- **Description**: Add a typed helper that validates inputs, ranks candidates by
  confidence, selects one candidate per source-image grid cell, preserves aligned
  arrays, and leaves small candidate sets usable. Invoke it immediately after feature
  matching and before diagnostics/RANSAC.

### Step 3: [Cross-cutting] Verify metrics and regression behavior
- **Requirements**: REQ-002, REQ-003, REQ-004
- **Design inputs**: Existing RANSAC, validation, output, and CLI tests.
- **Description**: Add focused tests for deterministic grid selection, alignment,
  invalid input handling, and end-to-end preservation of existing fail-loud behavior.
  Update user-facing documentation to explain the selection and its limitations.

## Project Structure

```text
src/lunar_isis_gui/
  matching.py       # uniform correspondence selection and matcher contract
  register.py       # pipeline integration
tests/
  test_matching.py  # focused selection tests
docs/
  implementation-plan-26166/plan.md
  implementation-plan-26166/checkpoints/spec-to-plan.yaml
  implementation-plan-26166/checkpoints/plan-to-tasks.yaml
```

## Testing Strategy

- **appType**: CLI plus desktop GUI
- **Critical user journeys**:
  1. Match an overlapping source/reference pair and receive aligned match arrays.
  2. Reject insufficient or degenerate registration instead of writing misleading output.
  3. Run with optional LoFTR unavailable and receive a SIFT fallback warning.
- **primaryValidationStack**: pytest unit tests with OpenCV/NumPy synthetic fixtures.
- **fallbackMatrix**:
  - `infra-tier`: synthetic arrays → no external ISIS/GDAL prerequisite for focused tests.
  - `browser-tier`: not applicable; this is a desktop/CLI workflow.
- **Environment requirements**: Python dependencies for tests; ISIS/GDAL only for
  integration against real cubes.
- **knownGaps**: Synthetic tests do not prove camera-model projection accuracy,
  illumination invariance on mission imagery, or sub-pixel accuracy on verified pairs.
- **Test data strategy**: deterministic synthetic images and point arrays; no raw
  mission data committed.
- **Acceptance criteria**: selected points remain aligned, occupied grid cells are
  distributed as requested, existing tests pass, and no output is written after a
  validation failure.
- **Validation review expectations**: confirm selection happens before RANSAC and that
  confidence ordering, array alignment, and failure messages remain observable.

## Phase 1: Setup

- [x] T001 [Plan:1.1] Record the normalized requirement mapping and preserve existing module boundaries in `docs/implementation-plan-26166/plan.md`.

## Phase 2: Foundational

- [x] T002 [Plan:2.1] Add validated uniform correspondence selection to `src/lunar_isis_gui/matching.py`.
- [x] T003 [Plan:2.1] Integrate selection before match visualization and RANSAC in `src/lunar_isis_gui/register.py`.

## Phase 3: User Story 1 (P1) — Obtain uniformly distributed correspondences

- [x] T004 [US1] [Plan:2.1] Add deterministic selection, alignment, and invalid-input tests in `tests/test_matching.py`.
- [x] T005 [US1] [Plan:3.1] Update `README.md` with the selection behavior and scientific limitations.

## Final Phase: Cross-cutting validation

- [x] T006 [Plan:3.1] Run the focused matcher and registration test suite and confirm no unrelated files changed.

## Requirement Mapping

| REQ ID | Description | Plan Items | Implementation Evidence |
|--------|-------------|------------|------------------------|
| REQ-001 | Find correspondences across Chandrayaan-2 and lunar reference imagery. | 2.1 | `src/lunar_isis_gui/matching.py`, `src/lunar_isis_gui/register.py` |
| REQ-002 | Maintain a uniform spatial distribution of accepted match points. | 2.1, 3.1 | Grid selection helper and `tests/test_matching.py` |
| REQ-003 | Support registration-quality evaluation including RMSE, inlier count, and ratio. | 3.1 | Existing `validation.py` and regression tests |
| REQ-004 | Preserve robust operation across illumination, viewpoint, and scale variation. | 1.1, 3.1 | Existing SIFT/LoFTR, bounded resize, projection, and fail-loud tests |
