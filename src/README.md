# Solar potential estimation pipeline

A set of Python scripts that use libraries from GDAL and GRASS GIS to aid automation of estimating rooftop solar potential for regions.

`grass_utils.py` - utility functions for dealing with GRASS, including environment management and setup.

`dsm.py` - functions to handle tiled DSMs, loading the merged raster into GRASS, and calculating slope and aspect rasters.

`solar_irradiance.py` - core functions that use r.sun to calculate solar irradiance for a given time period.

`building_outlines.py` - functions to deal with loading building outline shapefiles and using it as a mask to clip rasters.

`linke.py` - interpolation function for monthly Linke turbidity values which are used as part of the r.sun algorithm.

`wrf.py` - functions to load, clip, and resample WRF (Weather Research and Forecasting) netCDF data to incorporate measured solar radiation.

`stats.py` - creates a GeoPackage and optional CSV file of solar irradiance statistics for each building polygon.

Not yet implemented/added:
- dynamic loading of DSM data from LINZ (see: https://github.com/linz/elevation/blob/master/docs/usage.md)
- weather profiles as a CLI argument (e.g. worst-case winter)
- output of final results
    - total solar generation for area taking into account:
        - solar panel size/efficiency/capacity
        - install location type e.g. rooftops, carparks, other land area
- compiling GRASS to use GPU-enabled r.sun and creating instructions for it
- investigating parallelisation of r.sun module call within Python

## Installation

### GRASS on macOS

*This has been tested for GRASS 8.4.1. Apple ARM on MacOS Sequoia 15.7.1.*

Download and install GRASS following these instructions: https://cmbarton.github.io/grass-mac/download/#installation-tips

When trying to open the GRASS app, you may get the warning `GRASS is Damaged and Can’t Be Opened. You Should Move It To The Trash.`. Although [the documentation says](https://cmbarton.github.io/grass-mac/download/#important-apple-security-block-and-workaround-for-grass-versions-downloaded-in-2024-and-prior-to-9-january-2025) that this should be resolved as of 9 Jan 2025, this may still be the case for you.

To get around this, go to `Applications`, right click the GRASS app and click `Open`. It will block it, so cancel. Then go to your Mac's `System Settings` > `Privacy & Security` > scroll down to the `Security` section at the bottom. Assuming GRASS was the last app you tried to open, there should be a message about GRASS being blocked, with an `Open Anyway` button next to it. Click this, and it will allow your Mac to open GRASS from now on. See [this screenshot](https://support.apple.com/en-nz/102445#openanyway) for an example.

### Installing GDAL on macOS

Use Homebrew (`brew install gdal`) as per the official instructions: https://gdal.org/en/stable/download.html#mac-os

Ensure the GDAL used is the one installed via Homebrew:

```bash
> which gdalinfo
/opt/homebrew/bin/gdalinfo
```

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

### Installing QGIS (optional)

This is a GUI for exploring the geopackage data that is created by our pipeline, including running queries over it like you would with SQL. GRASS can visualise geopackages as well, but QGIS is a bit more user friendly and has more functionality.

1. [Download QGIS from the website]([url](https://qgis.org/download/))
1. Download the Shotover Country winter geopackage file from [this Google Drive folder](https://drive.google.com/drive/folders/18qfvIaRy2X5fYjm-V0amQPvnxvDS_CAS).
1. Open QGIS and go to Layer > Data Source Manager. This will open a dialog box.
1. Select the `Geopackage` option in the sidebar of the dialog box.
1. Under `Connections` click `New`. Select the `.gpkg` file you downloaded from Google Drive and click `Add`. This will add the building outlines to your QGIS viewer window.
1. In the main window browser sidebar, you can select `XYZ Tiles > OpenStreetMap`, right click and `Add Layer to Project`. Drag this layer under the `building_stats` layer to show the building outlines overlaid on top of the OpenStreetMap view.

[More examples of how to use to calculate and visualise things to be added!]

## Example usage

This repo includes some example data in the `data/` folder. You can use these to try out the pipeline.

```bash
# See all available options
python3 pipeline.py --help

# Run the pipeline using all defaults
python3 pipeline.py

# Run the pipeline specifying some arguments
python3 pipeline.py \
  --dsm-glob "data/shotover_country/*.tif" \
  --building-dir "data/queenstown_lakes_building_outlines" \
  --area-name "shotover_country" \
  --building-layer-name "queenstown_lakes_buildings" \
  --output-prefix "my_solar_analysis" \
  --time-step 0.5 \
  --export-rasters

# Run the pipeline with WRF data
python3 pipeline.py \
  --dsm-glob "data/shotover_country/*.tif" \
  --building-dir "data/queenstown_lakes_building_outlines" \
  --area-name "shotover_country" \
  --building-layer-name "queenstown_lakes_buildings" \
  --output-prefix "my_solar_analysis" \
  --time-step 0.5 \
  --wrf-file "data/swdown_2016-2020_daily_mean_doy.nc" \
  --source-crs "EPSG:4326" \
  --target-crs "EPSG:2193" \
  --export-rasters
```

### Command-line arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--dsm-glob` | No | `data/shotover_country/*.tif` | Glob pattern for DSM GeoTIFF files |
| `--building-dir` | No | `data/queenstown_lakes_building_outlines` | Directory containing building outline shapefiles |
| `--area-name` | No | `shotover_country` | Descriptive name for the area (used in filenames) |
| `--building-layer-name` | No | `queenstown_lakes_buildings` | Name of the building outline layer |
| `--grass-base` | No | Auto-detected | Path to GRASS GIS installation |
| `--output-prefix` | No | `solar_on_buildings` | Prefix for output files |
| `--max-slope` | No | `45.0` | Maximum slope in degrees for filtering |
| `--key-days` | No | `1 7` | Day numbers for solar irradiance interpolation |
| `--time-step` | No | `1.0` | Time step in decimal hours for calculations |
| `--export-rasters` | No | `False` | Export all rasters as GeoTIFFs |
| `--wrf-file` | No | - | Path to WRF NetCDF file for measured radiation data |
| `--source-crs` | No | `EPSG:4326` | Source CRS for WRF data |
| `--target-crs` | No | `EPSG:2193` | Target CRS for WRF reprojection |

### Note on GRASS GIS base paths by platform

Currently, the pipeline will attempt to auto-detect the operating system and set the GRASS base path accordingly. If this fails, you can manually specify the path using the `--grass-base` argument.

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

2. **GeoPackage** - `{area_name}_building_stats.gpkg` with building-level solar potential statistics

3. **Statistics CSV** - `{area_name}_building_stats.csv` CSV format for building-level solar potential statistics

4. **GeoTIFFs** (if `--export-rasters` used):
   - `{area_name}_solar_irradiance_on_buildings.tif` - Final solar irradiance on buildings
   - `{dsm}_solar_irradiance_interp.tif` - Interpolated solar irradiance
   - `{dsm}_solar_irradiance_interp_coefficient.tif` - Solar coefficient (when WRF enabled)
   - `{area_name}_wrf_adjusted.tif` - WRF-adjusted radiation (when WRF enabled)
