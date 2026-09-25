# Problem Statement ID26166

## Title

Multi-modal, Sun angle and scale invariant image correspondence using Chandrayaan-2 optical images (OHRC, TMC and IIRS)

## Organization

Indian Space Research Organisation (ISRO)

## Department

Department of Space / Indian Space Research Organisation

## Category

Software

## Theme

Space Technology

## Background

Image registration is the process of aligning two or more images of the same scene taken at different times, from different viewpoints, or by different sensors into a common coordinate system.

It has two main components:

- **Source image (moving):** The image that is geometrically transformed to align with the reference image.
- **Reference image (fixed):** The target image about which the source image is geometrically transformed.

## Description

The registration of lunar images involves finding match points between source and reference images and aligning the source image with the reference image.

## Key challenges

### Illumination variation

Changes in sun azimuth and elevation alter surface lighting conditions and affect the appearance of lunar surface features, making them difficult to correlate.

### Viewpoint variation

Different camera positions and orientations introduce geometric distortions. Features may appear shifted, scaled, rotated, or perspective-distorted depending on the observing angle.

### Scale variation

Lunar imaging missions operate at different altitudes and spatial resolutions, creating potentially large scale ratios between images.

## Expected solution

Develop a generic software solution for finding correspondences between Chandrayaan-2 optical images and lunar reference images, achieving sub-pixel accuracy for the source image while maintaining a uniform distribution of match points across the images.

Expected outputs include:

- Software and registered products with corresponding match points.
- Evaluation metrics such as:
  - RMSE
  - Inlier match count
  - Inlier ratio
  - Other relevant registration-quality measures

## Mentors

- **Sri. Rohit Mishra:** [rohitmishra@sac.isro.gov.in](mailto:rohitmishra@sac.isro.gov.in)
- **Sri. Abdullah Suhail Ayyub Zinjani:** [abdul@sac.isro.gov.in](mailto:abdul@sac.isro.gov.in)
- **Sri. K Suresh:** [ksuresh@sac.isro.gov.in](mailto:ksuresh@sac.isro.gov.in)

## Dataset links

Specific dataset links will be provided. Current references include:

- **Chandrayaan-2 orbiter optical payload:** OHRC, TMC-2, and IIRS lunar images
  - [Chandrayaan-2 data portal](https://chmapbrowse.issdc.gov.in/)
- **Reference imagery:** LRO NAC images
  - [LRO NAC downloads](https://lroc.im-ldi.com/images/downloads/)
  - [LROC QuickMap](https://quickmap.lroc.im-ldi.com/)
- **Additional reference imagery:** SELENE images

## Related link

[SIH 2026 problem statement](https://www.sih.gov.in/sih2026PS)

## Contact information

No additional contact information was provided.
