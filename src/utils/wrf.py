"""
WRF (Weather Research and Forecasting) functionality for GRASS GIS workflows.

This module contains utilities to load, reproject, clip, import and summarise
WRF-derived solar variables (surface downward shortwave radiation).

High level responsibilities:
- Read WRF NetCDF files via xarray and manage the CRS, including reprojections,
  and creating per-day WRF rasters.
- Helpers to multiply WRF rasters by normalized coefficient rasters,
  sum per-day adjusted rasters, and produce a summed WRF raster for comparison
  against clear-sky modeled values.
"""

import os
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import xarray as xr

from .building_outlines import apply_building_mask, remove_masks

def _load_wrf_with_crs(nc_file_path: str, crs: str = "EPSG:4326") -> xr.Dataset:
    """Open a WRF NetCDF with xarray and attach a CRS using rioxarray.

    Args:
        nc_file_path: Path to the WRF NetCDF file.
        crs: CRS string to attach to the dataset (default EPSG:4326).

    Returns:
        An xarray.Dataset with rioxarray spatial metadata attached.
    """
    ds = xr.open_dataset(nc_file_path, engine="h5netcdf")
    # Standardize coordinate names for rioxarray compatibility
    ds = ds.rename({"lon": "x", "lat": "y"})

    # Write CRS and spatial dimension metadata in-place
    ds.rio.write_crs(crs, inplace=True)
    ds.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)

    return ds

def _clip_raster_to_region(raster_name: str, output_name: str, grass_module: Any) -> str:
    """Clip/copy a GRASS raster to the current computational region.

    This helper produces a new raster whose values match `raster_name` but
    conform to the current GRASS computational region (resolution/extent).

    Args:
        raster_name: Source raster name in GRASS.
        output_name: Destination raster name to create in GRASS.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The created raster name (`output_name`).
    """
    r_mapcalc = grass_module(
        "r.mapcalc",
        expression=f"{output_name} = {raster_name}",
        overwrite=True,
        quiet=True,
    )
    r_mapcalc.run()

    return output_name

def _import_wrf_to_grass(
    wrf_dataset: xr.Dataset,
    output_prefix: str,
    grass_module: Any,
    days: Iterable[int],
    clip_to_raster: Optional[str] = None,
) -> Dict[int, str]:
    """Import per-day WRF fields into GRASS as individual rasters.

    This function:
    - Determines the subset of days available in the dataset within the
      requested `days` iterable.
    - For each day, writes a temporary GeoTIFF for the day and imports it into
      GRASS using `r.in.gdal`.
    - Optionally clips the imported raster to a provided GRASS raster by
      setting the region before clipping and removing the un-clipped raster.

    Args:
        wrf_dataset: xarray Dataset containing a `dayofyear` coordinate and
            variable `SWDOWN` (or another solar variable).
        output_prefix: Prefix for names created in GRASS (e.g. "wrf").
        grass_module: GRASS Module-like callable used to run imports.
        days: Iterable of day-of-year integers to import (subset of dataset days).
        clip_to_raster: If provided, the GRASS raster name to which the imported
            rasters should be clipped (region set to this raster).

    Returns:
        Mapping of day-of-year (int) to created GRASS raster name.
    """
    # Determine available days within the requested range using the dataset coord
    min_day = min(days)
    max_day = max(days)
    days_to_import = wrf_dataset.dayofyear.where(
        (wrf_dataset.dayofyear >= min_day) & (wrf_dataset.dayofyear <= max_day),
        drop=True,
    ).values

    # If clipping to an existing GRASS raster is requested, set the region now
    if clip_to_raster:
        grass_module("g.region", raster=clip_to_raster).run()

    imported_rasters: Dict[int, str] = {}
    temp_dir = tempfile.mkdtemp()

    try:
        for day in days_to_import:
            day_int = int(day)
            raster_name = f"{output_prefix}_doy_{day_int}"
            day_data = wrf_dataset.sel(dayofyear=day)

            # TODO: do these need to be GeoTIFFs or can we use in-memory via GRASS
            # Write the day's SWDOWN variable to a temporary GeoTIFF.
            # The caller is expected to ensure the variable exists and is named
            # appropriately (here we use 'SWDOWN' as the conventional shortwave).
            temp_tif = os.path.join(temp_dir, f"wrf_day_{day_int}.tif")
            # Use rioxarray's to_raster - this will respect the dataset's CRS/transform
            day_data["SWDOWN"].rio.to_raster(temp_tif)

            # Import the temp GeoTIFF into GRASS
            r_in = grass_module(
                "r.in.gdal",
                input=temp_tif,
                output=raster_name,
                overwrite=True,
                quiet=True,
            )
            r_in.run()

            if clip_to_raster:
                # Create a clipped raster that aligns with the current region
                clipped_name = f"{output_prefix}_clipped_doy_{day_int}"
                _clip_raster_to_region(raster_name, clipped_name, grass_module)
                # Remove the original un-clipped raster to avoid duplication
                grass_module(
                    "g.remove", type="raster", name=raster_name, flags="f", quiet=True
                ).run()
                imported_rasters[day_int] = clipped_name
            else:
                imported_rasters[day_int] = raster_name

            # Remove the temporary GeoTIFF for this day
            os.remove(temp_tif)
    finally:
        # Attempt to remove the temporary directory if empty
        try:
            os.rmdir(temp_dir)
        except Exception:
            # If removal fails (shouldn't), don't break the pipeline
            pass

    return imported_rasters

