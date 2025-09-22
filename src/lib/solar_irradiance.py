from .linke import linke_by_day

def calculate_solar_irradiance(dsm: str,
                               grass_output: str,
                               aspect,
                               slope,
                               day: int,
                               step: float,
                               grass_module):
    """Calculate solar irradiance for a given day using the r.sun module."""

    r_sun = grass_module('r.sun',
                        elevation=dsm,
                        aspect=aspect,
                        slope=slope,
                        day=day,
                        step=step,
                        linke_value=linke_by_day(day),
                        nprocs=16,
                        glob_rad=grass_output,
                        overwrite=True)
    r_sun.run()

    return grass_output

def calculate_solar_irradiance_range(dsm: str,
                               aspect,
                               slope,
                               days,
                               step: float,
                               grass_module,
                               cleanup: bool = True):
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
    rasters = ','.join(day_rasters)

    # Sum rasters together
    r_series = grass_module('r.series',
                            input=rasters,
                            output=f"{dsm}_solar_irradiance",
                            method='sum',
                            overwrite=True)
    r_series.run()

    # Export the summed raster
    r_out = grass_module('r.out.gdal',
                            input=f"{dsm}_solar_irradiance",
                            output=f"{dsm}_solar_irradiance.tif",
                            format="GTiff",
                            createopt="TFW=YES,COMPRESS=LZW",
                            overwrite=True)
    r_out.run()

    if cleanup:
        g_remove = grass_module('g.remove',
                                type='raster',
                                name=rasters,
                                flags='f') # force without prompt
        g_remove.run()

    return f"{dsm}_solar_irradiance"
