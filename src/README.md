# Solar Estimates source code

A set of Python scripts that use libraries from GDAL and GRASS GIS to aid automation of estimating rooftop solar potential for regions.

`grass_utils.py` - utility functions for dealing with GRASS, includings environment management and setup.

`dsm.py` - functions to handle tiled DSMs, loading the merged raster into GRASS, and calculating slope and aspect rasters.

`solar_irradiance.py` - core functions that use r.sun to calculate solar irradiance for a given time period.

Not yet implemented/added:
- loading of building outlines shapefile
- cropping of irradiance raster to building outlines
- table(?) output of final results
- example code workflow using above scripts
