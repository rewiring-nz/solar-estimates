from .linke import linke_by_day
import numpy as np


def calculate_solar_irradiance(
    dsm: str, grass_output: str, aspect, slope, day: int, step: float, grass_module
):
    """Calculate solar irradiance for a given day using the r.sun module."""

    r_sun = grass_module(
        "r.sun",
        elevation=dsm,
        aspect=aspect,
        slope=slope,
        day=day,
        step=step,
        linke_value=linke_by_day(day),
        nprocs=16,
        glob_rad=grass_output,
        overwrite=True,
    )
    r_sun.run()

    return grass_output


def calculate_solar_irradiance_range(
    dsm: str,
    aspect,
    slope,
    days,
    step: float,
    grass_module,
    export: bool = False,
    cleanup: bool = True,
):
    """Calculate solar irradiance over a range of days, and sum the rasters.
    Optionally cleans up individual day rasters from GRASS' database with
    cleanup=True, and exports the summed raster as a GeoTIFF with export=True."""

    # Loop through day range, keeping track of generated rasters
    day_rasters = []
    for day in days:
        day_map = calculate_solar_irradiance(
            dsm=dsm,
            grass_output=f"{dsm}_solar_irradiance_day{day}",
            aspect=aspect,
            slope=slope,
            day=day,
            step=step,
            grass_module=grass_module,
        )
        day_rasters.append(day_map)

    # Comma-delimited as the format used by most GRASS modules
    rasters = ",".join(day_rasters)

    # Sum rasters together
    r_series = grass_module(
        "r.series",
        input=rasters,
        output=f"{dsm}_solar_irradiance",
        method="sum",
        overwrite=True,
    )
    r_series.run()

    # Export the summed raster as a GeoTIFF
    if export:
        r_out = grass_module(
            "r.out.gdal",
            input=f"{dsm}_solar_irradiance",
            output=f"{dsm}_solar_irradiance.tif",
            format="GTiff",
            createopt="TFW=YES,COMPRESS=LZW",
            overwrite=True,
        )
        r_out.run()

    # Clean up day rasters
    if cleanup:
        g_remove = grass_module(
            "g.remove", type="raster", name=rasters, flags="f"
        )  # force without prompt
        g_remove.run()

    return f"{dsm}_solar_irradiance"


def calculate_solar_irradiance_interpolated(
    dsm: str,
    aspect,
    slope,
    key_days: list,
    step: float,
    grass_module,
    export: bool = False,
    cleanup: bool = True,
):
    """
    Interpolate solar irradiance between key_days using linear interpolation.
    Creates weighted sum directly. Optionally cleans up individual day rasters
    from GRASS' database with cleanup=True, and exports the summed raster as
    a GeoTIFF with export=True.
    """
    # Calculate irradiance for each key day and store rasters
    day_rasters = []
    for day in key_days:
        day_map = calculate_solar_irradiance(
            dsm=dsm,
            grass_output=f"{dsm}_solar_irradiance_day{day}",
            aspect=aspect,
            slope=slope,
            day=day,
            step=step,
            grass_module=grass_module,
        )
        day_rasters.append(day_map)

    # Use sorted key_days to determine interpolation range
    key_days_sorted = sorted(key_days)
    first, last = key_days_sorted[0], key_days_sorted[-1]

    # Determine interpolation days (handles wrap-around)
    if last < first:
        interp_days = list(range(first, 366)) + list(range(1, last + 1))
    else:
        interp_days = list(range(first, last + 1))

    # Calculate total weight for each key day using simple linear interpolation
    weights_per_key_day = np.zeros(len(key_days_sorted))

    for day in interp_days:
        # Find which two key days this falls between
        # Handle wrap-around
        if last < first:
            day_adj = day if day >= first else day + 365
            key_days_adj = [kd if kd >= first else kd + 365 for kd in key_days_sorted]
        else:
            day_adj = day
            key_days_adj = key_days_sorted

        # Find surrounding key days
        idx_after = next((i for i, kd in enumerate(key_days_adj) if kd >= day_adj), 0)
        idx_before = (idx_after - 1) % len(key_days_sorted)

        day_before = key_days_adj[idx_before]
        day_after = key_days_adj[idx_after]

        # Linear interpolation weight
        if day_before == day_after:
            # Exactly on a key day
            weights_per_key_day[idx_before] += 1.0
        else:
            span = day_after - day_before
            weight_after = (day_adj - day_before) / span
            weight_before = 1.0 - weight_after

            weights_per_key_day[idx_before] += weight_before
            weights_per_key_day[idx_after] += weight_after

    # Create a single weighted sum expression
    output_name = f"{dsm}_solar_irradiance_interp"

    weighted_terms = [
        f"({raster} * {weight:.10f})"
        for raster, weight in zip(day_rasters, weights_per_key_day)
    ]

    expression = f"{output_name} = " + " + ".join(weighted_terms)

    r_mapcalc = grass_module("r.mapcalc", expression=expression, overwrite=True)
    r_mapcalc.run()

    # Export the raster as a GeoTIFF
    if export:
        r_out = grass_module(
            "r.out.gdal",
            input=output_name,
            output=f"{output_name}.tif",
            format="GTiff",
            createopt="TFW=YES,COMPRESS=LZW",
            overwrite=True,
        )
        r_out.run()

    # Clean up intermediate rasters
    if cleanup:
        g_remove = grass_module(
            "g.remove", type="raster", name=",".join(day_rasters), flags="f"
        )
        g_remove.run()

    return output_name
