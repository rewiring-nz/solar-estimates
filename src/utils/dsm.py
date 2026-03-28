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
- Calculating horizon rasters using r.horizon.
"""

import glob
from pathlib import Path
from subprocess import PIPE
from typing import Any, List, Optional, Tuple
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


def calculate_horizon_raster(
    elevation: str,
    output_basename: str,
    step: float,
    start_azimuth: float = 0.0,
    end_azimuth: float = 360.0,
    max_distance: Optional[float] = None,
    grass_module: Any = None,
) -> str:
    """Calculate horizon angle rasters using GRASS ``r.horizon``.

    ``r.horizon`` produces one raster per azimuth direction, each named
    ``{output_basename}_{azimuth_formatted}``.  The *basename* (prefix) is
    what ``r.sun`` consumes via its ``horizon_basename`` parameter.

    Args:
        elevation: Name of the input elevation raster in the GRASS mapset.
            Can be either a DSM (for local horizon) or DEM (for regional).
        output_basename: Basename/prefix for the output horizon rasters.
        step: Angular step in degrees between computed horizon directions.
        start_azimuth: Starting azimuth in degrees (default: 0.0).
        end_azimuth: Ending azimuth in degrees (default: 360.0).
        max_distance: Maximum search distance in metres.  If ``None`` the
            ``r.horizon`` default (unlimited) is used.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The output basename (same as ``output_basename``).
    """
    params: dict = {
        "elevation": elevation,
        "step": step,
        "start": start_azimuth,
        "end": end_azimuth,
        "output": output_basename,
        "overwrite": True,
    }
    if max_distance is not None:
        params["maxdistance"] = max_distance

    grass_module("r.horizon", **params).run()

    return output_basename


def list_horizon_rasters(basename: str, grass_module: Any) -> List[str]:
    """List GRASS rasters whose names start with *basename*.

    Uses ``g.list`` to query the GRASS mapset rather than shell wildcards,
    which are not supported inside GRASS module arguments.

    Args:
        basename: The prefix shared by the rasters to find (e.g. the value
            returned by :func:`calculate_horizon_raster`).
        grass_module: The GRASS Python scripting Module class.

    Returns:
        Sorted list of matching raster names.  Empty list when none found.
    """
    g_list = grass_module(
        "g.list",
        type="raster",
        pattern=f"{basename}*",
        stdout_=PIPE,
    )
    g_list.run()

    raw = g_list.outputs.stdout.strip()
    if not raw:
        return []
    return sorted(line.strip() for line in raw.split("\n") if line.strip())


def combine_horizon_rasters_per_direction(
    local_basename: str,
    regional_basename: str,
    combined_basename: str,
    grass_module: Any,
) -> str:
    """Combine local and regional horizon rasters per azimuth direction.

    For each azimuth direction the combined horizon angle is
    ``max(local_angle, regional_angle)``; the obstruction that blocks more
    sunlight wins.  The combined rasters share *combined_basename* as their
    prefix so that ``r.sun`` can consume them via ``horizon_basename``.

    Args:
        local_basename: Basename for the local horizon rasters (DSM-derived).
        regional_basename: Basename for the regional horizon rasters
            (DEM-derived).
        combined_basename: Basename/prefix for the output combined rasters.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The combined basename (same as ``combined_basename``).

    Raises:
        ValueError: If the local and regional raster sets have different
            counts, indicating mismatched azimuth parameters.
    """
    local_rasters = list_horizon_rasters(local_basename, grass_module)
    regional_rasters = list_horizon_rasters(regional_basename, grass_module)

    if not local_rasters:
        raise ValueError(f"No horizon rasters found for local basename: {local_basename}")
    if not regional_rasters:
        raise ValueError(
            f"No horizon rasters found for regional basename: {regional_basename}"
        )
    if len(local_rasters) != len(regional_rasters):
        raise ValueError(
            f"Local ({len(local_rasters)}) and regional ({len(regional_rasters)}) "
            "horizon raster counts do not match. Ensure both were computed with the "
            "same azimuth step, start, and end parameters."
        )

    for local_r, regional_r in zip(local_rasters, regional_rasters):
        # Derive the direction suffix from the local raster name and apply it
        # to the combined basename so r.sun can discover the combined rasters.
        suffix = local_r[len(local_basename):]
        combined_r = f"{combined_basename}{suffix}"

        expression = f"{combined_r} = max({local_r}, {regional_r})"
        grass_module("r.mapcalc", expression=expression, overwrite=True).run()

    return combined_basename


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
