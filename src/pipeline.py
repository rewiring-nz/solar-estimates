#!/usr/bin/env python3
"""
CLI tool for estimating solar irradiance on buildings from digital surface models.
"""

import argparse
import sys
from pathlib import Path

from lib.building_outlines import (
    calculate_outline_raster,
    export_final_raster,
    load_building_outlines,
    remove_masks,
)
from lib.dsm import (
    calculate_slope_aspect_rasters,
    filter_raster_by_slope,
    load_virtual_raster_into_grass,
    merge_rasters,
)
from lib.grass_utils import setup_grass
from lib.solar_irradiance import calculate_solar_irradiance_interpolated
from lib.stats import create_stats


def parse_args():
    parser = argparse.ArgumentParser(
        description="Estimate solar irradiance on buildings from DSM data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  %(prog)s \\
    --dsm-glob "data/shotover_country/*.tif" \\
    --building-dir "data/queenstown-lakes-building-outlines" \\
    --area-name "shotover_country" \\
    --building-outline-name "queenstown_lakes_buildings" \\
    --grass-base "/Applications/GRASS-8.4.app/Contents/Resources"
        """,
    )

    parser.add_argument(
        "--dsm-glob",
        required=True,
        help='Glob for DSM GeoTIFF files (example: "data/shotover_country/*.tif")',
    )

    parser.add_argument(
        "--building-dir",
        required=True,
        help='Directory containing building outline shapefiles (example: "data/queenstown_lakes_building_outlines")',
    )

    parser.add_argument(
        "--area-name",
        required=True,
        help='Descriptive name for the area (example: "shotover_country")',
    )

    parser.add_argument(
        "--building-layer-name",
        required=True,
        help='Name of the building outline layer (example: "queenstown_lakes_buildings_outlines")',
    )

    parser.add_argument(
        "--grass-base",
        required=True,
        help='Path to GRASS GIS installation base directory (example: "/Applications/GRASS-8.4.app/Contents/Resources")',
    )

    parser.add_argument(
        "--output-prefix",
        default="solar_on_buildings",
        help='Prefix for output files (example: "solar_on_buildings")',
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
        default=[1, 79, 172, 266, 357, 365],
        help="Day numbers for solar irradiance interpolation (default: solstices and equinoxes)",
    )

    parser.add_argument(
        "--time-step",
        type=float,
        default=1.0,
        help="Time step when computing all-day radiation sums in decimal hours. Default: 1.0",
    )

    parser.add_argument(
        "--export-raster",
        action="store_true",
        help="Export final solar irradiance raster as GeoTIFF",
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

    # Set up GRASS environment
    print(f"Setting up GRASS GIS from: {args.grass_base}")
    gscript, Module = setup_grass(gisbase=args.grass_base)

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

    print(f"Calculating solar irradiance for days: {args.key_days}")
    solar_irradiance = calculate_solar_irradiance_interpolated(
        dsm=virtual_raster,
        aspect=aspect,
        slope=slope,
        key_days=args.key_days,
        step=args.time_step,
        grass_module=Module,
        export=False,
        cleanup=True,
    )

    print("Loading building outlines...")
    outlines = load_building_outlines(
        args.building_dir, args.building_layer, grass_module=Module
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

    if args.export_raster:
        print("Exporting final raster...")
        final_raster = export_final_raster(
            raster_name=solar_on_buildings_filtered,
            slope=slope,
            aspect=aspect,
            output_tif=f"{args.area_name}_solar_irradiance_on_buildings.tif",
            grass_module=Module,
        )

    print("Generating statistics...")
    create_stats(
        area=args.area_name,
        building_outlines=outlines,
        rooftop_raster=f"{args.output_prefix}_filtered",
        output_csv=True,
        grass_module=Module,
    )

    print("Processing complete!")


if __name__ == "__main__":
    main()
