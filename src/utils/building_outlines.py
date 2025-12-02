def load_building_outlines(shapefile: str, output_name: str, grass_module):
    """Load building outlines from a shapefile into GRASS GIS."""

    v_in = grass_module("v.in.ogr", input=shapefile, output=output_name, overwrite=True)
    v_in.run()

    return output_name


def apply_building_mask(building_vector: str, output_name: str, grass_module):
    """Apply a temporary mask of building outlines."""

    r_mask = grass_module("r.mask", vector=building_vector, overwrite=True)
    r_mask.run()

    return output_name


def remove_masks(grass_module):
    """Remove any applied masks."""

    try:
        r_mask = grass_module("r.mask", flags="r")
        r_mask.run()
    except Exception as e:
        print(f"Error removing masks: {e}")

    return None


def calculate_outline_raster(
    solar_irradiance_raster: str, building_vector: str, output_name: str, grass_module
):
    """Copy values to a raster - should only be run when the building mask is active."""

    apply_building_mask(
        building_vector, output_name="building_mask", grass_module=grass_module
    )

    r_mapcalc = grass_module(
        "r.mapcalc",
        expression=f"{output_name} = {solar_irradiance_raster}",
        overwrite=True,
    )
    r_mapcalc.run()

    return output_name


def export_final_raster(
    raster_name: str,
    slope: str,
    aspect: str,
    output_tif: str,
    grass_module,
):
    """Export the final raster to a GeoTIFF file with slope and aspect as additional bands."""

    # Create an imagery group with the three rasters
    group_name = f"{raster_name}_group"
    i_group = grass_module(
        "i.group",
        group=group_name,
        input=f"{raster_name},{slope},{aspect}",
    )
    i_group.run()

    # Export the group as a multi-band GeoTIFF
    r_out_multiband = grass_module(
        "r.out.gdal",
        input=group_name,
        output=output_tif,
        format="GTiff",
        createopt="TFW=YES,COMPRESS=LZW",
        overwrite=True,
    )
    r_out_multiband.run()

    # Clean up the group
    g_remove = grass_module(
        "g.remove",
        type="group",
        name=group_name,
        flags="f",
    )
    g_remove.run()

    return output_tif
