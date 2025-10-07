from .linke import linke_by_day
import numpy as np
from scipy.interpolate import CubicSpline


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
    """Calculate solar irradiance over a range of days, sum the rasters. Optionally cleans up
    day rasters from GRASS' database."""

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
    """Calculate annual solar irradiance by interpolating between key days (solstices/equinoxes)
    using cubic spline interpolation for weights."""

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

    # Interpolate weights for each key day using cubic spline
    days_of_year = np.arange(1, 366)
    key_days_extended = key_days + [key_days[0] + 365]  # For periodicity
    weights_matrix = []

    for i, kd in enumerate(key_days):
        # Create a vector with 1 at the key day, 0 elsewhere, and repeat the first value at the end
        y = np.zeros(len(key_days))
        y[i] = 1
        y_extended = np.append(y, y[0])  # Ensure periodicity
        cs = CubicSpline(key_days_extended, y_extended, bc_type='periodic')
        weights = cs(days_of_year)
        weights_matrix.append(weights)

    # Sum weights for each key day across all days
    total_weights = [float(np.sum(np.clip(w, 0, None))) for w in weights_matrix]

    # Create weighted sum using r.mapcalc
    weighted_terms = [
        f"({raster} * {weight})"
        for raster, weight in zip(day_rasters, total_weights)
    ]
    expression = f"{dsm}_solar_irradiance_annual = " + " + ".join(weighted_terms)

    r_mapcalc = grass_module(
        "r.mapcalc",
        expression=expression,
        overwrite=True
    )
    r_mapcalc.run()

    # Export the annual raster as a GeoTIFF
    if export:
        r_out = grass_module(
            "r.out.gdal",
            input=f"{dsm}_solar_irradiance_annual",
            output=f"{dsm}_solar_irradiance_annual.tif",
            format="GTiff",
            createopt="TFW=YES,COMPRESS=LZW",
            overwrite=True,
        )
        r_out.run()

    # Clean up day rasters
    if cleanup:
        rasters = ",".join(day_rasters)
        g_remove = grass_module(
            "g.remove", type="raster", name=rasters, flags="f"
        )
        g_remove.run()

    return f"{dsm}_solar_irradiance_annual"
