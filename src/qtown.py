# This is example code intended to demonstrate how to use the functions in the lib/ directory
# to estimate solar irradiance for a provided digital surface model.

from lib.building_outlines import (
    calculate_outline_raster,
    export_final_raster,
    load_building_outlines,
    remove_masks,
)
from lib.dsm import (
    calculate_slope_aspect_rasters,
    load_virtual_raster_into_grass,
    merge_rasters,
)
from lib.grass_utils import setup_grass
from lib.solar_irradiance import calculate_solar_irradiance_interpolated
from lib.stats import create_stats

# DSM data is usually tiled and contains multiple GeoTIFFs. There is an example shotover-country.zip
# file in the data/ directory that can be unzipped to provide example data.
dsm_data_glob = "data/shotover_country/*.tif"

# Directory containing building outline shapefiles.
building_outline_dir = "data/queenstown_lakes_building_outlines"

# Used for descriptive filenames.
area_name = "shotover_country"
building_outline_name = "queenstown_lakes_buildings"

# Set up GRASS to be scriptable via Python. Note that this path will vary based on OS and installation method. The
# path below is for a MacOS installation using the .dmg installer.
# (see: https://cmbarton.github.io/grass-mac/download/#installation-tips)
gscript, Module = setup_grass(gisbase="/Applications/GRASS-8.4.app/Contents/Resources")

# Main workflow. Refer to the docstrings in the respective functions for more information.

remove_masks(grass_module=Module)

merged_virtual_raster = merge_rasters(dsm_file_glob=dsm_data_glob, area_name=area_name)

virtual_raster = load_virtual_raster_into_grass(
    input_vrt=merged_virtual_raster, output_name=f"{area_name}_dsm", grass_module=Module
)

aspect, slope = calculate_slope_aspect_rasters(dsm=virtual_raster, grass_module=Module)

days = [36, 126, 218, 310]  # solstices and equinoxes

solar_irradiance_annual = calculate_solar_irradiance_interpolated(
    dsm=virtual_raster,
    aspect=aspect,
    slope=slope,
    key_days=days,
    step=1,
    grass_module=Module,
    export=False,
    cleanup=True
)

outlines = load_building_outlines(
    building_outline_dir, building_outline_name, grass_module=Module
)

solar_on_buildings = calculate_outline_raster(
    solar_irradiance_raster=solar_irradiance_annual,
    building_vector=outlines,
    output_name="solar_on_buildings",
    grass_module=Module,
)

final_raster = export_final_raster(
    raster_name=solar_on_buildings,
    output_tif=f"{area_name}_solar_irradiance_on_buildings.tif",
    grass_module=Module,
)

create_stats(
    area=area_name,
    building_outlines=outlines,
    rooftop_raster=solar_on_buildings,
    output_csv=True,
    grass_module=Module,
)
