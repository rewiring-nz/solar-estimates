def _calculate_clear_sky_stats(building_outlines, rooftop_raster, grass_module):
    """Calculate clear-sky solar irradiance statistics for buildings."""

    # Creates:
    # roof_sum - total number of pixel values (Wh)
    # roof_number - number of pixels used in calculation
    v_rast_stats = grass_module(
        "v.rast.stats",
        map=building_outlines,
        raster=rooftop_raster,
        column_prefix="roof",
        method=["sum", "number"],
        flags="c",
    )
    v_rast_stats.run()

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

    # Copy the pixel count from roof_number to usable_sqm
    v_db_update_pixels = grass_module(
        "v.db.update",
        map=building_outlines,
        column="usable_sqm",
        query_column="roof_number",
    )
    v_db_update_pixels.run()

    return building_outlines


def _calculate_wrf_stats(building_outlines, wrf_raster, grass_module):
    """Calculate WRF measured radiation statistics for buildings."""

    # Creates:
    # wrf_sum - total number of pixel values from WRF raster (Wh)
    v_rast_stats_wrf = grass_module(
        "v.rast.stats",
        map=building_outlines,
        raster=wrf_raster,
        column_prefix="wrf",
        method=["sum"],
        flags="c",
    )
    v_rast_stats_wrf.run()

    v_db_addcolumn = grass_module(
        "v.db.addcolumn",
        map=building_outlines,
        columns=["wrf_mwh DOUBLE PRECISION"],
    )
    v_db_addcolumn.run()

    # Calculate WRF measured MWh
    v_db_update_wrf_mwh = grass_module(
        "v.db.update",
        map=building_outlines,
        column="wrf_mwh",
        query_column="CAST(wrf_sum AS DOUBLE PRECISION) / 1000000.0",
    )
    v_db_update_wrf_mwh.run()

    return building_outlines


def _export_combined_stats(area, building_outlines, output_csv, grass_module):
    """Combine clear-sky and WRF statistics, calculate comparison metrics, and export."""

    # Extract only buildings with roof_sum values
    v_extract = grass_module(
        "v.extract",
        input=building_outlines,
        output="filtered_buildings",
        where="roof_sum IS NOT NULL",
        overwrite=True,
    )
    v_extract.run()

    # Add several columns:
    # percent_loss: percentage difference between calculated and measured
    # area_sqm: building footprint area in square meters
    v_db_addcolumn = grass_module(
        "v.db.addcolumn",
        map="filtered_buildings",
        columns=[
            "percent_loss DOUBLE PRECISION",
            "area_sqm DOUBLE PRECISION",
        ],
    )
    v_db_addcolumn.run()

    # Calculate percentage loss: (calculated - measured) / calculated * 100
    v_db_update_percent_loss = grass_module(
        "v.db.update",
        map="filtered_buildings",
        column="percent_loss",
        query_column="((CAST(roof_sum AS DOUBLE PRECISION) - CAST(wrf_sum AS DOUBLE PRECISION)) / CAST(roof_sum AS DOUBLE PRECISION)) * 100.0",
    )
    v_db_update_percent_loss.run()

    v_db_update_area = grass_module(
        "v.to.db",
        map="filtered_buildings",
        option="area",
        columns="area_sqm",
        units="meters",
        overwrite=True,
    )
    v_db_update_area.run()

    if output_csv:
        # roof_sum (Wh) and roof_kwh (kWh) are also available
        v_db_select = grass_module(
            "v.db.select",
            map="filtered_buildings",
            columns="building_i, suburb_loc, town_city, roof_mwh, wrf_mwh, percent_loss, area_sqm, usable_sqm",
            where="roof_sum IS NOT NULL",
            file=f"{area}_building_stats.csv",
            overwrite=True,
        )
        v_db_select.run()

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
    area, building_outlines, rooftop_raster, wrf_raster, output_csv, grass_module
):
    """Calculate statistics of rooftop solar irradiance for building outlines."""

    building_outlines = _calculate_clear_sky_stats(
        building_outlines, rooftop_raster, grass_module
    )

    building_outlines = _calculate_wrf_stats(
        building_outlines, wrf_raster, grass_module
    )

    gpkg_file = _export_combined_stats(
        area, building_outlines, output_csv, grass_module
    )

    return gpkg_file
