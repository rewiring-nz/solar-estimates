# This is example code intended to demonstrate how to use the functions in the lib/ directory
# to estimate solar irradiance for a provided digital surface model.

from lib.dsm import calculate_slope_aspect_rasters, load_raster_into_grass, merge_rasters
from lib.grass_utils import setup_grass
from lib.solar_irradiance import calculate_solar_irradiance_range

# DSM data is usually tiled and contains multiple GeoTIFFs. There is an example shotover-country.zip
# file in the data/ directory that can be unzipped to provide example data.
dsm_data_glob = "data/shotover-country/*.tif"

# Used for descriptive filenames.
area_name = "shotover-country"

# Set up GRASS to be scriptable via Python. Note that this path will vary based on OS and installation method. The
# path below is for a MacOS installation using the .dmg installer.
# (see: https://cmbarton.github.io/grass-mac/download/#installation-tips)
gscript, Module = setup_grass(gisbase="/Applications/GRASS-8.4.app/Contents/Resources")

# Main workflow. Refer to the docstrings in the respective functions for more information.

merged_raster, merged_raster_fname = merge_rasters(
    dsm_file_glob=dsm_data_glob,
    area_name=area_name
)

load_raster_into_grass(
    input_tif=merged_raster_fname,
    output_name=merged_raster,
    grass_module=Module)

aspect, slope = calculate_slope_aspect_rasters(
    dsm=merged_raster,
    grass_module=Module)

calculate_solar_irradiance_range(
    dsm=merged_raster,
    aspect=aspect,
    slope=slope,
    days=range(172, 174),
    step=1,
    grass_module=Module,
    cleanup=True
)
