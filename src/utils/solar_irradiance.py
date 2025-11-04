from .linke import linke_by_day


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
    Interpolate solar irradiance rasters between key_days.
    Optionally cleans up individual day rasters from GRASS' database with
    cleanup=True, and exports the summed raster as a GeoTIFF with export=True.
    """
    # Calculate irradiance for each key day and store rasters
    key_day_rasters = []
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
        key_day_rasters.append(day_map)

    # Determine interpolation range from min to max key day
    interp_days = list(range(min(key_days), max(key_days) + 1))

    # Generate output raster names and sampling positions for each day
    interp_rasters = [f"{dsm}_solar_irradiance_interp_day{day}" for day in interp_days]

    # Use r.series.interp to interpolate between key days
    # datapos: positions of calculated raster data (key days)
    # samplingpos: positions to interpolate (all days in range)
    r_series_interp = grass_module(
        "r.series.interp",
        input=",".join(key_day_rasters),
        datapos=key_days,
        output=",".join(interp_rasters),
        samplingpos=interp_days,
        method="linear",
        overwrite=True,
    )
    r_series_interp.run()

    # Sum all interpolated rasters
    output_name = f"{dsm}_solar_irradiance_interp"
    r_series = grass_module(
        "r.series",
        input=",".join(interp_rasters),
        output=output_name,
        method="sum",
        overwrite=True,
    )
    r_series.run()

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
        all_rasters = key_day_rasters + interp_rasters
        g_remove = grass_module(
            "g.remove", type="raster", name=",".join(all_rasters), flags="f"
        )
        g_remove.run()

    return output_name
