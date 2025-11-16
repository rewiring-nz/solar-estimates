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
from utils.solar_irradiance import calculate_solar_irradiance_interpolated
from utils.stats import create_stats

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
    # Standard path for Ubuntu systems where GRASS 8.3 is installed via apt.
    # NOTE: If your GRASS version is different (e.g., 8.2), you may need to update 'grass83' here.
    gisbase = "/usr/lib/grass83"
else:
    # Raise an error for other operating systems or if the path is unknown
    raise EnvironmentError(
        f"Unsupported operating system ({platform.system()}) or missing GRASS GIS installation path. "
        f"Please manually define the 'gisbase' variable."
    )

gscript, Module = setup_grass(gisbase=gisbase)

# --- Main Workflow ---
# Refer to the docstrings in the respective functions for more information.

remove_masks(grass_module=Module)

merged_virtual_raster = merge_rasters(dsm_file_glob=dsm_data_glob, area_name=area_name)

virtual_raster = load_virtual_raster_into_grass(
    input_vrt=merged_virtual_raster, output_name=f"{area_name}_dsm", grass_module=Module
)

aspect, slope = calculate_slope_aspect_rasters(dsm=virtual_raster, grass_module=Module)

# Simple one-week calculation
days = [1, 7]

# Annual using solstices and equinoxes as key days for interpolation
# days = [1, 79, 172, 266, 357, 365]

# Winter only with winter solstice
# days = [152, 172, 243]

# Summer only with summer solstice
# days = [335, 357, 59]

solar_irradiance = calculate_solar_irradiance_interpolated(
    dsm=virtual_raster,
    aspect=aspect,
    slope=slope,
    key_days=days,
    step=1,
    grass_module=Module,
    export=False,
    cleanup=True,
)

outlines = load_building_outlines(
    building_outline_dir, building_outline_name, grass_module=Module
)

solar_on_buildings = calculate_outline_raster(
    solar_irradiance_raster=solar_irradiance,
    building_vector=outlines,
    output_name="solar_on_buildings",
    grass_module=Module,
)

solar_on_buildings_filtered = filter_raster_by_slope(
    input_raster=solar_on_buildings,
    slope_raster=slope,
    max_slope_degrees=45,
    output_name="solar_on_buildings_filtered",
    grass_module=Module,
)

# This can be used to export a raster of solar irradiance on buildings if required
#
# final_raster = export_final_raster(
#     raster_name=solar_on_buildings_filtered,
#     slope=slope,
#     aspect=aspect,
#     output_tif=f"{area_name}_solar_irradiance_on_buildings.tif",
#     grass_module=Module,
# )

create_stats(
    area=area_name,
    building_outlines=outlines,
    rooftop_raster="solar_on_buildings_filtered",
    output_csv=True,
    grass_module=Module,
)
