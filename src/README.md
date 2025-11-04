# Solar potential estimation pipeline

A set of Python scripts that use libraries from GDAL and GRASS GIS to aid automation of estimating rooftop solar potential for regions.

`grass_utils.py` - utility functions for dealing with GRASS, including environment management and setup.

`dsm.py` - functions to handle tiled DSMs, loading the merged raster into GRASS, and calculating slope and aspect rasters.

`solar_irradiance.py` - core functions that use r.sun to calculate solar irradiance for a given time period.

`building_outlines.py` - functions to deal with loading building outline shapefiles and using it as a mask to clip rasters.

`linke.py` - interpolation function for monthly Linke turbidity values which are used as part of the r.sun algorithm.

`stats.py` - creates a GeoPackage and optional CSV file of solar irradiance statistics for each building polygon.

Not yet implemented/added:
- dynamic loading of DSM data from LINZ (see: https://github.com/linz/elevation/blob/master/docs/usage.md)
- output of final results
    - total solar generation for area taking into account:
        - solar panel size/efficiency/capacity
        - install location type e.g. rooftops, carparks, other land area
- compiling GRASS to use GPU-enabled r.sun and creating instructions for it
- investigating parallelisation of r.sun module call within Python

## Installation

### GRASS

Download and install GRASS following these instructions: https://cmbarton.github.io/grass-mac/download/#installation-tips

#### Notes for GRASS on Mac

*This has been tested for GRASS 8.4.1. Apple ARM on MacOS Sequoia 15.7.1.*

When trying to open the GRASS app, you may get the warning `GRASS is Damaged and Can’t Be Opened. You Should Move It To The Trash.`. Although [the documentation says](https://cmbarton.github.io/grass-mac/download/#important-apple-security-block-and-workaround-for-grass-versions-downloaded-in-2024-and-prior-to-9-january-2025) that this should be resolved as of 9 Jan 2025, this may still be the case for you.

To get around this, go to `Applications`, right click the GRASS app and click `Open`. It will block it, so cancel. Then go to your Mac's `System Settings` > `Privacy & Security` > scroll down to the `Security` section at the bottom. Assuming GRASS was the last app you tried to open, there should be a message about GRASS being blocked, with an `Open Anyway` button next to it. Click this, and it will allow your Mac to open GRASS from now on. See [this screenshot](https://support.apple.com/en-nz/102445#openanyway) for an example.

### Python packages

Solar Estimates uses a `pyproject.toml` file to manage dependencies, which is supported by various dependency management
solutions such as Poetry, pip, and uv.

The following example uses `pip` and `venv`. Ensure you are in the `src/` directory before running the commands.

```bash
# Create a virtual environment
python3 -m venv .venv

# Activate the env
source .venv/bin/activate

# Install dependencies
pip install .
```

## Usage

This repo includes some example data in the `data/` folder. You can use these to try out the pipeline.

```bash
# Run the example
python3 example.py

# Run the pipeline (same as example, base usage)
python3 pipeline.py

# See all available options
python3 pipeline.py --help

# Run the pipeline (including examples for all optional arguments)
python3 pipeline.py \
  --dsm-glob "data/shotover_country/*.tif" \
  --building-dir "data/queenstown_lakes_building_outlines" \
  --area-name "shotover_country" \
  --building-layer-name "queenstown_lakes_buildings" \
  --grass-base "/Applications/GRASS-8.4.app/Contents/Resources" \
  --output-prefix "my_solar_analysis" \
  --max-slope 30.0 \
  --key-days 152 172 243 \
  --time-step 0.5 \
  --export-raster

# Deactivate the env once you're done
deactivate
```

### Command-line arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--dsm-glob` | Yes | - | Glob glob for DSM GeoTIFF files |
| `--building-dir` | Yes | - | Directory containing building outline shapefiles |
| `--area-name` | Yes | - | Descriptive name for the area (used in filenames) |
| `--building-layer-name` | Yes | - | Name of the building outline layer |
| `--grass-base` | Yes | - | Path to GRASS GIS installation |
| `--output-prefix` | No | `solar_on_buildings` | Prefix for output files |
| `--max-slope` | No | `45.0` | Maximum slope in degrees for filtering |
| `--key-days` | No | `1 79 172 266 357 365` | Day numbers for solar irradiance interpolation |
| `--time-step` | No | `1.0` | Time step in decimal hours for calculations |
| `--export-raster` | No | `False` | Export final raster as GeoTIFF |

### GRASS base paths by platform

- **macOS (DMG installer)**: `/Applications/GRASS-8.4.app/Contents/Resources`
- **Linux (apt)**: TBC
- **Windows**: TBC

### Linting & formatting

We use [Ruff](https://github.com/astral-sh/ruff) with default configs.

```bash
# To lint:
ruff check .

# To format:
ruff format .
```

## Outputs

The pipeline generates:

1. **GRASS rasters** (stored in GRASS database):
   - `{area_name}_dsm` - Digital surface model
   - `{output_prefix}` - Solar irradiance on buildings
   - `{output_prefix}_filtered` - Filtered by slope

2. **Statistics CSV** - Building-level solar potential statistics (see `stats.py`)

3. **GeoTIFF** (if `--export-raster` used):
   - `{area_name}_solar_irradiance_on_buildings.tif`