def _sum_wrf_rasters(wrf_rasters: Union[Dict[int, str], Iterable[str]], output_name: str, grass_module: Any) -> str:
    """Sum multiple WRF day rasters into a single total raster using r.mapcalc.

    This function constructs an expression like:
        output = raster1 + raster2 + raster3 + ...

    Args:
        wrf_rasters: Dict or iterable of raster names to sum.
        output_name: Desired name of the summed raster.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The name of the created summed raster (`output_name`).
    """
    if isinstance(wrf_rasters, dict):
        raster_list = list(wrf_rasters.values())
    else:
        raster_list = list(wrf_rasters)

    if not raster_list:
        raise ValueError("No WRF rasters provided to sum.")

    raster_sum = " + ".join(raster_list)
    expression = f"{output_name} = {raster_sum}"

    r_mapcalc = grass_module("r.mapcalc", expression=expression, overwrite=True)
    r_mapcalc.run()

    return output_name

def calculate_wrf_adjusted_per_day(
    wrf_day_rasters: Dict[int, str],
    coefficient_rasters: Dict[int, str],
    grass_module: Any,
    output_prefix: str = "wrf_adjusted",
) -> Dict[int, str]:
    """Multiply per-day WRF rasters by corresponding coefficient rasters.

    This creates a new GRASS raster for each day named "<output_prefix>_day{doy}".

    Args:
        wrf_day_rasters: Mapping from day-of-year (int) to GRASS raster name
            containing that day's WRF data.
        coefficient_rasters: Mapping from day-of-year (int) to GRASS raster
            name containing the normalized coefficient (0-1) for that day.
        grass_module: The GRASS Python scripting Module class.
        output_prefix: Prefix to use when naming the adjusted rasters.

    Returns:
        Mapping from day-of-year to the created adjusted raster names.
    """
    adjusted_rasters: Dict[int, str] = {}

    for day, wrf_raster in wrf_day_rasters.items():
        # If coefficients are missing for a day, skip with a warning
        if day not in coefficient_rasters:
            print(f"Warning: No coefficient raster for day {day}, skipping")
            continue

        coeff_raster = coefficient_rasters[day]
        output_name = f"{output_prefix}_day{day}"

        # Use r.mapcalc to multiply rasters in GRASS
        mapcalc_expr = f"{output_name} = {wrf_raster} * {coeff_raster}"
        grass_module(
            "r.mapcalc",
            expression=mapcalc_expr,
            overwrite=True,
        ).run()

        adjusted_rasters[day] = output_name

    return adjusted_rasters

def sum_adjusted_rasters(
    adjusted_rasters: Union[Dict[int, str], Iterable[str]],
    output_name: str,
    grass_module: Any,
    cleanup: bool = True,
) -> str:
    """Sum a collection of per-day adjusted WRF rasters into a single raster.

    This uses `r.series` (method=sum) when provided a list of raster names; if
    a dict of day->raster is supplied the dict values are used.

    Args:
        adjusted_rasters: Mapping or iterable of raster names to sum.
        output_name: Name for the summed raster in GRASS.
        grass_module: The GRASS Python scripting Module class.
        cleanup: If True, remove the input adjusted rasters from the mapset
            after the sum is created.

    Returns:
        The name of the summed raster (`output_name`).
    """
    if isinstance(adjusted_rasters, dict):
        raster_list = list(adjusted_rasters.values())
    else:
        raster_list = list(adjusted_rasters)

    grass_module(
        "r.series",
        input=",".join(raster_list),
        output=output_name,
        method="sum",
        overwrite=True,
    ).run()

    # Optionally remove intermediate rasters to keep the GRASS mapset tidy
    if cleanup and raster_list:
        grass_module(
            "g.remove",
            type="raster",
            name=",".join(raster_list),
            flags="f",
        ).run()

    return output_name

