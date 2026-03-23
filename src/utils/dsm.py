"""DSM/DEM raster helpers for GDAL and GRASS GIS workflows."""

import glob
from subprocess import PIPE
from typing import Any, Optional, Tuple

from osgeo import gdal


def merge_rasters(dsm_file_glob: str, area_name: str) -> str:
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
    dsm_files = glob.glob(dsm_file_glob)
    if not dsm_files:
        raise FileNotFoundError(f"No files found for pattern: {dsm_file_glob}")

    try:
        vrt_options = gdal.BuildVRTOptions(resampleAlg=gdal.GRA_NearestNeighbour)
        vrt_path = f"{area_name}_merged.vrt"
        gdal.BuildVRT(vrt_path, dsm_files, options=vrt_options)
    except Exception as e:
        raise RuntimeError(
            f"Failed to build VRT from {len(dsm_files)} files: {e}"
        ) from e

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
    r_external = grass_module(
        "r.external", input=input_vrt, output=output_name, band=1, overwrite=True
    )
    r_external.run()

    g_region = grass_module("g.region", raster=output_name, flags="p")
    g_region.run()

    return output_name


def get_raster_resolution(raster_name: str, grass_module: Any) -> Tuple[float, float]:
    """Return the east-west and north-south resolution of a GRASS raster.

    Uses ``r.info -g`` (machine-readable key=value output) to read the
    raster's ``ewres`` and ``nsres`` metadata fields.

    Args:
        raster_name: Name of the raster in the current GRASS mapset.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        A tuple ``(ewres, nsres)`` in the map's native units (typically metres).
    """
    r_info = grass_module(
        "r.info",
        map=raster_name,
        flags="g",
        stdout_=PIPE,
    )
    r_info.run()

    stats: dict[str, str] = {}
    for line in r_info.outputs.stdout.strip().split("\n"):
        if "=" in line:
            key, value = line.split("=", 1)
            stats[key.strip()] = value.strip()

    ewres = float(stats["ewres"])
    nsres = float(stats["nsres"])
    return ewres, nsres


def resample_to_resolution(
    input_raster: str,
    target_resolution: float,
    output_name: Optional[str],
    grass_module: Any,
    method: str = "bilinear",
) -> str:
    """Resample a raster to a target resolution.

    Args:
        input_raster: Name of the source raster in the current GRASS mapset.
        target_resolution: Desired output resolution in the map's native units
            (e.g. ``1.0`` for 1 metre when the CRS is NZGD2000 / NZTM2000).
        output_name: Name for the resampled raster inside GRASS. When
            ``None`` the name ``"{input_raster}_resampled_{target_resolution}m"``
            is generated automatically.
        grass_module: The GRASS Python scripting Module class.
        method: Interpolation method passed to ``r.resamp.interp``.

    Returns:
        The GRASS raster name of the resampled output.

    Raises:
        ValueError: If *target_resolution* is not a positive number.
        ValueError: If *method* is not one of the accepted interpolation strings.
    """
    if target_resolution <= 0:
        raise ValueError(
            f"target_resolution must be a positive number, got {target_resolution!r}"
        )

    accepted_methods = {"nearest", "bilinear", "bicubic", "lanczos"}
    if method not in accepted_methods:
        raise ValueError(
            f"method must be one of {sorted(accepted_methods)}, got {method!r}"
        )

    if output_name is None:
        res_str = str(target_resolution).replace(".", "p")
        output_name = f"{input_raster}_resampled_{res_str}m"

    grass_module(
        "g.region",
        raster=input_raster,
        res=target_resolution,
        flags="a",
    ).run()

    grass_module(
        "r.resamp.interp",
        input=input_raster,
        output=output_name,
        method=method,
        overwrite=True,
    ).run()

    grass_module(
        "g.region",
        raster=input_raster,
    ).run()

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
