import os
import tempfile

import xarray as xr

from .building_outlines import apply_building_mask, remove_masks


def calculate_wrf_adjusted_per_day(
    wrf_day_rasters: dict,
    coefficient_rasters: dict,
    grass_module,
    output_prefix: str = "wrf_adjusted",
):
    """Multiply each day's WRF raster by its corresponding coefficient raster."""
    adjusted_rasters = {}

    for day in wrf_day_rasters:
        if day not in coefficient_rasters:
            print(f"Warning: No coefficient raster for day {day}, skipping")
            continue

        wrf_raster = wrf_day_rasters[day]
        coeff_raster = coefficient_rasters[day]
        output_name = f"{output_prefix}_day{day}"

        mapcalc_expr = f"{output_name} = {wrf_raster} * {coeff_raster}"
        grass_module(
            "r.mapcalc",
            expression=mapcalc_expr,
            overwrite=True,
        ).run()

        adjusted_rasters[day] = output_name

    return adjusted_rasters


def sum_adjusted_rasters(
    adjusted_rasters: dict,
    output_name: str,
    grass_module,
    cleanup: bool = True,
):
    """Sum per-day adjusted WRF rasters into a single total."""
    raster_list = list(adjusted_rasters.values())

    grass_module(
        "r.series",
        input=",".join(raster_list),
        output=output_name,
        method="sum",
        overwrite=True,
    ).run()

    if cleanup:
        grass_module(
            "g.remove",
            type="raster",
            name=",".join(raster_list),
            flags="f",
        ).run()

    return output_name


def _load_wrf_with_crs(nc_file_path, crs="EPSG:4326"):
    """Load a WRF NetCDF file and assign a CRS to it."""

    ds = xr.open_dataset(nc_file_path, engine="h5netcdf")
    ds = ds.rename({"lon": "x", "lat": "y"})
    ds.rio.write_crs(crs, inplace=True)
    ds.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)

    return ds


def _reproject_wrf_to_crs(wrf_dataset, target_crs):
    """Reproject a WRF dataset to match a target CRS."""

    ds_reprojected = wrf_dataset.rio.reproject(target_crs)

    return ds_reprojected


def _clip_raster_to_region(raster_name, output_name, grass_module):
    """Clip a raster to the current computational region."""

    r_mapcalc = grass_module(
        "r.mapcalc",
        expression=f"{output_name} = {raster_name}",
        overwrite=True,
        quiet=True,
    )
    r_mapcalc.run()

    return output_name


def _import_wrf_to_grass(
    wrf_dataset, output_prefix, grass_module, days, clip_to_raster=None
):
    """Import a WRF dataset into GRASS as separate rasters for all days in range."""
    min_day = min(days)
    max_day = max(days)
    days_to_import = wrf_dataset.dayofyear.where(
        (wrf_dataset.dayofyear >= min_day) & (wrf_dataset.dayofyear <= max_day),
        drop=True,
    ).values

    if clip_to_raster:
        grass_module("g.region", raster=clip_to_raster).run()

    imported_rasters = {}
    temp_dir = tempfile.mkdtemp()

    for day in days_to_import:
        day_int = int(day)
        raster_name = f"{output_prefix}_doy_{day_int}"
        day_data = wrf_dataset.sel(dayofyear=day)

        temp_tif = os.path.join(temp_dir, f"wrf_day_{day_int}.tif")
        day_data["SWDOWN"].rio.to_raster(temp_tif)

        r_in = grass_module(
            "r.in.gdal", input=temp_tif, output=raster_name, overwrite=True, quiet=True
        )
        r_in.run()

        if clip_to_raster:
            clipped_name = f"{output_prefix}_clipped_doy_{day_int}"
            _clip_raster_to_region(raster_name, clipped_name, grass_module)
            grass_module(
                "g.remove", type="raster", name=raster_name, flags="f", quiet=True
            ).run()
            imported_rasters[day_int] = clipped_name
        else:
            imported_rasters[day_int] = raster_name

        os.remove(temp_tif)

    os.rmdir(temp_dir)

    return imported_rasters


def _sum_wrf_rasters(wrf_rasters, output_name, grass_module):
    """Sum multiple WRF day rasters into a single total radiation raster."""
    if isinstance(wrf_rasters, dict):
        raster_list = list(wrf_rasters.values())
    else:
        raster_list = wrf_rasters

    raster_sum = " + ".join(raster_list)
    expression = f"{output_name} = {raster_sum}"

    r_mapcalc = grass_module("r.mapcalc", expression=expression, overwrite=True)
    r_mapcalc.run()

    return output_name


def calculate_wrf_on_buildings(
    wrf_summed_raster, building_vector, output_name, grass_module
):
    """Calculate WRF measured radiation on building outlines."""

    apply_building_mask(
        building_vector, output_name="building_mask", grass_module=grass_module
    )

    r_mapcalc = grass_module(
        "r.mapcalc",
        expression=f"{output_name} = {wrf_summed_raster}",
        overwrite=True,
    )
    r_mapcalc.run()

    remove_masks(grass_module)

    return output_name


def cleanup_wrf_intermediates(day_rasters, summed_raster, grass_module):
    """Clean up intermediate WRF rasters."""
    if isinstance(day_rasters, dict):
        raster_list = list(day_rasters.values())
    else:
        raster_list = day_rasters

    for raster in raster_list:
        grass_module(
            "g.remove", type="raster", name=raster, flags="f", quiet=True
        ).run()

    if summed_raster:
        grass_module(
            "g.remove", type="raster", name=summed_raster, flags="f", quiet=True
        ).run()


def process_wrf_for_grass(
    nc_file_path,
    output_prefix,
    grass_module,
    source_crs="EPSG:4326",
    target_crs=None,
    days=None,
    clip_to_raster=None,
    print_diagnostics=False,
):
    """Load, reproject, clip, and import WRF data into GRASS."""

    if print_diagnostics:
        from .diagnostics import print_wrf_diagnostics

        wrf_ds = print_wrf_diagnostics(nc_file_path)
        wrf_ds = wrf_ds.rename({"lon": "x", "lat": "y"})
        wrf_ds.rio.write_crs(source_crs, inplace=True)
        wrf_ds.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)
    else:
        wrf_ds = _load_wrf_with_crs(nc_file_path, crs=source_crs)

    if target_crs:
        wrf_ds = _reproject_wrf_to_crs(wrf_ds, target_crs)

    imported_rasters = _import_wrf_to_grass(
        wrf_ds, output_prefix, grass_module, days, clip_to_raster
    )

    summed_raster_name = f"{output_prefix}_total"
    summed_raster = _sum_wrf_rasters(imported_rasters, summed_raster_name, grass_module)

    return imported_rasters, summed_raster
