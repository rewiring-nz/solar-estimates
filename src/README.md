# Solar Estimates source code

A set of Python scripts that use libraries from GDAL and GRASS GIS to aid automation of estimating rooftop solar potential for regions.

`grass_utils.py` - utility functions for dealing with GRASS, including environment management and setup.

`dsm.py` - functions to handle tiled DSMs, loading the merged raster into GRASS, and calculating slope and aspect rasters.

`solar_irradiance.py` - core functions that use r.sun to calculate solar irradiance for a given time period.

`building_outlines.py` - functions to deal with loading building outline shapefiles and using it as a mask to clip rasters.

`linke.py` - interpolation function for monthly Linke turbidity values which are used as part of the r.sun algorithm.

Not yet implemented/added:
- dynamic loading of DSM data from LINZ (see: https://github.com/linz/elevation/blob/master/docs/usage.md)
- output of final results
    - total solar generation for area taking into account:
        - solar panel size/efficiency/capacity
        - install location type e.g. rooftops, carparks, other land area
- compiling GRASS to use GPU-enabled r.sun and creating instructions for it
- investigating parallelisation of r.sun module call within Python

## Requirements
- GDAL
- GRASS GIS

## Conda commands
```bash
# Export a minimal environment file to be able to set up a conda env on other machines.
# Remove the prefix line from this manually as it will refer to an absolute path on local disk
conda env export -n solar-estimates --no-builds --from-history > environment.yml

# Recreate a conda env from file
conda env create -f environment.yml

# Activate a conda env
conda activate solar-estimates
```
