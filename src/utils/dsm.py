"""
Digital Surface Model (DSM) utilities.

This module contains helper functions for working with DSM rasters, using
GDAL and GRASS GIS.

High-level responsibilities:
- Attaching virtual rasters (VRT) to GRASS as external rasters.
- Merging tiled DSM GeoTIFFs into a single VRT (optionally can be translated
  to a GeoTIFF).
- Calculating slope and aspect rasters from a DSM.
- Filtering rasters.
- Pre-calculating horizon rasters for solar shading optimisation.
"""

import glob
from pathlib import Path
from typing import Any, Optional, Tuple
from osgeo import gdal


def merge_rasters(dsm_file_glob: str, area_name: str, output_dir: Path) -> str:
    """Merge tiled DSM files into a single VRT using GDAL.

    This function discovers DSM tiles using a glob pattern, builds a GDAL VRT
    (virtual raster) that mosaics them together, and returns the VRT filename.
    The function intentionally leaves the VRT on disk instead of translating to
    a final GeoTIFF so callers can decide on translation parameters (compression,
    data type, nodata handling) or feed the VRT directly to GRASS via `r.external`.

    Args:
        dsm_file_glob: Glob pattern matching input DSM tiles.
        area_name: Prefix to use for the generated VRT filename.

    Returns:
        The path to the generated VRT file.

    Raises:
        FileNotFoundError: If the glob pattern matches no files.
        RuntimeError: If GDAL fails to create the VRT for any reason.
    """
    # Find input files using the glob pattern
    dsm_files = glob.glob(dsm_file_glob)
    if not dsm_files:
        raise FileNotFoundError(f"🚫 No files found for pattern: {dsm_file_glob}")

    # Build a Virtual Raster (VRT). Use nearest-neighbor resampling by default
    try:
        vrt_options = gdal.BuildVRTOptions(resampleAlg=gdal.GRA_NearestNeighbour)
        vrt_path = f"{str(output_dir)}/{area_name}_merged.vrt"
        gdal.BuildVRT(vrt_path, dsm_files, options=vrt_options)
    except Exception as e:
        # Propagate any errors
        raise RuntimeError(
            f"🚫 Failed to build VRT from {len(dsm_files)} files: {e}"
        ) from e

    # Return the VRT path
    return vrt_path


def load_virtual_raster_into_grass(
    input_vrt: str, output_name: str, grass_module: Any
) -> str:
    """Attach a VRT (virtual raster) to GRASS using `r.external` and set region.

    Using `r.external` avoids copying data into the GRASS database; the VRT is
    referenced externally which is faster and uses no additional disk space.

    Args:
        input_vrt: Path to the VRT file on disk.
        output_name: The raster name to expose inside GRASS.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The GRASS raster name.
    """
    # Register the VRT as an external raster
    r_external = grass_module(
        "r.external", input=input_vrt, output=output_name, band=1, overwrite=True
    )
    r_external.run()

    # Print and set the region to match the attached raster
    g_region = grass_module("g.region", raster=output_name, flags="p")
    g_region.run()

    return output_name


def calculate_slope_aspect_rasters(dsm: str, grass_module: Any) -> Tuple[str, str]:
    """Compute slope and aspect rasters from a DSM using GRASS `r.slope.aspect`.

    Args:
        dsm: Name of the DSM raster in the GRASS mapset.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        A tuple `(aspect_raster_name, slope_raster_name)`.
    """
    r_slope_aspect = grass_module(
        "r.slope.aspect",
        elevation=dsm,
        slope=f"{dsm}_slope",
        aspect=f"{dsm}_aspect",
        format="degrees",
        precision="FCELL",
        a=True,  # compute aspect
        nprocs=16,
        overwrite=True,
    )
    r_slope_aspect.run()

    return f"{dsm}_aspect", f"{dsm}_slope"


