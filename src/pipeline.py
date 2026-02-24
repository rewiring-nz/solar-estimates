#!/usr/bin/env python3
"""
CLI tool for estimating solar irradiance on buildings from digital surface models.
"""

import argparse
import platform
import sys
from pathlib import Path

from utils.building_outlines import (
    calculate_outline_raster,
    export_final_raster,
    load_building_outlines,
    remove_masks,
)
from utils.dsm import (
    calculate_slope_aspect_rasters,
    filter_raster_by_slope,
    load_virtual_raster_into_grass,
    merge_rasters,
)
from utils.grass_utils import setup_grass
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

    return parser.parse_args()


def main():
    args = parse_args()

    # Validate inputs
    if not Path(args.building_dir).exists():
        if not Path(f"{args.building_dir}.zip").exists():
            print(
                f"Error: Building directory does not exist: {args.building_dir}",
                file=sys.stderr,
            )
            sys.exit(1)

    # Auto-detect or validate GRASS base path
    grass_base = args.grass_base
    if grass_base is None:
        grass_base = detect_grass_base()
        if grass_base is None:
            print(
                f"Error: Could not auto-detect GRASS GIS installation for {platform.system()}. "
                "Please provide --grass-base argument.",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"Auto-detected GRASS GIS at: {grass_base}")

    # Set up GRASS environment
    print(f"Setting up GRASS GIS from: {grass_base}")
    gscript, Module = setup_grass(gisbase=grass_base)

    # Main workflow
    print("Removing existing masks...")
    remove_masks(grass_module=Module)

    print(f"Merging rasters from: {args.dsm_glob}")
    merged_virtual_raster = merge_rasters(
        dsm_file_glob=args.dsm_glob, area_name=args.area_name
    )

    print("Loading virtual raster into GRASS...")
    virtual_raster = load_virtual_raster_into_grass(
        input_vrt=merged_virtual_raster,
        output_name=f"{args.area_name}_dsm",
        grass_module=Module,
    )

    print("Calculating slope and aspect...")
    aspect, slope = calculate_slope_aspect_rasters(
        dsm=virtual_raster, grass_module=Module
    )

    print(f"Calculating solar irradiance (interpolated) for days: {args.key_days}")
    day_irradiance_rasters, solar_irradiance = calculate_solar_irradiance_interpolated(
        dsm=virtual_raster,
        aspect=aspect,
        slope=slope,
        key_days=args.key_days,
        step=args.time_step,
        grass_module=Module,
        export=args.export_rasters,
    )

    print("Loading building outlines...")
    outlines = load_building_outlines(
        args.building_dir, args.building_layer_name, grass_module=Module
    )

    print("Calculating solar irradiance on buildings...")
    solar_on_buildings = calculate_outline_raster(
        solar_irradiance_raster=solar_irradiance,
        building_vector=outlines,
        output_name=args.output_prefix,
        grass_module=Module,
    )

    print(f"Filtering by slope (max: {args.max_slope}°)...")
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
        print("Calculating per-day solar coefficients...")
        day_coefficient_rasters = calculate_solar_coefficients(
            day_irradiance_rasters=day_irradiance_rasters,
            dsm=virtual_raster,
            grass_module=Module,
        )

        print(f"Processing WRF data from: {args.wrf_file}")
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

        # Apply per-day coefficients to WRF rasters
        print("Applying per-day solar coefficients to WRF data...")
        adjusted_day_rasters = calculate_wrf_adjusted_per_day(
            wrf_day_rasters=wrf_day_rasters,
            coefficient_rasters=day_coefficient_rasters,
            grass_module=Module,
            output_prefix="wrf_adjusted",
        )

        # Sum the per-day adjusted rasters
        print("Summing adjusted WRF rasters...")
        adjusted_raster_list = list(adjusted_day_rasters.values())
        wrf_adjusted_total = "wrf_adjusted_total"
        Module(
            "r.series",
            input=",".join(adjusted_raster_list),
            output=wrf_adjusted_total,
            method="sum",
            overwrite=True,
        ).run()

        # Apply building mask to get WRF on buildings
        print("Calculating WRF on buildings...")
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

        # Export the adjusted WRF raster if requested
        if args.export_rasters:
            print("Exporting WRF adjusted raster...")
            Module(
                "r.out.gdal",
                input=wrf_adjusted,
                output=f"{args.area_name}_wrf_adjusted.tif",
                format="GTiff",
                createopt="TFW=YES,COMPRESS=LZW",
                overwrite=True,
            ).run()

    # Clean up per-day irradiance and coefficient rasters
    print("Cleaning up intermediate rasters...")
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
        print("Exporting final raster...")
        export_final_raster(
            raster_name=solar_on_buildings_filtered,
            slope=slope,
            aspect=aspect,
            output_tif=f"{args.area_name}_solar_irradiance_on_buildings.tif",
            grass_module=Module,
        )

    print("\n👉 Generating statistics...")
    create_stats(
        area=args.area_name,
        building_outlines=outlines,
        output_dir=output_dir,
        rooftop_raster=f"{args.output_prefix}_filtered",
        wrf_raster=wrf_adjusted,
        output_csv=True,
        grass_module=Module,
    )

    print("Processing complete!")


if __name__ == "__main__":
    main()
