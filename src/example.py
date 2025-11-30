# This is example code intended to demonstrate how to use the functions in the lib/ directory
# to estimate solar irradiance for a provided digital surface model.

import platform  # Import platform module for OS detection

from utils.building_outlines import (
    calculate_outline_raster,
    export_final_raster,
    load_building_outlines,
    remove_masks,
)
from utils.dsm import (
    calculate_slope_aspect_rasters,
    filter_raster_by_slope,
    load_virtual_raster_into_grass,
    merge_rasters,
)
from utils.grass_utils import setup_grass
from utils.solar_irradiance import (
    calculate_solar_coefficient,
    calculate_solar_irradiance_interpolated,
)
from utils.stats import create_stats
from utils.wrf import (
    calculate_wrf_on_buildings,
    cleanup_wrf_intermediates,
    process_wrf_for_grass,
)

# --- Configuration ---

# DSM data is usually tiled and contains multiple GeoTIFFs. There is example data in the data/ directory.
dsm_data_glob = "data/shotover_country/*.tif"

# Directory containing building outline shapefiles.
building_outline_dir = "data/queenstown_lakes_building_outlines"

# Used for descriptive filenames.
area_name = "shotover_country"
building_outline_name = "queenstown_lakes_buildings"

# --- GRASS GIS Setup for Cross-Platform Resilience ---

# Set up GRASS 'gisbase' path based on OS.
# Todo: Update this to be less brittle, and move logic into grass-utils.py

if platform.system() == "Darwin":  # macOS
    # Standard path for macOS installations using the GRASS 8.x DMG installer
    gisbase = "/Applications/GRASS-8.4.app/Contents/Resources"
elif platform.system() == "Linux":  # Ubuntu/Linux
    # Standard path for Ubuntu systems where GRASS 8.4 is installed via apt.
    # NOTE: If your GRASS version is different (e.g., 8.2), you may need to update 'grass84' here.
    gisbase = "/usr/lib/grass84"
else:
    # Raise an error for other operating systems or if the path is unknown
    raise EnvironmentError(
        f"Unsupported operating system ({platform.system()}) or missing GRASS GIS installation path. "
        f"Please manually define the 'gisbase' variable."
    )

gscript, Module = setup_grass(gisbase=gisbase)

# --- Main Workflow ---
# Refer to the docstrings in the respective functions for more information.

# Remove any potential existing masks from previous runs.
remove_masks(grass_module=Module)

# Merge DSM tiles into a single virtual raster (VRT) using GDAL.
merged_virtual_raster = merge_rasters(dsm_file_glob=dsm_data_glob, area_name=area_name)

# Load the merged virtual raster into GRASS.
virtual_raster = load_virtual_raster_into_grass(
    input_vrt=merged_virtual_raster, output_name=f"{area_name}_dsm", grass_module=Module
)

# Calculate slope and aspect rasters from the DSM.
aspect, slope = calculate_slope_aspect_rasters(dsm=virtual_raster, grass_module=Module)

# Simple one-week calculation
days = [1, 7]

# Annual using solstices and equinoxes as key days for interpolation
# days = [1, 79, 172, 266, 357, 365]

# Winter only with winter solstice
# days = [152, 172, 243]

# Calculate total solar irradiance via interpolation for the supplied period.
solar_irradiance = calculate_solar_irradiance_interpolated(
    dsm=virtual_raster,
    aspect=aspect,
    slope=slope,
    key_days=days,
    step=0.05,
    grass_module=Module,
    export=True,
    cleanup=True,
)

# Create normalized coefficient raster (0-1) from irradiance values.
solar_coefficient = calculate_solar_coefficient(
    irradiance_raster=solar_irradiance,
    grass_module=Module,
    export=True,
)

# Load building outlines into GRASS.
outlines = load_building_outlines(
    building_outline_dir, building_outline_name, grass_module=Module
)

# Clip solar irradiance to building outlines.
solar_on_buildings = calculate_outline_raster(
    solar_irradiance_raster=solar_irradiance,
    building_vector=outlines,
    output_name="solar_on_buildings",
    grass_module=Module,
)

# Filter 1: remove pixels that exceed a certain slope.
solar_on_buildings_filtered = filter_raster_by_slope(
    input_raster=solar_on_buildings,
    slope_raster=slope,
    max_slope_degrees=45,
    output_name="solar_on_buildings_filtered",
    grass_module=Module,
)

# Process WRF data
wrf_day_rasters, wrf_summed = process_wrf_for_grass(
    nc_file_path="data/swdown_2016-2020_daily_mean_doy.nc",
    output_prefix="wrf_swdown",
    grass_module=Module,
    source_crs="EPSG:4326",
    target_crs="EPSG:2193",
    days=days,
    clip_to_raster=virtual_raster,
    print_diagnostics=False,
)

# Create raster for WRF clipped to building outlines.
wrf_on_buildings = calculate_wrf_on_buildings(
    wrf_summed_raster=wrf_summed,
    building_vector=outlines,
    output_name="wrf_on_buildings",
    grass_module=Module,
)

# Clean up intermediate WRF rasters (day rasters and summed raster)
cleanup_wrf_intermediates(wrf_day_rasters, wrf_summed, Module)

# Adjust WRF values by solar coefficient (multiply WRF by coefficient percentage)
wrf_adjusted = "wrf_on_buildings_adjusted"
mapcalc_expr = f"{wrf_adjusted} = {wrf_on_buildings} * {solar_coefficient}"
Module("r.mapcalc", expression=mapcalc_expr, overwrite=True).run()

# Export the adjusted WRF raster
Module(
    "r.out.gdal",
    input=wrf_adjusted,
    output=f"{area_name}_wrf_adjusted.tif",
    format="GTiff",
    createopt="TFW=YES,COMPRESS=LZW",
    overwrite=True,
).run()

# This can be used to export a raster of solar irradiance on buildings if required
#
final_raster = export_final_raster(
    raster_name=solar_on_buildings_filtered,
    slope=slope,
    aspect=aspect,
    output_tif=f"{area_name}_solar_irradiance_on_buildings.tif",
    grass_module=Module,
)

# Calculate statistics and create a GeoPackage and optional CSV.
create_stats(
    area=area_name,
    building_outlines=outlines,
    rooftop_raster="solar_on_buildings_filtered",
    wrf_raster=wrf_adjusted,
    output_csv=True,
    grass_module=Module,
)
