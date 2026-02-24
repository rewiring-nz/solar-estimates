"""Solar irradiance calculation utilities for GRASS GIS.

This module provides functions for calculating solar irradiance using the
GRASS GIS r.sun module. It supports both single-day calculations and
interpolated multi-day calculations for seasonal analysis, as well as
creating normalized coefficient rasters for WRF data adjustment.

The main workflow (if WRF data is provided) involves:
    1. Calculate solar irradiance for key sample days using r.sun
    2. Interpolate between key days to generate daily irradiance maps
    3. Normalize to create coefficient rasters to adjust WRF data
"""

from subprocess import PIPE

from .linke import linke_by_day


def _get_raster_min_max(raster_name: str, grass_module) -> tuple[float, float]:
    """Get minimum and maximum values from a GRASS raster using r.univar.

    This is a helper function that extracts basic statistics from a raster
    using the GRASS r.univar module.

    Args:
        raster_name: Name of the raster in the current GRASS mapset.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        A tuple of (min_value, max_value) as floats.
    """
    univar = grass_module(
        "r.univar",
        map=raster_name,
        flags="g",
        stdout_=PIPE,
    )
    univar.run()

    # Parse the key=value output from r.univar -g
    stats = {}
    for line in univar.outputs.stdout.strip().split("\n"):
        if "=" in line:
            key, value = line.split("=", 1)
            stats[key] = value

    return float(stats["min"]), float(stats["max"])


def _percent_of_max_raster(
    input_raster: str,
    output_raster: str,
    grass_module,
) -> str:
    """Normalize a raster to percentage of the maximum value (0-1 scale).

    Applies the formula: percent = value / max

    This creates a coefficient raster where:
        - 1 represents the maximum irradiance location
        - Other values are a fraction of the maximum

    Args:
        input_raster: Name of the input raster to normalize.
        output_raster: Name for the normalized output raster.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The name of the output normalized raster (same as output_raster).
    """
    _, max_val = _get_raster_min_max(input_raster, grass_module)

    # Build the r.mapcalc expression for percent-of-max normalization
    mapcalc_expr = f"{output_raster} = float({input_raster}) / float({max_val})"

    grass_module(
        "r.mapcalc",
        expression=mapcalc_expr,
        overwrite=True,
    ).run()

    return output_raster


def calculate_solar_irradiance(
    dsm: str,
    grass_output: str,
    aspect,
    slope,
    day: int,
    step: float,
    grass_module,
) -> str:
    """Calculate solar irradiance for a single day using the GRASS r.sun module.

    This function wraps the r.sun solar radiation model to compute global
    horizontal irradiance (GHI) under clear-sky conditions. The Linke turbidity
    factor is automatically interpolated based on the day of year.

    Args:
        dsm: Name of the input Digital Surface Model (elevation) raster in GRASS.
        grass_output: Name for the output global radiation raster.
        aspect: Name of the aspect raster (direction of slope) in GRASS.
        slope: Name of the slope raster (steepness) in GRASS.
        day: Day of year (1-365) for the irradiance calculation.
        step: Time step in hours for the r.sun calculation.
            Smaller values (e.g., 0.5) give more accurate results but take longer.
        grass_module: The GRASS Python scripting Module class for running
            GRASS commands.

    Returns:
        The name of the output global radiation raster (same as grass_output).

    Note:
        This function assumes the GRASS computational region is already set
        appropriately for the DSM. The output units are Wh/m²/day.
    """
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


