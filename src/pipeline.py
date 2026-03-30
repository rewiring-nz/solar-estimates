#!/usr/bin/env python3
"""
CLI tool for estimating solar irradiance on buildings from digital surface models.
"""

import argparse
import platform
import sys
import time
from pathlib import Path

from utils.building_outlines import (
    calculate_outline_raster,
    export_final_raster,
    load_building_outlines,
    remove_masks,
)
from utils.dsm import (
    calculate_horizon_raster,
    calculate_slope_aspect_rasters,
    combine_horizon_rasters_per_direction,
    filter_raster_by_slope,
    load_virtual_raster_into_grass,
    merge_rasters,
    normalize_horizon_raster_names,
)
from utils.grass_utils import setup_grass
from utils.logging_config import get_logger, setup_logging
from utils.misc import calculate_tif_size_MB, generate_duration_message, get_dir_size_MB
from utils.solar_irradiance import (
    calculate_solar_coefficients,
    calculate_solar_irradiance_interpolated,
)
from utils.stats import create_stats
from utils.wrf import (
    calculate_wrf_adjusted_per_day,
    calculate_wrf_on_buildings,
    cleanup_wrf_intermediates,
    process_wrf_for_grass,
)


def detect_grass_base():
    """Auto-detect GRASS GIS installation path based on operating system."""
    if platform.system() == "Darwin":
        return "/Applications/GRASS-8.4.app/Contents/Resources"
    elif platform.system() == "Linux":
        return "/usr/lib/grass84"
    else:
        return None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Estimate solar irradiance on buildings from DSM data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--dsm-glob",
        default="data/shotover_country/*.tif",
        help='Glob for DSM GeoTIFF files to use as inputs (default: "data/shotover_country/*.tif")',
    )

    parser.add_argument(
        "--building-dir",
        default="data/queenstown_lakes_building_outlines",
        help='Directory containing building outline shapefiles to use as inputs (default: "data/queenstown_lakes_building_outlines")',
    )

    parser.add_argument(
        "--area-name",
        default="shotover_country",
        help='Descriptive name for the area that will be used in outputs (default: "shotover_country")',
    )

    parser.add_argument(
        "--building-layer-name",
        default="queenstown_lakes_buildings",
        help='Name of the output building outline layer (default: "queenstown_lakes_buildings")',
    )

    parser.add_argument(
        "--grass-base",
        default=None,
        help="Path to GRASS GIS installation base directory (auto-detected if not provided)",
    )

    parser.add_argument(
        "--output-prefix",
        default="solar_on_buildings",
        help='Prefix for output files (default: "solar_on_buildings")',
    )

    parser.add_argument(
        "--max-slope",
        type=float,
        default=45.0,
        help="Maximum slope in degrees for filtering (default: 45.0)",
    )

    parser.add_argument(
        "--key-days",
        type=int,
        nargs="+",
        default=[1, 7],
        help="Day numbers for solar irradiance calculation (default: 1, 7)",
    )

    parser.add_argument(
        "--time-step",
        type=float,
        default=1.0,
        help="Time step when computing all-day radiation sums in decimal hours (default: 1.0)",
    )

    parser.add_argument(
        "--export-rasters",
        action="store_true",
        help="Export rasters (solar irradiance, coefficient, WRF adjusted, final) as GeoTIFFs",
    )

    # WRF-related arguments
    parser.add_argument(
        "--wrf-file",
        default=None,
        help="Path to WRF NetCDF file for measured radiation data (optional)",
    )

    parser.add_argument(
        "--source-crs",
        default="EPSG:4326",
        help='Source CRS for WRF data (default: "EPSG:4326")',
    )

    parser.add_argument(
        "--target-crs",
        default="EPSG:2193",
        help='Target CRS for WRF reprojection (default: "EPSG:2193" - NZGD2000)',
    )

    # Horizon pre-calculation arguments
    parser.add_argument(
        "--calculate-horizon",
        action="store_true",
        help="Pre-calculate horizon rasters using r.horizon and feed them to r.sun",
    )

    parser.add_argument(
        "--dsm-buffer-distance",
        type=float,
        default=1000.0,
        help="Maximum search distance in metres for local (DSM) horizon (default: 1000.0)",
    )

    parser.add_argument(
        "--dem-buffer-distance",
        type=float,
        default=50000.0,
        help="Maximum search distance in metres for regional (DEM) horizon (default: 50000.0)",
    )

    parser.add_argument(
        "--horizon-azimuth-steps",
        type=int,
        default=16,
        help="Number of azimuth directions for horizon calculation (default: 16)",
    )

    parser.add_argument(
        "--horizon-start-azimuth",
        type=float,
        default=0.0,
        help="Start azimuth in degrees for horizon calculation (default: 0.0)",
    )

    parser.add_argument(
        "--horizon-end-azimuth",
        type=float,
        default=360.0,
        help="End azimuth in degrees for horizon calculation (default: 360.0)",
    )

    parser.add_argument(
        "--input-dem-glob",
        default=None,
        help="Glob pattern for DEM tiles used for regional horizon (optional)",
    )

    return parser.parse_args()


