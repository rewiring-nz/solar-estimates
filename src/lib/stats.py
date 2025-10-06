def create_stats(building_outlines, rooftop_raster, output_csv, grass_module):
    """Calculate statistics of rooftop solar irradiance for building outlines."""

    v_rast_stats = grass_module(
        "v.rast.stats",
        map=building_outlines,
        raster=rooftop_raster,
        column_prefix="roof",
        method="sum",
        flags="c",
    )
    v_rast_stats.run()

    v_db_update = grass_module(
        "v.db.update",
        map=building_outlines,
        column="roof_sum",
        value="roof_sum / 1000.0",
        where="roof_sum IS NOT NULL",
    )
    v_db_update.run()

    if output_csv:
        v_db_select = grass_module(
            "v.db.select",
            map=building_outlines,
            columns="building_i, suburb_loc, town_city, roof_sum",
            where="roof_sum IS NOT NULL",
            file=output_csv,
            overwrite=True,
        )

        v_db_select.run()

    v_extract = grass_module(
        "v.extract",
        input=building_outlines,
        output="filtered_buildings",
        where="roof_sum IS NOT NULL",
        overwrite=True,
    )
    v_extract.run()

    v_out_ogr = grass_module(
        "v.out.ogr",
        input="filtered_buildings",
        output="building_stats.shp",
        format="ESRI_Shapefile",
        output_layer="building_stats",
        overwrite=True,
    )
    v_out_ogr.run()
