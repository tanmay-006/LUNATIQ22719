# Lunar Image Registration

Research workspace for illumination-aware registration between Chandrayaan-2 OHRC imagery and LRO NAC reference imagery.

## Structure

- `docs/` - problem statement, architecture, and registration design notes
- `docs/verified-test-pairs.md` - user-verified OHRC/NAC correspondence for testing
- `data/raw/ohrc/` - original Chandrayaan-2 OHRC archives and PDS4 products
- `data/raw/nac/` - original LRO NAC PDS products and archives
- `data/derived/isis/` - ISIS cubes and display-ready GeoTIFF products
- `config/isis/` - ISIS project configuration
- `requirements/` - Python dependency sets
- `tools/installers/` - local installation scripts

## ISIS

Activate the installed ISIS environment:

```bash
source /home/tanmay/miniforge3/etc/profile.d/conda.sh
conda activate isis
```

Launch the GUI workbench:

```bash
./launch_isis_gui.sh
```

Choose an OHRC `.xml` label or NAC `.IMG`/`.img` file. The workbench selects
the correct ISIS importer, writes cubes under `data/derived/isis/`, and can
open the result in `qview`. Existing `.cub` and `.tiff` products can also be
opened directly.

Import an OHRC PDS4 product:

```bash
isisimport from=data/raw/ohrc/<product>/.../<product>.xml \
  to=data/derived/isis/ohrc/<product>.cub
```

Open an OHRC cube or GeoTIFF:

```bash
qview data/derived/isis/ohrc/<product>.tiff
```

Import an LRO NAC product using its attached PDS3 label:

```bash
pds2isis from=data/raw/nac/<product>.IMG \
  to=data/derived/isis/nac/<product>.cub
```

Open a NAC cube:

```bash
qview data/derived/isis/nac/<product>.cub
```

Run the registration CLI:

```bash
PYTHONPATH=src python -m lunar_isis_gui.register \
  data/derived/isis/ohrc/source.cub \
  data/derived/isis/nac/reference.cub \
  outputs/
```

The command prints progress and writes `registered.tif`, `matches.csv`, and
`metrics.json` under the output directory. Use `--method auto` to try LoFTR
before falling back to SIFT. For large cubes, `--max-dimension 1024` (the
default) downsamples during GDAL conversion, before pixels are loaded into
Python; this avoids allocating the original multi-gigabyte rasters. Use
`--projection-method auto` to attempt ISIS `cam2map`, or the default
`fallback` for the local affine/phase-correlation approximation. The fallback
is useful for pipeline diagnostics but is not a substitute for camera-model
map projection, so inspect `metrics.json` and the generated match list before
treating a result as scientifically valid. `launch_isis_gui.sh` starts the
graphical workbench; it does not run the registration CLI.

The original datasets are intentionally kept outside the Python source tree because they are large and are not application code.
