"""
Statistics helpers for rooftop solar calculations in GRASS GIS.

This module provides helpers to compute per-building statistics by sampling
rasters (clear-sky irradiance and optional WRF-adjusted irradiance) using
GRASS vector/raster database functions. The workflow implemented here is:

1. Use `v.rast.stats` to compute aggregated raster statistics (sum, count)
   for each building polygon.
2. Create and update attribute columns (kWh, MWh, usable sqm) using
   `v.db.addcolumn` and `v.db.update`.
3. Optionally compute WRF-derived statistics and a percent loss comparison
   between the calculated clear-sky values and WRF measured values.
4. Export results to a GeoPackage and optionally a CSV.
"""

from typing import Any, Optional


def _calculate_clear_sky_stats(
    building_outlines: str, rooftop_raster: str, grass_module: Any
) -> str:
    """Calculate clear-sky solar irradiance statistics for building outlines.

    This function uses `v.rast.stats` to compute:
      - `roof_sum`: the sum of raster pixel values overlapping each building
      - `roof_number`: the count of pixels used in the sum

    It then adds and populates some derived columns:
    `roof_kwh`, `roof_mwh`, `usable_sqm`

    Args:
        building_outlines: Name of the building polygon vector map in GRASS.
        rooftop_raster: Name of the raster containing per-pixel irradiance
            (expected units: Wh per pixel over the period).
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The input `building_outlines` vector name.
    """
    # Compute per-feature raster statistics: sum and number of pixels
    v_rast_stats = grass_module(
        "v.rast.stats",
        map=building_outlines,
        raster=rooftop_raster,
        column_prefix="roof",
        method=["sum", "number"],
        flags="c",
    )
    v_rast_stats.run()

    # Add columns for kWh, MWh and usable area (pixel count)
    v_db_addcolumn = grass_module(
        "v.db.addcolumn",
        map=building_outlines,
        columns=[
            "roof_kwh DOUBLE PRECISION",
            "roof_mwh DOUBLE PRECISION",
            "usable_sqm INTEGER",
        ],
    )
    v_db_addcolumn.run()

    # Populate kWh and MWh columns by converting roof_sum (Wh) to larger units
    v_db_update_kwh = grass_module(
        "v.db.update",
        map=building_outlines,
        column="roof_kwh",
        query_column="CAST(roof_sum AS DOUBLE PRECISION) / 1000.0",
    )
    v_db_update_kwh.run()

    v_db_update_mwh = grass_module(
        "v.db.update",
        map=building_outlines,
        column="roof_mwh",
        query_column="CAST(roof_sum AS DOUBLE PRECISION) / 1000000.0",
    )
    v_db_update_mwh.run()

    # Copy pixel count into usable_sqm
    v_db_update_pixels = grass_module(
        "v.db.update",
        map=building_outlines,
        column="usable_sqm",
        query_column="roof_number",
    )
    v_db_update_pixels.run()

    return building_outlines


def _calculate_wrf_stats(
    building_outlines: str, wrf_raster: str, grass_module: Any
) -> str:
    """Calculate statistics from a WRF-derived raster for building outlines.

    This computes a per-building sum of raster pixel values from the provided
    `wrf_raster` and creates a `wrf_mwh` column containing the summed value in MWh.

    Args:
        building_outlines: Name of the building polygon vector in GRASS.
        wrf_raster: Name of the WRF-derived raster in GRASS (same units as rooftop raster).
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The input `building_outlines` vector name.
    """
    # Compute per-building sum for the WRF raster
    v_rast_stats_wrf = grass_module(
        "v.rast.stats",
        map=building_outlines,
        raster=wrf_raster,
        column_prefix="wrf",
        method=["sum"],
        flags="c",
    )
    v_rast_stats_wrf.run()

    # Add column for summed WRF values in MWh
    v_db_addcolumn = grass_module(
        "v.db.addcolumn",
        map=building_outlines,
        columns=["wrf_mwh DOUBLE PRECISION"],
    )
    v_db_addcolumn.run()

    # Populate wrf_mwh by converting wrf_sum (Wh) to MWh
    v_db_update_wrf_mwh = grass_module(
        "v.db.update",
        map=building_outlines,
        column="wrf_mwh",
        query_column="CAST(wrf_sum AS DOUBLE PRECISION) / 1000000.0",
    )
    v_db_update_wrf_mwh.run()

    return building_outlines


