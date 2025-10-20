import glob
from osgeo import gdal


def load_raster_into_grass(input_tif: str, output_name: str, grass_module):
    """ "Load a raster file into GRASS GIS, and set the working region to the raster's extent."""

    r_in = grass_module(
        "r.in.gdal", input=input_tif, output=output_name, band=1, overwrite=True
    )
    r_in.run()

    g_region = grass_module(
        "g.region", raster=output_name, flags="p"
    )  # print region details
    g_region.run()

    return output_name


def load_virtual_raster_into_grass(input_vrt: str, output_name: str, grass_module):
    """ "Load a VRT (Virtual Raster) file into GRASS GIS, and set the working region to the raster's extent."""

    r_external = grass_module(
        "r.external", input=input_vrt, output=output_name, band=1, overwrite=True
    )
    r_external.run()

    g_region = grass_module(
        "g.region", raster=output_name, flags="p"
    )  # print region details
    g_region.run()

    return output_name


def merge_rasters(
    dsm_file_glob: str, area_name: str, min_value_threshold=0, nodata_value=0
):
    """Merge tiled DSM files into a single GeoTIFF using GDAL."""

    # DSM files are likely tiled into multiple GeoTIFFs
    dsm_files = glob.glob(dsm_file_glob)
    if not dsm_files:
        raise FileNotFoundError(f"No files found for pattern: {dsm_file_glob}")

    # Build a VRT (Virtual Raster) from the input files
    # See: https://gdal.org/en/stable/drivers/raster/vrt.html
    vrt_options = gdal.BuildVRTOptions(resampleAlg=gdal.GRA_NearestNeighbour)
    gdal.BuildVRT(f"{area_name}_merged.vrt", dsm_files, options=vrt_options)

    # Translate the VRT to a GeoTIFF
    # translate_options = gdal.TranslateOptions(format='GTiff')
    # gdal.Translate(f"{area_name}_merged.tif", f"{area_name}_merged.vrt", options=translate_options)

    # If the raster has -9999 as minimum, set this to a supplied value
    # dataset = gdal.Open(output_tif, gdal.GA_Update)
    # if dataset is None:
    #     raise RuntimeError(f"Failed to open translated file: {output_tif}")
    # band = dataset.GetRasterBand(1)
    # data = band.ReadAsArray()

    # data[data < min_value_threshold] = nodata_value
    # band.WriteArray(data)
    # band.SetNoDataValue(nodata_value)
    # band.FlushCache()
    # del dataset

    return f"{area_name}_merged.vrt"


def calculate_slope_aspect_rasters(dsm: str, grass_module):
    """Calculate slope and aspect rasters from the DSM. Returns the names
    of the aspect and slope rasters."""

    r_slope_aspect = grass_module(
        "r.slope.aspect",
        elevation=dsm,
        slope=f"{dsm}_slope",
        aspect=f"{dsm}_aspect",
        format="degrees",
        precision="FCELL",
        a=True,
        zscale=1,
        min_slope=0,
        overwrite=True,
    )
    r_slope_aspect.run()

    return f"{dsm}_aspect", f"{dsm}_slope"


def filter_raster_by_slope(
    input_raster: str,
    slope_raster: str,
    max_slope_degrees: float,
    output_name: str,
    grass_module,
):
    """Filter a raster to remove pixels where slope exceeds the max_slope_degrees."""

    r_mapcalc = grass_module(
        "r.mapcalc",
        expression=f"{output_name} = if({slope_raster} <= {max_slope_degrees}, {input_raster}, null())",
        overwrite=True,
    )
    r_mapcalc.run()

    return output_name
