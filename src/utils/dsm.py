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

import re
import subprocess
import glob
from pathlib import Path
from subprocess import PIPE
from typing import Any, Dict, List, Optional, Tuple
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
    step: float = 30.0,
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
    local_horizon_prefix: str,
    regional_horizon_prefix: str,
    output_prefix: str,
    grass_module: Any,
) -> str:
    """
    Combine local and regional r.horizon outputs *per direction* using r.mapcalc.

    r.horizon creates multiple rasters named like:
        <prefix>_<dirIndex>_<something>

    Example (your case):
        suburb_ShotoverCountry_horizon_local_000_315.000000
        suburb_ShotoverCountry_horizon_regional_000_315.000000

    Your previous implementation embedded the trailing <something> into new map names,
    but that <something> can become negative / invalid (e.g. -2147483648), causing
    r.mapcalc parse errors.

    This revised implementation:
      - uses only the direction index (e.g. 000, 001, ...) to name outputs
      - never includes a negative sign in map identifiers
      - pairs rasters by direction index

    Args:
        local_horizon_prefix: Prefix passed to r.horizon for local DSM horizon.
        regional_horizon_prefix: Prefix passed to r.horizon for regional DEM horizon.
        output_prefix: Prefix for combined per-direction rasters.
        grass_module: GRASS Module runner.

    Returns:
        The output_prefix (combined rasters will be named f"{output_prefix}_{idx:03d}").
    """

    def _g_list(pattern: str) -> List[str]:
        # Use subprocess g.list exactly like your other helper does.
        out = subprocess.run(
            ["g.list", "type=raster", f"pattern={pattern}*"],
            capture_output=True,
            text=True,
            check=False,
        )
        rasters = [r for r in out.stdout.strip().split("\n") if r]
        return rasters

    # Capture r.horizon outputs
    local_rasters = _g_list(local_horizon_prefix)
    regional_rasters = _g_list(regional_horizon_prefix)

    if not local_rasters:
        raise RuntimeError(
            f"No local horizon rasters found matching pattern: {local_horizon_prefix}*"
        )
    if not regional_rasters:
        raise RuntimeError(
            f"No regional horizon rasters found matching pattern: {regional_horizon_prefix}*"
        )

    # Extract direction index from names.
    # We match: "<prefix>_<3digits>_" and capture the 3 digits.
    # This is robust and avoids depending on the trailing azimuth token formatting.
    def _index_map(prefix: str, rasters: List[str]) -> Dict[str, str]:
        idx_by_raster: Dict[str, str] = {}
        pat = re.compile(rf"^{re.escape(horizon_basename)}_(\d{{1,3}})_")
        for r in rasters:
            m = pat.match(r)
            if not m:
                # Skip any unexpected names rather than crashing later with invalid expressions
                continue
            idx_by_raster[m.group(1)] = r
        return idx_by_raster

    local_by_idx = _index_map(local_horizon_prefix, local_rasters)
    regional_by_idx = _index_map(regional_horizon_prefix, regional_rasters)

    # Validate that we have a consistent set of directions.
    local_idxs = set(local_by_idx.keys())
    regional_idxs = set(regional_by_idx.keys())
    common_idxs = sorted(local_idxs.intersection(regional_idxs))

    if not common_idxs:
        raise RuntimeError(
            "No matching horizon directions between local and regional rasters.\n"
            f"Local idxs: {sorted(local_idxs)}\n"
            f"Regional idxs: {sorted(regional_idxs)}"
        )

    # If there is a mismatch, fail loudly (or you can choose to only combine intersection).
    missing_local = sorted(regional_idxs - local_idxs)
    missing_regional = sorted(local_idxs - regional_idxs)
    if missing_local or missing_regional:
        raise RuntimeError(
            "Mismatch between local and regional horizon directions.\n"
            f"Directions missing in local: {missing_local}\n"
            f"Directions missing in regional: {missing_regional}\n"
            "Refusing to continue because per-direction pairing would be wrong."
        )

    # Combine per direction with safe output names:
    #   <output_prefix>_<idx>
    for idx in common_idxs:
        local_r = local_by_idx[idx]
        regional_r = regional_by_idx[idx]

        # Important: output map name contains only [A-Za-z0-9_]
        combined_r = f"{output_prefix}_{idx}"

        expression = f"{combined_r} = max({local_r}, {regional_r})"
        breakpoint()
        grass_module("r.mapcalc", expression=expression, overwrite=True).run()

    return output_prefix



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

def normalize_horizon_raster_names(horizon_basename: str, grass_module: Any) -> None:
    rasters = list_horizon_rasters(horizon_basename, grass_module)
    if not rasters:
        raise RuntimeError(f"No horizon rasters found for basename: {horizon_basename}")

    pat = re.compile(rf"^{re.escape(horizon_basename)}_(\d{{1,3}})_")

    for r in rasters:
        m = pat.match(r)
        if not m:
            continue

        idx_int = int(m.group(1))
        safe_name = f"{horizon_basename}_{idx_int:03d}"

        if safe_name == r:
            continue

        grass_module("g.rename", raster=(r, safe_name), overwrite=True).run()