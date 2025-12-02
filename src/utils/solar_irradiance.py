import subprocess

from .linke import linke_by_day


def calculate_solar_irradiance(
    dsm: str, grass_output: str, aspect, slope, day: int, step: float, grass_module
):
    """Calculate solar irradiance for a given day using the r.sun module."""
    grass_module(
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
    ).run()

    return grass_output


def _get_raster_min_max(raster_name):
    """Get min and max values from a raster using r.univar."""
    result = subprocess.run(
        ["r.univar", "-g", raster_name],
        capture_output=True,
        text=True,
        check=True,
    )

    stats = {}
    for line in result.stdout.strip().split("\n"):
        if "=" in line:
            key, value = line.split("=", 1)
            stats[key] = value

    return float(stats["min"]), float(stats["max"])


def _normalize_raster(input_raster, output_raster, grass_module):
    """Normalize a raster to 0-1 range using min-max scaling."""
    min_val, max_val = _get_raster_min_max(input_raster)

    mapcalc_expr = (
        f"{output_raster} = "
        f"float({input_raster} - {min_val}) / "
        f"float({max_val} - {min_val})"
    )

    grass_module(
        "r.mapcalc",
        expression=mapcalc_expr,
        overwrite=True,
    ).run()

    return output_raster


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
    """Interpolate solar irradiance between key days and return per-day and summed rasters."""
    # Calculate irradiance for each key day
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

    # Interpolate to all days in range
    interp_days = list(range(min(key_days), max(key_days) + 1))
    interp_rasters = [f"{dsm}_solar_irradiance_interp_day{day}" for day in interp_days]

    grass_module(
        "r.series.interp",
        input=",".join(key_day_rasters),
        datapos=key_days,
        output=",".join(interp_rasters),
        samplingpos=interp_days,
        method="linear",
        overwrite=True,
    ).run()

    day_irradiance_rasters = {day: interp_rasters[i] for i, day in enumerate(interp_days)}

    # Sum all interpolated rasters
    summed_irradiance = f"{dsm}_solar_irradiance_interp"
    grass_module(
        "r.series",
        input=",".join(interp_rasters),
        output=summed_irradiance,
        method="sum",
        overwrite=True,
    ).run()

    if export:
        grass_module(
            "r.out.gdal",
            input=summed_irradiance,
            output=f"{summed_irradiance}.tif",
            format="GTiff",
            createopt="TFW=YES,COMPRESS=LZW",
            overwrite=True,
        ).run()

    if cleanup:
        grass_module(
            "g.remove",
            type="raster",
            name=",".join(key_day_rasters),
            flags="f",
        ).run()

    return day_irradiance_rasters, summed_irradiance


def calculate_solar_coefficients(day_irradiance_rasters: dict, dsm: str, grass_module):
    """Calculate normalized (0-1) solar coefficients for each day's irradiance raster."""
    day_coefficient_rasters = {}

    for day, irradiance_raster in day_irradiance_rasters.items():
        coefficient_raster = f"{dsm}_solar_coefficient_day{day}"
        _normalize_raster(irradiance_raster, coefficient_raster, grass_module)
        day_coefficient_rasters[day] = coefficient_raster

    return day_coefficient_rasters
