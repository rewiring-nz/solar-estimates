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
        raise RuntimeError(f"🚫 Failed to build VRT from {len(dsm_files)} files: {e}") from e

    # Return the VRT path
    return vrt_path


def load_virtual_raster_into_grass(input_vrt: str, output_name: str, grass_module: Any) -> str:
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
    r_external = grass_module("r.external", input=input_vrt, output=output_name, band=1, overwrite=True)
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
    expression = f"{output_name} = if({slope_raster} <= {max_slope_degrees}, {input_raster}, null())"
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


def _list_rasters_with_prefix(prefix: str, grass_module: Any) -> list[str]:
    """List raster maps in the current mapset matching `<prefix>*`.

    Uses GRASS itself (via the provided Module wrapper) instead of calling
    `g.list` via subprocess. This avoids PATH/env issues and guarantees we query
    the same GRASS session/mapset the pipeline is using.
    """
    from subprocess import PIPE

    # g.list prints one map per line to stdout
    proc = grass_module(
        "g.list",
        type="raster",
        pattern=f"{prefix}*",
        stdout_=PIPE,
    )
    proc.run()

    out = (proc.outputs.stdout or "").strip()
    if not out:
        return []
    return [line.strip() for line in out.split("\n") if line.strip()]


def _suffix_after_prefix(map_name: str, prefix: str) -> str:
    """Return the suffix part of a GRASS map name after the given prefix.

    Example:
      map_name="foo_horizon_local_000_0", prefix="foo_horizon_local"
      -> "_000_0"
    """
    if not map_name.startswith(prefix):
        raise ValueError(f"Map '{map_name}' does not start with prefix '{prefix}'")
    return map_name[len(prefix) :]


def combine_horizon_rasters(
    local_horizon: str,
    regional_horizon: str,
    output_name: str,
    grass_module: Any,
) -> str:
    """Combine local and regional horizon raster *sets* by taking the maximum angle.

    IMPORTANT: `r.sun`'s `horizon_basename=` expects a *basename* that resolves to a
    set of rasters like:

      <basename>_000_0
      <basename>_010_0
      ...

    `r.horizon` creates these rasters for `local_horizon` and `regional_horizon`.
    This function now creates the same style of rasters for `output_name` by
    combining matching azimuth rasters from local and regional sets.

    Args:
        local_horizon: GRASS raster name prefix for the local horizon (from DSM).
                       r.horizon creates multiple rasters with this prefix.
        regional_horizon: GRASS raster name prefix for the regional horizon (from DEM).
                          r.horizon creates multiple rasters with this prefix.
        output_name: Prefix for the combined horizon raster set.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The basename/prefix for the combined horizon rasters (same as ``output_name``).

    Raises:
        RuntimeError: if no matching rasters are found or if a local/regional pair
            is missing for a given azimuth.
    """
    local_rasters = _list_rasters_with_prefix(local_horizon, grass_module)
    regional_rasters = _list_rasters_with_prefix(regional_horizon, grass_module)

    if not local_rasters:
        raise RuntimeError(f"No horizon rasters found matching pattern: {local_horizon}*")
    if not regional_rasters:
        raise RuntimeError(f"No horizon rasters found matching pattern: {regional_horizon}*")

    # Build lookup of regional rasters by suffix (e.g. "_000_0")
    regional_by_suffix: dict[str, str] = {}
    for r in regional_rasters:
        suf = _suffix_after_prefix(r, regional_horizon)
        regional_by_suffix[suf] = r

    # For each local raster, find matching regional raster with same suffix,
    # then write output_name<suffix> = max(local, regional)
    created_any = False
    for local_map in local_rasters:
        suffix = _suffix_after_prefix(local_map, local_horizon)

        # Skip the previously-generated single-map products if they exist in the mapset
        # (e.g. "<prefix>_combined")
        if suffix == "_combined":
            continue

        regional_map = regional_by_suffix.get(suffix)
        if regional_map is None:
            raise RuntimeError(
                f"Missing matching regional horizon raster for suffix '{suffix}'. "
                f"Expected '{regional_horizon}{suffix}' to exist."
            )

        combined_map = f"{output_name}{suffix}"
        expr = f"{combined_map} = max({local_map}, {regional_map})"
        grass_module("r.mapcalc", expression=expr, overwrite=True).run()
        created_any = True

    if not created_any:
        raise RuntimeError(
            f"Did not create any combined horizon rasters for output prefix '{output_name}'. "
            f"Local rasters: {len(local_rasters)}, regional rasters: {len(regional_rasters)}"
        )

    return output_name