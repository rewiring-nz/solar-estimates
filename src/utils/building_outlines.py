"""Utilities for building outlines and building-masked raster exports."""

from typing import Any


def load_building_outlines(shapefile: str, output_name: str, grass_module: Any) -> str:
    """Import building outlines (vector) from a shapefile into GRASS.

    This uses the ``v.in.ogr`` GRASS module to import a vector dataset from a
    shapefile into the current GRASS mapset.

    Args:
        shapefile: Path to the directory containing a building footprints shapefile.
        output_name: Name to assign to the vector map inside GRASS.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The GRASS vector name.
    """
    grass_module("v.in.ogr", input=shapefile, output=output_name, overwrite=True).run()
    return output_name


def apply_building_mask(building_vector: str, grass_module: Any) -> None:
    """Apply a raster mask based on building outlines.

    The mask created by ``r.mask`` restricts subsequent raster operations to
    the area covered by the given vector.

    Args:
        building_vector: Name of the building footprint vector in GRASS.
        grass_module: The GRASS Python scripting Module class.
    """
    grass_module("r.mask", vector=building_vector, overwrite=True).run()


def remove_masks(grass_module: Any) -> None:
    """Remove any active raster mask(s) in the current GRASS session.

    This helper attempts to reset raster masking by calling ``r.mask -r``.

    Args:
        grass_module: The GRASS Python scripting Module class.

    Raises:
        Exception: if removing the mask encounters an error.
    """
    try:
        grass_module("r.mask", flags="r").run()
    except Exception as e:
        print(f"Warning: error removing GRASS mask: {e}")


def calculate_outline_raster(
    solar_irradiance_raster: str,
    building_vector: str,
    output_name: str,
    grass_module: Any,
) -> str:
    """Create a raster containing values only over building footprints.

    Args:
        solar_irradiance_raster: Name of the solar irradiance raster in GRASS.
        building_vector: Name of the building footprint vector in GRASS.
        output_name: Name to assign to the resulting building-only raster.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The GRASS raster name.
    """
    try:
        apply_building_mask(building_vector, grass_module=grass_module)
        grass_module(
            "r.mapcalc",
            expression=f"{output_name} = {solar_irradiance_raster}",
            overwrite=True,
        ).run()
    finally:
        remove_masks(grass_module=grass_module)

    return output_name


def export_final_raster(
    raster_name: str,
    slope: str,
    aspect: str,
    output_tif: str,
    grass_module: Any,
) -> str:
    """Export a multi-band GeoTIFF containing raster, slope, and aspect.

    This function:
      - Creates an imagery group containing the three rasters using ``i.group``.
      - Calls ``r.out.gdal`` to export the group as a multi-band GeoTIFF.
      - Removes the temporary imagery group.

    Args:
        raster_name: Name of the primary raster to export (e.g. building-only GHI).
        slope: Name of the slope raster to include as a band.
        aspect: Name of the aspect raster to include as a band.
        output_tif: Path for the output GeoTIFF file to create.
        grass_module: The GRASS Python scripting Module class.

    Returns:
        The ``output_tif`` path for convenience.
    """
    group_name = f"{raster_name}_group"

    grass_module(
        "i.group",
        group=group_name,
        input=f"{raster_name},{slope},{aspect}",
    ).run()

    grass_module(
        "r.out.gdal",
        input=group_name,
        output=output_tif,
        format="GTiff",
        createopt="TFW=YES,COMPRESS=LZW",
        overwrite=True,
    ).run()

    grass_module(
        "g.remove",
        type="group",
        name=group_name,
        flags="f",
    ).run()

    return output_tif