def calculate_wrf_on_buildings(
    wrf_summed_raster: str, building_vector: str, output_name: str, grass_module: Any
) -> str:
    """Apply a building mask and create a building-only WRF raster.

    Args:
        wrf_summed_raster: Name of the summed WRF raster in GRASS.
        building_vector: Name of the building footprints vector in GRASS.
        output_name: Name to create for the building-only WRF raster.
        grass_module: GRASS Module-like callable.

    Returns:
        The name of the created building-only raster (`output_name`).
    """
    # Apply building mask to restrict operations to building footprints
    apply_building_mask(building_vector, output_name="building_mask", grass_module=grass_module)

    r_mapcalc = grass_module(
        "r.mapcalc",
        expression=f"{output_name} = {wrf_summed_raster}",
        overwrite=True,
    )
    r_mapcalc.run()

    remove_masks(grass_module)

    return output_name

def cleanup_wrf_intermediates(
    day_rasters: Union[Dict[int, str], Iterable[str]], summed_raster: Optional[str], grass_module: Any
) -> None:
    """Remove intermediate WRF rasters from the GRASS mapset.

    Args:
        day_rasters: Dict or iterable containing the names of per-day rasters.
        summed_raster: Optional name of the summed raster to remove as well.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        None
    """
    if isinstance(day_rasters, dict):
        raster_list = list(day_rasters.values())
    else:
        raster_list = list(day_rasters)

    for raster in raster_list:
        grass_module("g.remove", type="raster", name=raster, flags="f", quiet=True).run()

    if summed_raster:
        grass_module("g.remove", type="raster", name=summed_raster, flags="f", quiet=True).run()

def process_wrf_for_grass(
    nc_file_path: str,
    output_prefix: str,
    grass_module: Any,
    source_crs: str = "EPSG:4326",
    target_crs: Optional[str] = None,
    days: Optional[Iterable[int]] = None,
    clip_to_raster: Optional[str] = None,
    print_diagnostics: bool = False,
) -> Tuple[Dict[int, str], str]:
    """Load WRF NetCDF, (optionally) reproject, import per-day rasters into GRASS and sum.

    Args:
        nc_file_path: Path to the WRF NetCDF file.
        output_prefix: Prefix to use when naming imported rasters in GRASS.
        grass_module: The GRASS Python scripting Module class.
        source_crs: CRS to attach to the raw WRF dataset (default EPSG:4326).
        target_crs: If provided, reproject the dataset to this CRS before import.
        days: Iterable of day-of-year integers to import. If None, the function
            imports the full range present in the dataset.
        clip_to_raster: If provided, set the GRASS region to this raster and
            clip imported rasters to that region.
        print_diagnostics: If True, call the diagnostics helper to print dataset
            metadata.

    Returns:
        A tuple (imported_rasters, summed_raster_name) where `imported_rasters` is
        a dict mapping day-of-year to GRASS raster name and `summed_raster_name`
        is the name of the combined total raster produced.
    """
    # Optionally print diagnostics
    if print_diagnostics:
        from .diagnostics import print_wrf_diagnostics

        wrf_ds = print_wrf_diagnostics(nc_file_path)

        # Ensure expected coordinate names and metadata for subsequent operations
        wrf_ds = wrf_ds.rename({"lon": "x", "lat": "y"})
        wrf_ds.rio.write_crs(source_crs, inplace=True)
        wrf_ds.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)
    else:
        wrf_ds = _load_wrf_with_crs(nc_file_path, crs=source_crs)

    # Reproject to the target CRS if requested
    if target_crs:
        wrf_ds = wrf_dataset.rio.reproject(target_crs)

    # If days is not provided infer the full range from dataset dayofyear values
    if days is None:
        # Convert to a sorted list of unique dayofyear integers present in dataset
        days = sorted(int(d) for d in xr.DataArray(wrf_ds["dayofyear"]).values)

    imported_rasters = _import_wrf_to_grass(wrf_ds, output_prefix, grass_module, days, clip_to_raster)

    # Sum imported daily rasters into a single total raster
    summed_raster_name = f"{output_prefix}_total"
    summed_raster = _sum_wrf_rasters(imported_rasters, summed_raster_name, grass_module)

    return imported_rasters, summed_raster