def main():
    logger = setup_logging()
    start_time = time.time()
    logger.info("Starting pipeline")

    args = parse_args()

    # Validate inputs
    if not Path(args.building_dir).exists():
        if not Path(f"{args.building_dir}.zip").exists():
            logger.error("Building directory does not exist: %s", args.building_dir)
            sys.exit(1)

    # Auto-detect or validate GRASS base path
    grass_base = args.grass_base
    if grass_base is None:
        grass_base = detect_grass_base()
        if grass_base is None:
            logger.error(
                "Could not auto-detect GRASS GIS installation for %s. "
                "Please provide --grass-base argument.",
                platform.system(),
            )
            sys.exit(1)
        logger.info("Auto-detected GRASS GIS at: %s", grass_base)

    # Set up environment
    logger.info("Setting up GRASS GIS from: %s", grass_base)
    gscript, Module = setup_grass(gisbase=grass_base)

    logger.info("Creating output dir...")
    output_dir = Path(f"data/outputs/{args.area_name}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Main workflow
    logger.info("Removing existing masks...")
    remove_masks(grass_module=Module)

    logger.info("Merging rasters from: %s", args.dsm_glob)
    merged_virtual_raster = merge_rasters(
        dsm_file_glob=args.dsm_glob, area_name=args.area_name, output_dir=output_dir
    )

    logger.info("Loading virtual raster into GRASS...")
    virtual_raster = load_virtual_raster_into_grass(
        input_vrt=merged_virtual_raster,
        output_name=f"{args.area_name}_dsm",
        grass_module=Module,
    )

    logger.info("Calculating slope and aspect...")
    aspect, slope = calculate_slope_aspect_rasters(
        dsm=virtual_raster, grass_module=Module
    )

    # Horizon pre-calculation (optional)
    sun_horizon_basename = None
    sun_horizon_step = None

    if args.calculate_horizon:
        # Compute the angular step once; used for both r.horizon and r.sun.
        start_az = args.horizon_start_azimuth
        end_az = args.horizon_end_azimuth
        steps = args.horizon_azimuth_steps

        if steps <= 0:
            raise ValueError(f"--horizon-azimuth-steps must be > 0, got {steps}")

        # Compute clockwise sweep in degrees (0..360)
        sweep = ((end_az - start_az) % 360.0)

        # Special case: if sweep is 0, treat as full circle rather than "no work".
        # This covers start=0,end=360 and also start=end.
        if sweep == 0.0:
            sweep = 360.0

        horizon_step = sweep / steps

        local_horizon_basename = f"{args.area_name}_horizon_local"
        logger.info(
            "Calculating local horizon (DSM) with step=%.4f°, "
            "start=%.1f°, end=%.1f°, maxdist=%.0fm...",
            horizon_step,
            args.horizon_start_azimuth,
            args.horizon_end_azimuth,
            args.dsm_buffer_distance,
        )
        # Remove any stale rasters from previous runs before calculating.
        Module(
            "g.remove",
            type="raster",
            pattern=f"{local_horizon_basename}*",
            flags="f",
        ).run()
        calculate_horizon_raster(
            elevation=virtual_raster,
            output_basename=local_horizon_basename,
            step=horizon_step,
            start_azimuth=start_az,
            end_azimuth=end_az,
            max_distance=args.dsm_buffer_distance,
            grass_module=Module,
        )
        normalize_horizon_raster_names(local_horizon_basename, Module)

        sun_horizon_basename = local_horizon_basename
        sun_horizon_step = horizon_step

        if args.input_dem_glob:
            logger.info("Merging DEM rasters from: %s", args.input_dem_glob)
            dem_vrt = merge_rasters(
                dsm_file_glob=args.input_dem_glob,
                area_name=f"{args.area_name}_dem",
                output_dir=output_dir,
            )
            dem_raster = load_virtual_raster_into_grass(
                input_vrt=dem_vrt,
                output_name=f"{args.area_name}_dem",
                grass_module=Module,
            )
            # Restore DSM region after loading DEM
            Module("g.region", raster=virtual_raster).run()

            regional_horizon_basename = f"{args.area_name}_horizon_regional"
            logger.info(
                "Calculating regional horizon (DEM) with step=%.4f°, "
                "start=%.1f°, end=%.1f°, maxdist=%.0fm...",
                horizon_step,
                args.horizon_start_azimuth,
                args.horizon_end_azimuth,
                args.dem_buffer_distance,
            )
            # Remove any stale rasters from previous runs before calculating.
            Module(
                "g.remove",
                type="raster",
                pattern=f"{regional_horizon_basename}*",
                flags="f",
            ).run()
            calculate_horizon_raster(
                elevation=dem_raster,
                output_basename=regional_horizon_basename,
                step=horizon_step,
                start_azimuth=args.horizon_start_azimuth,
                end_azimuth=args.horizon_end_azimuth,
                max_distance=args.dem_buffer_distance,
                grass_module=Module,
            )
            normalize_horizon_raster_names(regional_horizon_basename, Module)

            combined_horizon_basename = f"{args.area_name}_horizon_combined"
            logger.info("Combining local and regional horizons per direction...")
            combine_horizon_rasters_per_direction(
                local_horizon_prefix=local_horizon_basename,
                regional_horizon_prefix=regional_horizon_basename,
                output_prefix=f"{args.area_name}_horizon_combined",
                grass_module=Module,
            )
            sun_horizon_basename = combined_horizon_basename

        logger.info(
            "Horizon pre-calculation complete. Passing basename='%s', step=%.4f to r.sun.",
            sun_horizon_basename,
            sun_horizon_step,
        )

    logger.info("Calculating solar irradiance (interpolated) for days: %s", args.key_days)
    day_irradiance_rasters, solar_irradiance = calculate_solar_irradiance_interpolated(
        dsm=virtual_raster,
        aspect=aspect,
        slope=slope,
        key_days=args.key_days,
        step=args.time_step,
        grass_module=Module,
        export=args.export_rasters,
        output_dir=output_dir,
        horizon_basename=sun_horizon_basename,
        horizon_step=sun_horizon_step,
    )

    logger.info("Loading building outlines...")
    outlines = load_building_outlines(
        args.building_dir, args.building_layer_name, grass_module=Module
    )

    logger.info("Calculating solar irradiance on buildings...")
    solar_on_buildings = calculate_outline_raster(
        solar_irradiance_raster=solar_irradiance,
        building_vector=outlines,
        output_name=args.output_prefix,
        grass_module=Module,
    )

    logger.info("Filtering by slope (max: %s°)...", args.max_slope)
    solar_on_buildings_filtered = filter_raster_by_slope(
        input_raster=solar_on_buildings,
        slope_raster=slope,
        max_slope_degrees=args.max_slope,
        output_name=f"{args.output_prefix}_filtered",
        grass_module=Module,
    )

    # WRF processing (optional)
    day_coefficient_rasters = None
    wrf_adjusted = None

    if args.wrf_file:
        logger.info("Calculating per-day solar coefficients...")
        day_coefficient_rasters = calculate_solar_coefficients(
            day_irradiance_rasters=day_irradiance_rasters,
            dsm=virtual_raster,
            grass_module=Module,
        )

        logger.info("Processing WRF data from: %s", args.wrf_file)
        wrf_day_rasters, wrf_summed = process_wrf_for_grass(
            nc_file_path=args.wrf_file,
            output_prefix="wrf_swdown",
            grass_module=Module,
            source_crs=args.source_crs,
            target_crs=args.target_crs,
            days=args.key_days,
            clip_to_raster=virtual_raster,
            print_diagnostics=False,
        )

        logger.info("Applying per-day solar coefficients to WRF data...")
        adjusted_day_rasters = calculate_wrf_adjusted_per_day(
            wrf_day_rasters=wrf_day_rasters,
            coefficient_rasters=day_coefficient_rasters,
            grass_module=Module,
            output_prefix="wrf_adjusted",
        )

        logger.info("Summing adjusted WRF rasters...")
        adjusted_raster_list = list(adjusted_day_rasters.values())
        wrf_adjusted_total = "wrf_adjusted_total"
        Module(
            "r.series",
            input=",".join(adjusted_raster_list),
            output=wrf_adjusted_total,
            method="sum",
            overwrite=True,
        ).run()

        logger.info("Calculating WRF on buildings...")
        wrf_adjusted = calculate_wrf_on_buildings(
            wrf_summed_raster=wrf_adjusted_total,
            building_vector=outlines,
            output_name="wrf_on_buildings_adjusted",
            grass_module=Module,
        )

        # Clean up intermediate rasters
        cleanup_wrf_intermediates(wrf_day_rasters, wrf_summed, Module)
        Module(
            "g.remove",
            type="raster",
            name=",".join(adjusted_raster_list),
            flags="f",
        ).run()
        Module(
            "g.remove",
            type="raster",
            name=wrf_adjusted_total,
            flags="f",
        ).run()

        if args.export_rasters:
            logger.info("Exporting WRF adjusted raster...")
            Module(
                "r.out.gdal",
                input=wrf_adjusted,
                output=str(output_dir / f"{args.area_name}_wrf_adjusted.tif"),
                format="GTiff",
                createopt="TFW=YES,COMPRESS=LZW",
                overwrite=True,
            ).run()

    logger.info("Cleaning up intermediate rasters...")
    Module(
        "g.remove",
        type="raster",
        name=",".join(day_irradiance_rasters.values()),
        flags="f",
    ).run()

    if day_coefficient_rasters:
        Module(
            "g.remove",
            type="raster",
            name=",".join(day_coefficient_rasters.values()),
            flags="f",
        ).run()

    if args.export_rasters:
        logger.info("Exporting final raster...")
        export_final_raster(
            raster_name=solar_on_buildings_filtered,
            slope=slope,
            aspect=aspect,
            output_tif=f"{args.area_name}_solar_irradiance_on_buildings.tif",
            grass_module=Module,
            output_dir=output_dir,
        )

    logger.info("Generating statistics...")
    create_stats(
        area=args.area_name,
        building_outlines=outlines,
        output_dir=output_dir,
        rooftop_raster=f"{args.output_prefix}_filtered",
        wrf_raster=wrf_adjusted,
        output_csv=True,
        grass_module=Module,
    )

    elapsed_time = time.time() - start_time
    input_dsm_glob_tif_size_MB = calculate_tif_size_MB(args.dsm_glob)
    input_building_dir_size_MB = get_dir_size_MB(args.building_dir)
    logger.info(generate_duration_message(elapsed_time))
    logger.info("INPUT_DSM_GLOB TIF files: %.2f MB total", input_dsm_glob_tif_size_MB)
    logger.info("INPUT_BUILDING_DIR files: %.3f MB total", input_building_dir_size_MB)


if __name__ == "__main__":
    main()
