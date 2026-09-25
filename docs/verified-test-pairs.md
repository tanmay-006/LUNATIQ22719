# Verified Test Pairs

## OHRC fragment inside LRO NAC

Status: User-verified visual correspondence.

Source image:

- Product: `ch2_ohr_ncp_20260330T2317474369_d_img_d18`
- Instrument: Chandrayaan-2 OHRC
- Input label: `data/raw/ohrc/ch2_ohr_ncp_20260330T2317474369_d_img_d18_Bundle/ch2_ohr_ncp_20260330T2317474369_d_img_d18/data/calibrated/20260330/ch2_ohr_ncp_20260330T2317474369_d_img_d18.xml`
- ISIS cube: `data/derived/isis/ohrc/ch2_ohr_ncp_20260330T2317474369_d_img_d18.cub`

Reference image:

- Product: `m188628884lc`
- Instrument: LRO NAC, left camera
- Input label: `data/raw/nac/m188628884lc.xml`
- Input image: `data/raw/nac/m188628884lc.img`
- ISIS cube: `data/derived/isis/nac/m188628884lc.cub`

Observation:

The user verified that a fragment of the OHRC image is present within the `m188628884lc` NAC scene. This pair should be retained as a primary registration test case for checking correspondence, scale handling, illumination differences, and geometric alignment.

Suggested test record:

- Confirm the OHRC fragment can be located in the NAC reference.
- Record the selected image window and approximate overlap bounds.
- Run registration and record match count, inlier ratio, RMSE, and spatial coverage.
- Preserve the original raw products and use derived ISIS cubes for repeatable tests.
