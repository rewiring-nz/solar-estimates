def create_stats(area, building_outlines, rooftop_raster, output_csv, grass_module):
    """Calculate statistics of rooftop solar irradiance for building outlines."""

    v_rast_stats = grass_module(
        "v.rast.stats",
        map=building_outlines,
        raster=rooftop_raster,
        column_prefix="roof",
        method=["sum", "number"],
        flags="c",
    )
    v_rast_stats.run()

    v_extract = grass_module(
        "v.extract",
        input=building_outlines,
        output="filtered_buildings",
        where="roof_sum IS NOT NULL",
        overwrite=True,
    )
    v_extract.run()

    # Add several columns for Wh conversions, area, and usable pixels
    v_db_addcolumn = grass_module(
        "v.db.addcolumn",
        map="filtered_buildings",
        columns=[
            "roof_kwh DOUBLE PRECISION", 
            "roof_mwh DOUBLE PRECISION",
            "area_sqm DOUBLE PRECISION",
            "usable_sqm INTEGER" 
        ],
    )
    v_db_addcolumn.run()

    v_db_update_kwh = grass_module(
        "v.db.update",
        map="filtered_buildings",
        column="roof_kwh",
        query_column="CAST(roof_sum AS DOUBLE PRECISION) / 1000.0"
    )
    v_db_update_kwh.run()

    v_db_update_mwh = grass_module(
        "v.db.update",
        map="filtered_buildings",
        column="roof_mwh",
        query_column="CAST(roof_sum AS DOUBLE PRECISION) / 1000000.0"
    )
    v_db_update_mwh.run()
    
    # Copy the pixel count from roof_number to usable_sqm
    v_db_update_pixels = grass_module(
        "v.db.update",
        map="filtered_buildings",
        column="usable_sqm",
        query_column="roof_number"
    )
    v_db_update_pixels.run()

    v_db_update_area = grass_module(
        "v.to.db",
        map="filtered_buildings",
        option="area",
        columns="area_sqm",
        units="meters",
        overwrite=True
    )
    v_db_update_area.run()

    if output_csv:
        # roof_sum (Wh) and roof_kwh (kWh) are also available
        v_db_select = grass_module(
            "v.db.select",
            map="filtered_buildings",
            columns="building_i, suburb_loc, town_city, roof_mwh, area_sqm, usable_sqm",
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