def _export_combined_stats(
    area: str,
    building_outlines: str,
    output_csv: bool,
    grass_module: Any,
    has_wrf: bool = False,
) -> str:
    """Combine statistics, compute comparison metrics, and export results.

    Steps:
      - Filter out features without `roof_sum` (only export buildings with values).
      - Add an `area_sqm` attribute and populate it.
      - If WRF data is present, add and compute a `percent_loss`.
      - Optionally export CSV and always export a GeoPackage with stats.

    Args:
        area: Base name for output files (used in file naming).
        building_outlines: Name of the building vector in GRASS (after stats computed).
        output_csv: Whether to create a CSV output in addition to the GeoPackage.
        grass_module: The GRASS Python scripting Module class.
        has_wrf: Whether WRF-derived statistics have been computed and should be included.

    Returns:
        The path to the generated GeoPackage file containing building statistics.
    """
    # Keep only buildings that have roof_sum (skip features without raster overlap)
    v_extract = grass_module(
        "v.extract",
        input=building_outlines,
        output="filtered_buildings",
        where="roof_sum IS NOT NULL",
        overwrite=True,
    )
    v_extract.run()

    # Add area column to store building area
    v_db_addcolumn = grass_module(
        "v.db.addcolumn",
        map="filtered_buildings",
        columns=["area_sqm DOUBLE PRECISION"],
    )
    v_db_addcolumn.run()

    # If WRF stats are available, add a percent_loss column and compute it
    if has_wrf:
        v_db_addcolumn_wrf = grass_module(
            "v.db.addcolumn",
            map="filtered_buildings",
            columns=["percent_loss DOUBLE PRECISION"],
        )
        v_db_addcolumn_wrf.run()

        # Compute percentage loss: (calculated - measured) / calculated * 100
        v_db_update_percent_loss = grass_module(
            "v.db.update",
            map="filtered_buildings",
            column="percent_loss",
            query_column=(
                "((CAST(roof_sum AS DOUBLE PRECISION) - CAST(wrf_sum AS DOUBLE PRECISION)) "
                "/ CAST(roof_sum AS DOUBLE PRECISION)) * 100.0"
            ),
        )
        v_db_update_percent_loss.run()

    # Populate area_sqm by computing geometry area in meters
    v_db_update_area = grass_module(
        "v.to.db",
        map="filtered_buildings",
        option="area",
        columns="area_sqm",
        units="meters",
        overwrite=True,
    )
    v_db_update_area.run()

    # Optionally export a CSV summary (columns depend on WRF presence)
    if output_csv:
        if has_wrf:
            columns = "building_i, suburb_loc, town_city, roof_mwh, wrf_mwh, percent_loss, area_sqm, usable_sqm"
        else:
            columns = "building_i, suburb_loc, town_city, roof_mwh, area_sqm, usable_sqm"

        v_db_select = grass_module(
            "v.db.select",
            map="filtered_buildings",
            columns=columns,
            where="roof_sum IS NOT NULL",
            file=f"{area}_building_stats.csv",
            overwrite=True,
        )
        v_db_select.run()

    # Export filtered buildings (with attributes) to a GeoPackage
    v_out_ogr = grass_module(
        "v.out.ogr",
        input="filtered_buildings",
        output=f"{area}_building_stats.gpkg",
        format="GPKG",
        output_layer="building_stats",
        overwrite=True,
    )
    v_out_ogr.run()

    return f"{area}_building_stats.gpkg"


def create_stats(
    area: str,
    building_outlines: str,
    rooftop_raster: str,
    grass_module: Any,
    wrf_raster: Optional[str] = None,
    output_csv: bool = True,
) -> str:
    """High-level workflow to produce building-level rooftop irradiance statistics.

    Args:
        area: Descriptive name for the area used as a prefix for output files.
        building_outlines: GRASS vector name containing building polygons.
        rooftop_raster: GRASS raster name containing rooftop irradiance (Wh).
        grass_module: The GRASS Python scripting Module class.
        wrf_raster: Optional GRASS raster name for WRF-adjusted irradiance.
        output_csv: If True, also export a CSV summary. Defaults to True.

    Returns:
        Path to the generated GeoPackage file containing building statistics.
    """
    # Compute clear-sky (calculated) stats and update vector attributes
    building_outlines = _calculate_clear_sky_stats(
        building_outlines, rooftop_raster, grass_module
    )

    # Optionally compute WRF-derived stats
    has_wrf = wrf_raster is not None
    if has_wrf:
        building_outlines = _calculate_wrf_stats(
            building_outlines, wrf_raster, grass_module
        )

    # Export combined stats to GeoPackage and optionally CSV
    gpkg_file = _export_combined_stats(
        area, building_outlines, output_csv, grass_module, has_wrf=has_wrf
    )

    return gpkg_file
