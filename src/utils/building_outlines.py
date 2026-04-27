"""
Building outlines utilities for GRASS GIS.

This module contains helper functions to import building footprint vectors into a
GRASS mapset, apply building masks so raster operations affect only building
areas, extract masked raster values into building-specific rasters, and
export final multi-band GeoTIFFs that include computed rasters (for example,
solar irradiance) together with slope and aspect bands.
"""

from pathlib import Path
from typing import Any, Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)


def load_building_outlines(shapefile: str, output_name: str, grass_module: Any) -> str:
    """Import building outlines (vector) from a shapefile into GRASS.

    This uses the `v.in.ogr` GRASS module to import a vector dataset from a
    shapefile into the current GRASS mapset.

    Args:
        shapefile: Path to the directory containing a building footprints shapefile.
        output_name: Name to assign to the vector map inside GRASS.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The GRASS vector name.
    """
    # Import vector into GRASS; overwrite if a vector with the same name exists
    v_in = grass_module("v.in.ogr", input=shapefile, output=output_name, overwrite=True)
    v_in.run()

    return output_name


def buffer_building_outlines(
    vector_name: str, buffer_distance: float, area_name: str, grass_module: Any
) -> str:
    """Create a buffered copy of a building outlines vector in GRASS.

    Uses ``v.buffer`` to expand each building polygon by ``buffer_distance``
    metres, producing a new vector that can be used as a mask so that raster
    operations cover a slightly larger area than the raw footprints.

    Args:
        vector_name: Name of the existing building footprint vector in GRASS.
        buffer_distance: Distance in metres to expand each polygon.
        area_name: Prefix used to build the output vector name.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The GRASS vector name of the buffered output.
    """
    output_name = f"{area_name}_buildings_buffered"
    v_buffer = grass_module(
        "v.buffer",
        input=vector_name,
        output=output_name,
        distance=buffer_distance,
        overwrite=True,
    )
    v_buffer.run()
    return output_name


def apply_building_mask(building_vector: str, grass_module: Any) -> None:
    """Apply a raster mask based on building outlines.

    The mask created by `r.mask` restricts subsequent raster operations to the
    area covered by the given vector. Typical workflows call this beforehand to copy
    or compute values only for buildings.

    Args:
        building_vector: Name of the building footprint vector in GRASS.
        output_name: Friendly name returned by the function (no effect on mask).
        grass_module: The GRASS Python scripting Module class.

    Returns:
        None
    """
    # Create a raster mask from the vector; overwrite any existing mask
    r_mask = grass_module("r.mask", vector=building_vector, overwrite=True)
    r_mask.run()


def remove_masks(grass_module: Any) -> None:
    """Remove any active raster mask(s) in the current GRASS session.

    This helper attempts to reset raster masking by calling `r.mask -r`.

    Args:
        grass_module: The GRASS Python scripting Module class.

    Returns:
        None

    Raises:
        Exception: if removing the mask encounters an error.
    """
    try:
        # The 'r' flag removes the active mask
        r_mask = grass_module("r.mask", flags="r")
        r_mask.run()
    except Exception as e:  # Don't break the workflow if it can't remove the mask
        logger.warning("Error removing GRASS mask: %s", e)


def calculate_outline_raster(
    solar_irradiance_raster: str,
    building_vector: str,
    output_name: str,
    grass_module: Any,
) -> str:
    """Create a raster containing values only for building outlines.

    Args:
        solar_irradiance_raster: Name of the solar irradiance raster to be masked.
        building_vector: Name of the building footprint vector to use for masking.
        output_name: Name to assign to the resulting building-only raster.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The GRASS raster name.
    """
    # Apply mask using the building vector
    apply_building_mask(building_vector, grass_module=grass_module)

    # Copy values from the source raster into the masked output raster
    r_mapcalc = grass_module(
        "r.mapcalc",
        expression=f"{output_name} = {solar_irradiance_raster}",
        overwrite=True,
    )
    r_mapcalc.run()

    return output_name


def export_final_raster(
    raster_name: str,
    slope: str,
    aspect: str,
    output_tif: str,
    grass_module: Any,
    output_dir: Optional[Path] = None,
) -> str:
    """Export a multi-band GeoTIFF containing raster, slope, and aspect.

    This function:
      - Creates an imagery group containing the three rasters using `i.group`.
      - Calls `r.out.gdal` to export the group as a multi-band GeoTIFF.
      - Removes the temporary imagery group.

    Args:
        raster_name: Name of the primary raster to export (e.g., building-only GHI).
        slope: Name of the slope raster to include as a band.
        aspect: Name of the aspect raster to include as a band.
        output_tif: Filename (or path) for the output GeoTIFF file to create.
            If output_dir is provided, the file is written inside that directory.
        grass_module: The GRASS Python scripting Module class.
        output_dir: Optional directory in which to write the output file.
            When provided, output_tif is treated as a filename and joined with
            output_dir to form the full path.

    Returns:
        The full `output_tif` path for convenience.
    """
    # Create a temporary imagery group containing the three rasters. This groups
    # the rasters into a single multi-band dataset.
    group_name = f"{raster_name}_group"
    i_group = grass_module(
        "i.group",
        group=group_name,
        input=f"{raster_name},{slope},{aspect}",
    )
    i_group.run()

    # Resolve the output path, writing into output_dir when provided.
    if output_dir is not None:
        output_path = str(Path(output_dir) / output_tif)
    else:
        output_path = output_tif

    # TFW = World File containing georeferencing info
    # LZW = Lempel-Ziv-Welch lossless compression algorithm
    r_out_multiband = grass_module(
        "r.out.gdal",
        input=group_name,
        output=output_path,
        format="GTiff",
        createopt="TFW=YES,COMPRESS=LZW",
        overwrite=True,
    )
    r_out_multiband.run()

    # Clean up the temporary group to avoid leaving workspace state behind.
    g_remove = grass_module(
        "g.remove",
        type="group",
        name=group_name,
        flags="f",  # force removal without extra prompts
    )
    g_remove.run()

    return output_path
