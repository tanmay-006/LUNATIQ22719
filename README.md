# Lunar Image Registration

Research workspace for illumination-aware registration between Chandrayaan-2 OHRC imagery and LRO NAC reference imagery.

## Structure

- `docs/` - problem statement, architecture, and registration design notes
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

The original datasets are intentionally kept outside the Python source tree because they are large and are not application code.