def calculate_solar_irradiance_interpolated(
    dsm: str,
    aspect,
    slope,
    key_days: list[int],
    step: float,
    grass_module,
    export: bool = False,
) -> tuple[dict[int, str], str]:
    """Calculate interpolated solar irradiance between key sample days.

    This function computes solar irradiance for a set of key days, then uses
    linear interpolation (via r.series.interp) to estimate irradiance for all
    days in the range.

    Workflow:
        1. Run r.sun for each key day to get irradiance values
        2. Interpolate between key days to fill in the intermediate days
        3. Sum all daily rasters to get total irradiance over the period

    Args:
        dsm: Name of the Digital Surface Model raster in GRASS.
        aspect: Name of the aspect raster in GRASS.
        slope: Name of the slope raster in GRASS.
        key_days: List of day-of-year values (1-365) to estimate irradiance.
        step: Time step in hours for the r.sun calculation.
            Smaller values (e.g., 0.5) give more accurate results but take longer.
        grass_module: The GRASS Python scripting Module class.
        export: If True, export the summed irradiance raster as a GeoTIFF.
            Defaults to False.

    Returns:
        A tuple containing:
            - day_irradiance_rasters: Dict mapping day-of-year (int) to the
              irradiance raster name (str) for each day in the range from
              min(key_days) to max(key_days). This includes both the exact
              r.sun calculations for key_days and interpolated values for
              days in between. The caller is responsible for cleaning up
              these rasters when no longer needed.
            - summed_irradiance: Name of the raster containing the sum of
              all daily irradiance values (total Wh/m² over the period).
    """
    # Step 1: Calculate irradiance for each key day
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

    # Step 2: Interpolate to days between the key days (excluding key days themselves)
    all_days = list(range(min(key_days), max(key_days) + 1))
    key_days_set = set(key_days)
    interp_only_days = [day for day in all_days if day not in key_days_set]

    # Build the output raster mapping, starting with the key day rasters we already have
    day_irradiance_rasters = {day: key_day_rasters[i] for i, day in enumerate(key_days)}

    # Only run interpolation if there are days between the key days
    if interp_only_days:
        interp_rasters = [
            f"{dsm}_solar_irradiance_interp_day{day}" for day in interp_only_days
        ]

        # datapos = key_days positions correspond to input rasters
        # samplingpos = interp_only_days positions for output rasters
        grass_module(
            "r.series.interp",
            input=",".join(key_day_rasters),
            datapos=key_days,
            output=",".join(interp_rasters),
            samplingpos=interp_only_days,
            method="linear",
            overwrite=True,
        ).run()

        # Add interpolated rasters to the mapping
        for i, day in enumerate(interp_only_days):
            day_irradiance_rasters[day] = interp_rasters[i]

    # Step 3: Sum all rasters (key days + interpolated) to get total irradiance
    all_rasters = list(day_irradiance_rasters.values())
    summed_irradiance = f"{dsm}_solar_irradiance_interp"
    grass_module(
        "r.series",
        input=",".join(all_rasters),
        output=summed_irradiance,
        method="sum",
        overwrite=True,
    ).run()

    # Optionally export the summed raster as a GeoTIFF
    if export:
        grass_module(
            "r.out.gdal",
            input=summed_irradiance,
            output=f"{summed_irradiance}.tif",
            format="GTiff",
            createopt="TFW=YES,COMPRESS=LZW",
            overwrite=True,
        ).run()

    return day_irradiance_rasters, summed_irradiance


def calculate_solar_coefficients(
    day_irradiance_rasters: dict[int, str],
    dsm: str,
    grass_module,
) -> dict[int, str]:
    """Calculate percent-of-max solar coefficients for each day's irradiance.

    Converts irradiance values (Wh/m²) to relative coefficients (0-1)
    using percent-of-max normalization.

    The coefficients are then used to adjust WRF irradiance data so it
    accounts for roof shape, shading, etc.

    Args:
        day_irradiance_rasters: Dict mapping day-of-year to irradiance raster
            names, as returned by calculate_solar_irradiance_interpolated().
        dsm: Name of the DSM raster, used as a prefix for output names.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        Dict mapping day-of-year (int) to coefficient raster name (str).
    """
    day_coefficient_rasters = {}

    for day, irradiance_raster in day_irradiance_rasters.items():
        coefficient_raster = f"{dsm}_solar_percentmax_day{day}"
        _percent_of_max_raster(irradiance_raster, coefficient_raster, grass_module)
        day_coefficient_rasters[day] = coefficient_raster

    return day_coefficient_rasters
