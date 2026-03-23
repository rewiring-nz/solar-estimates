"""Statistics helpers for rooftop solar calculations in GRASS GIS."""

from typing import Any, Optional

from .dsm import get_raster_resolution


def _calculate_clear_sky_stats(
    building_outlines: str,
    irradiance_raster: str,
    grass_module: Any,
) -> str:
    """Compute per-building clear-sky irradiance statistics.

    Samples the filtered irradiance raster with ``v.rast.stats``.

    Args:
        building_outlines: Name of the building polygon vector map in GRASS.
        irradiance_raster: Name of the solar irradiance raster in GRASS
            (units: Wh/m² over the period of interest).
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The input ``building_outlines`` vector name.
    """
    ewres, nsres = get_raster_resolution(irradiance_raster, grass_module)
    cell_area = abs(ewres * nsres)

    grass_module(
        "v.rast.stats",
        map=building_outlines,
        raster=irradiance_raster,
        column_prefix="roof",
        method=["average", "number"],
        flags="c",
    ).run()

    grass_module(
        "v.db.addcolumn",
        map=building_outlines,
        columns=["usable_sqm DOUBLE PRECISION"],
    ).run()

    grass_module(
        "v.db.addcolumn",
        map=building_outlines,
        columns=[
            "roof_kwh DOUBLE PRECISION",
            "roof_mwh DOUBLE PRECISION",
        ],
    ).run()

    grass_module(
        "v.db.update",
        map=building_outlines,
        column="usable_sqm",
        query_column=f"CAST(roof_number AS DOUBLE PRECISION) * {cell_area}",
    ).run()

    grass_module(
        "v.db.update",
        map=building_outlines,
        column="roof_kwh",
        query_column=(
            "CAST(roof_average AS DOUBLE PRECISION) "
            "* CAST(usable_sqm AS DOUBLE PRECISION) "
            "/ 1000.0"
        ),
    ).run()

    grass_module(
        "v.db.update",
        map=building_outlines,
        column="roof_mwh",
        query_column=(
            "CAST(roof_average AS DOUBLE PRECISION) "
            "* CAST(usable_sqm AS DOUBLE PRECISION) "
            "/ 1000000.0"
        ),
    ).run()

    return building_outlines


def _calculate_wrf_stats(
    building_outlines: str,
    wrf_raster: str,
    grass_module: Any,
) -> str:
    """Compute per-building WRF-derived irradiance statistics.

    Keeps the existing WRF summary path based on summed raster values.

    Args:
        building_outlines: Name of the building polygon vector in GRASS.
        wrf_raster: Name of the WRF-derived raster in GRASS.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The input ``building_outlines`` vector name.
    """
    grass_module(
        "v.rast.stats",
        map=building_outlines,
        raster=wrf_raster,
        column_prefix="wrf",
        method=["sum"],
        flags="c",
    ).run()

    grass_module(
        "v.db.addcolumn",
        map=building_outlines,
        columns=["wrf_mwh DOUBLE PRECISION"],
    ).run()

    grass_module(
        "v.db.update",
        map=building_outlines,
        column="wrf_mwh",
        query_column="CAST(wrf_sum AS DOUBLE PRECISION) / 1000000.0",
    ).run()

    return building_outlines


def _export_combined_stats(
    area: str,
    building_outlines: str,
    output_csv: bool,
    grass_module: Any,
    has_wrf: bool = False,
) -> str:
    """Filter buildings with valid stats, annotate, and export.

    Steps:
      - Extract only buildings where ``roof_average IS NOT NULL`` (i.e. the
        irradiance raster had coverage over that polygon).
      - Add and populate an ``area_sqm`` column from polygon geometry.
      - Optionally add a ``percent_loss`` column when WRF data is present.
      - Export to GeoPackage; optionally also export a CSV.

    Args:
        area: Base name for output files.
        building_outlines: Name of the building vector in GRASS (stats already
            computed).
        output_csv: Whether to create a CSV in addition to the GeoPackage.
        grass_module: The GRASS Python scripting Module class.
        has_wrf: Whether WRF-derived statistics have been computed.

    Returns:
        Path to the generated GeoPackage file.
    """
    grass_module(
        "v.extract",
        input=building_outlines,
        output="filtered_buildings",
        where="roof_average IS NOT NULL",
        overwrite=True,
    ).run()

    grass_module(
        "v.db.addcolumn",
        map="filtered_buildings",
        columns=["area_sqm DOUBLE PRECISION"],
    ).run()

    grass_module(
        "v.to.db",
        map="filtered_buildings",
        option="area",
        columns="area_sqm",
        units="meters",
        overwrite=True,
    ).run()

    if has_wrf:
        grass_module(
            "v.db.addcolumn",
            map="filtered_buildings",
            columns=["percent_loss DOUBLE PRECISION"],
        ).run()

        grass_module(
            "v.db.update",
            map="filtered_buildings",
            column="percent_loss",
            query_column=(
                "((CAST(roof_mwh AS DOUBLE PRECISION) "
                "- CAST(wrf_mwh AS DOUBLE PRECISION)) "
                "/ CAST(roof_mwh AS DOUBLE PRECISION)) * 100.0"
            ),
        ).run()

    if output_csv:
        if has_wrf:
            columns = (
                "building_i, suburb_loc, town_city, "
                "roof_mwh, wrf_mwh, percent_loss, area_sqm, usable_sqm"
            )
        else:
            columns = (
                "building_i, suburb_loc, town_city, roof_mwh, area_sqm, usable_sqm"
            )

        grass_module(
            "v.db.select",
            map="filtered_buildings",
            columns=columns,
            where="roof_average IS NOT NULL",
            file=f"{area}_building_stats.csv",
            overwrite=True,
        ).run()

    grass_module(
        "v.out.ogr",
        input="filtered_buildings",
        output=f"{area}_building_stats.gpkg",
        format="GPKG",
        output_layer="building_stats",
        overwrite=True,
    ).run()

    return f"{area}_building_stats.gpkg"


def create_stats(
    area: str,
    building_outlines: str,
    rooftop_raster: str,
    grass_module: Any,
    wrf_raster: Optional[str] = None,
    output_csv: bool = True,
) -> str:
    """Produce building-level rooftop irradiance statistics.

    Args:
        area: Descriptive name used as a prefix for output files.
        building_outlines: GRASS vector name containing building polygons.
        rooftop_raster: GRASS raster name containing filtered irradiance in Wh/m².
        grass_module: The GRASS Python scripting Module class.
        wrf_raster: Optional GRASS raster name for WRF-adjusted irradiance.
        output_csv: If ``True``, also export a CSV summary.

    Returns:
        Path to the generated GeoPackage file.
    """
    building_outlines = _calculate_clear_sky_stats(
        building_outlines,
        rooftop_raster,
        grass_module,
    )

    has_wrf = wrf_raster is not None
    if has_wrf:
        building_outlines = _calculate_wrf_stats(
            building_outlines,
            wrf_raster,
            grass_module,
        )

    return _export_combined_stats(
        area, building_outlines, output_csv, grass_module, has_wrf=has_wrf
    )