def filter_raster_by_slope(
    input_raster: str,
    slope_raster: str,
    max_slope_degrees: float,
    output_name: str,
    grass_module: Any,
) -> str:
    """Filter `input_raster` to only keep pixels where slope <= max_slope_degrees.

    This function uses a `r.mapcalc` expression to produce a masked
    raster where any pixel with slope greater than `max_slope_degrees` is set
    to NULL (GRASS NULL) and valid pixels retain their original value.

    Example expression used:
        output = if(slope_raster <= max_slope_degrees, input_raster, null())

    Args:
        input_raster: GRASS raster name containing the values to be filtered.
        slope_raster: GRASS raster name containing slope in degrees.
        max_slope_degrees: Maximum allowed slope (inclusive). Pixels with slope
            greater than this value will be masked to NULL.
        output_name: Name for the output raster.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The name of the output raster.
    """
    # Build and run the r.mapcalc expression to mask out steep slopes
    expression = (
        f"{output_name} = if({slope_raster} <= {max_slope_degrees}, "
        f"{input_raster}, null())"
    )
    r_mapcalc = grass_module("r.mapcalc", expression=expression, overwrite=True)
    r_mapcalc.run()

    return output_name


def calculate_horizon_raster(
    elevation: str,
    output_name: str,
    grass_module: Any,
    buffer_distance: float = 30.0,
    start_azimuth: float = 315.0,
    end_azimuth: float = 135.0,
    azimuth_steps: int = 18,
) -> str:
    """Pre-calculate a horizon raster using GRASS `r.horizon`.

    Computes the maximum horizon elevation angle (in degrees above horizontal)
    for each cell in the given direction range.  By restricting the azimuth
    range to the northern arc (315°→135°), only those directions from which the
    sun can reach New Zealand are calculated, reducing computation by ~50 %
    compared to a full 360° sweep.

    Args:
        elevation: Name of the input elevation raster (DSM or DEM) in GRASS.
        output_name: Base name for the output horizon raster(s).
        grass_module: The GRASS Python scripting Module class.
        buffer_distance: Search radius in metres.  Use a small value (e.g. 30 m)
            for a 1 m DSM to capture local building/tree shading, or a large
            value (e.g. 10 000 m) for an 8 m DEM to capture distant mountain
            shading.  Defaults to 30.
        start_azimuth: Starting azimuth in degrees (clockwise from north).
            Defaults to 315° (NW), the beginning of the NZ northern solar arc.
        end_azimuth: Ending azimuth in degrees (clockwise from north).
            Defaults to 135° (SE), the end of the NZ northern solar arc.
        azimuth_steps: Number of discrete azimuth directions to calculate
            within [start_azimuth, end_azimuth].  Defaults to 18 (≈10° spacing
            over the ~180° NZ northern arc).

    Returns:
        The base name of the output horizon raster (same as ``output_name``).
    """
    step_size = ((end_azimuth - start_azimuth) % 360) / azimuth_steps
    grass_module(
        "r.horizon",
        elevation=elevation,
        step=step_size,
        bufferzone=buffer_distance,
        output=output_name,
        start=start_azimuth,
        end=end_azimuth,
        overwrite=True,
    ).run()

    return output_name


def combine_horizon_rasters(
    local_horizon: str,
    regional_horizon: str,
    output_name: str,
    grass_module: Any,
) -> str:
    """Combine local and regional horizon rasters by taking the maximum angle.

    For each cell the combined horizon is the higher of the two elevation
    angles, i.e. the obstruction that blocks more sunlight wins.  The local
    horizon (derived from a high-resolution DSM) captures buildings and trees,
    while the regional horizon (derived from a coarser DEM) captures distant
    mountain ranges.

    Args:
        local_horizon: GRASS raster name for the local horizon (from DSM).
        regional_horizon: GRASS raster name for the regional horizon (from DEM).
        output_name: Name for the combined output raster.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The name of the combined horizon raster (same as ``output_name``).
    """
    expression = f"{output_name} = max({local_horizon}, {regional_horizon})"
    grass_module("r.mapcalc", expression=expression, overwrite=True).run()

    return output_name
