#!/usr/bin/env python3
"""
CLI tool for estimating solar irradiance on buildings from digital surface models.
"""

import argparse
import os
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
from utils.download_dsm_from_s3 import download_items, parse_bool, parse_env_file, select_items
from utils.dsm import (
    calculate_horizon_raster,
    calculate_slope_aspect_rasters,
    combine_horizon_rasters,
    filter_raster_by_slope,
    load_virtual_raster_into_grass,
    merge_rasters,
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


def parse_key_days(value: str | None, default: list[int]) -> list[int]:
    if not value:
        return default
    parts = value.replace(",", " ").split()
    if not parts:
        return default
    return [int(part) for part in parts]


def load_config(config_path: str) -> dict[str, str]:
    path = Path(config_path)
    if not path.exists():
        raise SystemExit(f"Config file does not exist: {path}")
    return parse_env_file(path)


def get_config_value(
    config: dict[str, str],
    key: str,
    default: str | None = None,
    *,
    required: bool = False,
) -> str | None:
    value = config.get(key)
    if value is not None and value.strip():
        return value

    if required:
        raise SystemExit(f"Missing required config key: {key}")

    return default


def get_config_float(config: dict[str, str], key: str, default: float) -> float:
    value = get_config_value(config, key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid float for {key}: {value}") from exc


def get_config_int(config: dict[str, str], key: str, default: int) -> int:
    value = get_config_value(config, key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid integer for {key}: {value}") from exc


def get_config_key_days(config: dict[str, str], default: list[int]) -> list[int]:
    value = get_config_value(config, "KEY_DAYS")
    return parse_key_days(value, default)


def parse_args():
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument(
        "--defaults-config",
        default=os.environ.get("DEFAULT_CONFIG_FILE", "configs/default.env"),
        help="Base defaults config file (KEY=VALUE). Precedence: CLI > --config > --defaults-config",
    )
    config_parser.add_argument(
        "--config",
        default=os.environ.get("CONFIG_FILE", "configs/suburb_ShotoverCountry.env"),
        help="Scenario config file (KEY=VALUE) that overrides --defaults-config",
    )
    config_args, remaining_argv = config_parser.parse_known_args()
    defaults_config = load_config(config_args.defaults_config)
    scenario_config = load_config(config_args.config)
    config = {**defaults_config, **scenario_config}

    parser = argparse.ArgumentParser(
        description="Estimate solar irradiance on buildings from DSM data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[config_parser],
        epilog=(
            "Configuration precedence:\n"
            "  1) CLI flags\n"
            "  2) --config scenario file\n"
            "  3) --defaults-config base defaults file"
        ),
    )

    parser.add_argument(
        "--dsm-glob",
        default=get_config_value(config, "INPUT_DSM_GLOB", required=True),
        help="Glob for DSM GeoTIFF files to use as inputs (required after config merge)",
    )

    parser.add_argument(
        "--building-dir",
        default=get_config_value(config, "INPUT_BUILDING_DIR", required=True),
        help="Building outlines path (required after config merge)",
    )

    parser.add_argument(
        "--area-name",
        default=get_config_value(config, "OUTPUT_AREA_NAME", required=True),
        help="Descriptive name used in output filenames (required after config merge)",
    )

    parser.add_argument(
        "--building-layer-name",
        default=get_config_value(config, "OUTPUT_BUILDING_LAYER_NAME", required=True),
        help="Name of the output building outline layer (required after config merge)",
    )

    parser.add_argument(
        "--grass-base",
        default=config.get("GRASS_BASE"),
        help="Path to GRASS GIS installation base directory (auto-detected if not provided)",
    )

    parser.add_argument(
        "--output-prefix",
        default=get_config_value(config, "OUTPUT_PREFIX", "solar_on_buildings"),
        help="Prefix for output files (default: from merged config)",
    )

    parser.add_argument(
        "--max-slope",
        type=float,
        default=get_config_float(config, "MAX_SLOPE", 45.0),
        help="Maximum slope in degrees for filtering (default: from merged config)",
    )

    parser.add_argument(
        "--key-days",
        type=int,
        nargs="+",
        default=get_config_key_days(config, [15, 105, 196]),
        help="Day numbers for solar irradiance calculation (default: from merged config)",
    )

    parser.add_argument(
        "--time-step",
        type=float,
        default=get_config_float(config, "TIME_STEP", 1.0),
        help="Time step for all-day radiation sums in decimal hours (default: from merged config)",
    )

    parser.add_argument(
        "--region-bbox",
        default=config.get("REGION_BBOX"),
        help="Optional GRASS region bbox as north,south,east,west in project CRS to constrain processing",
    )

    parser.add_argument(
        "--n-procs",
        type=int,
        default=get_config_int(config, "N_PROCS", 1),
        help="Number of parallel processes for r.sun irradiance calculation (default: from merged config)",
    )

    parser.add_argument(
        "--export-rasters",
        action="store_true",
        default=parse_bool(config.get("EXPORT_RASTERS"), default=False),
        help="Export rasters (solar irradiance, coefficient, WRF adjusted, final) as GeoTIFFs",
    )

    # Horizon pre-calculation arguments
    parser.add_argument(
        "--calculate-horizon",
        action="store_true",
        default=parse_bool(config.get("CALCULATE_HORIZON"), default=False),
        help="Enable horizon pre-calculation using r.horizon (improves r.sun speed by 10-30%%)",
    )

    parser.add_argument(
        "--dem-glob",
        default=config.get("INPUT_DEM_GLOB"),
        help="Glob pattern for optional 8m DEM tiles used for regional horizon calculation",
    )

    parser.add_argument(
        "--dsm-buffer-distance",
        type=float,
        default=get_config_float(config, "DSM_BUFFER_DISTANCE", 30.0),
        help="Local horizon search radius in metres for 1m DSM (default: from merged config)",
    )

    parser.add_argument(
        "--dem-buffer-distance",
        type=float,
        default=get_config_float(config, "DEM_BUFFER_DISTANCE", 10000.0),
        help="Regional horizon search radius in metres for 8m DEM (default: from merged config)",
    )

    parser.add_argument(
        "--horizon-step-degrees",
        type=float,
        default=get_config_float(config, "HORIZON_STEP_DEGREES", 30.0),
        help="Azimuth increment in degrees for horizon calculation (default: from merged config)",
    )

    parser.add_argument(
        "--horizon-start-azimuth",
        type=float,
        default=get_config_float(config, "HORIZON_START_AZIMUTH", 315.0),
        help="Start azimuth in degrees for horizon calculation (default: from merged config)",
    )

    parser.add_argument(
        "--horizon-end-azimuth",
        type=float,
        default=get_config_float(config, "HORIZON_END_AZIMUTH", 135.0),
        help="End azimuth in degrees for horizon calculation (default: from merged config)",
    )

    # WRF-related arguments
    parser.add_argument(
        "--wrf-file",
        default=config.get("WRF_FILE"),
        help="Path to WRF NetCDF file for measured radiation data (optional)",
    )

    parser.add_argument(
        "--source-crs",
        default=get_config_value(config, "SOURCE_CRS", "EPSG:4326"),
        help="Source CRS for WRF data (default: from merged config)",
    )

    parser.add_argument(
        "--target-crs",
        default=get_config_value(config, "TARGET_CRS", "EPSG:2193"),
        help="Target CRS for WRF reprojection (default: from merged config)",
    )

    parser.add_argument(
        "--download-dsm",
        action="store_true",
        default=parse_bool(config.get("DOWNLOAD_DSM"), default=False),
        help="Optionally run S3 DSM downloader before pipeline steps using the selected config file",
    )

    args = parser.parse_args(remaining_argv)
    args.defaults_config = config_args.defaults_config
    args.config = config_args.config
    return args, config


def parse_region_bbox(region_bbox: str | None) -> tuple[float, float, float, float] | None:
    if not region_bbox:
        return None

    parts = [part.strip() for part in region_bbox.split(",")]
    if len(parts) != 4:
        raise ValueError("--region-bbox must contain four comma-separated values: north,south,east,west")

    north, south, east, west = (float(part) for part in parts)
    return north, south, east, west


def run_optional_dsm_download(logger, config: dict[str, str]) -> None:
    """Run DSM downloader before main pipeline processing using the selected config file."""
    logger.info("Running DSM downloader using config file values")
    selected_items = select_items(config)
    if not selected_items:
        logger.warning("DSM downloader selected 0 items")
        return

    download_items(selected_items, config)
    logger.info("DSM downloader completed")


def log_runtime_configuration(logger, args) -> None:
    defaults_config_path = Path(args.defaults_config).resolve()
    config_path = Path(args.config).resolve()
    resolved_values = {
        "defaults_config": str(defaults_config_path),
        "config": str(config_path),
        "dsm_glob": args.dsm_glob,
        "building_dir": args.building_dir,
        "area_name": args.area_name,
        "building_layer_name": args.building_layer_name,
        "grass_base": args.grass_base,
        "output_prefix": args.output_prefix,
        "max_slope": args.max_slope,
        "key_days": args.key_days,
        "time_step": args.time_step,
        "region_bbox": args.region_bbox,
        "n_procs": args.n_procs,
        "export_rasters": args.export_rasters,
        "calculate_horizon": args.calculate_horizon,
        "dem_glob": args.dem_glob,
        "dsm_buffer_distance": args.dsm_buffer_distance,
        "dem_buffer_distance": args.dem_buffer_distance,
        "horizon_step_degrees": args.horizon_step_degrees,
        "horizon_start_azimuth": args.horizon_start_azimuth,
        "horizon_end_azimuth": args.horizon_end_azimuth,
        "wrf_file": args.wrf_file,
        "source_crs": args.source_crs,
        "target_crs": args.target_crs,
        "download_dsm": args.download_dsm,
    }

    logger.info("Runtime defaults config source: %s", resolved_values["defaults_config"])
    logger.info("Runtime scenario config source: %s", resolved_values["config"])
    logger.info("Resolved runtime parameters:")
    for key, value in resolved_values.items():
        if key in {"defaults_config", "config"}:
            continue
        logger.info("  %s=%s", key, value)


def main():
    logger = setup_logging()
    start_time = time.time()
    logger.info("Starting pipeline")

    args, config = parse_args()
    log_runtime_configuration(logger, args)

    if args.download_dsm:
        try:
            run_optional_dsm_download(logger, config)
        except Exception as exc:
            logger.error("DSM downloader failed: %s", exc)
            sys.exit(1)

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
    region_bbox = parse_region_bbox(args.region_bbox)
    virtual_raster = load_virtual_raster_into_grass(
        input_vrt=merged_virtual_raster,
        output_name=f"{args.area_name}_dsm",
        grass_module=Module,
        region_bbox=region_bbox,
    )

    logger.info("Calculating slope and aspect...")
    aspect, slope = calculate_slope_aspect_rasters(dsm=virtual_raster, grass_module=Module)

    # Horizon pre-calculation (optional, opt-in via --calculate-horizon)
    horizon = None
    if args.calculate_horizon:
        logger.info(
            "Calculating local horizon from 1m DSM (buffer: %sm)...",
            args.dsm_buffer_distance,
        )
        local_horizon = calculate_horizon_raster(
            elevation=virtual_raster,
            output_name=f"{args.area_name}_horizon_local",
            grass_module=Module,
            buffer_distance=args.dsm_buffer_distance,
            start_azimuth=args.horizon_start_azimuth,
            end_azimuth=args.horizon_end_azimuth,
            step_degrees=args.horizon_step_degrees,
        )
        horizon = local_horizon

        if args.dem_glob:
            logger.info("Merging DEM rasters from: %s", args.dem_glob)
            merged_dem_vrt = merge_rasters(
                dsm_file_glob=args.dem_glob,
                area_name=f"{args.area_name}_dem",
                output_dir=output_dir,
            )

            logger.info("Loading DEM virtual raster into GRASS...")
            dem_raster = load_virtual_raster_into_grass(
                input_vrt=merged_dem_vrt,
                output_name=f"{args.area_name}_dem",
                grass_module=Module,
            )

            logger.info(
                "Calculating regional horizon from 8m DEM (buffer: %sm)...",
                args.dem_buffer_distance,
            )
            regional_horizon = calculate_horizon_raster(
                elevation=dem_raster,
                output_name=f"{args.area_name}_horizon_regional",
                grass_module=Module,
                buffer_distance=args.dem_buffer_distance,
                start_azimuth=args.horizon_start_azimuth,
                end_azimuth=args.horizon_end_azimuth,
                step_degrees=args.horizon_step_degrees,
            )

            logger.info("Combining local and regional horizons...")
            horizon = combine_horizon_rasters(
                local_horizon=local_horizon,
                regional_horizon=regional_horizon,
                output_name=f"{args.area_name}_horizon",
                grass_module=Module,
            )

        if args.export_rasters:
            # `horizon` is a basename prefix for r.sun (a set of rasters like
            # <basename>_000_0, <basename>_010_0, ...), not a single raster map.
            logger.info("Exporting horizon rasters (per-azimuth)...")

            from subprocess import PIPE

            # List the per-azimuth rasters for the basename
            g_list = Module(
                "g.list",
                type="raster",
                pattern=f"{horizon}_*_*",
                stdout_=PIPE,
            )
            g_list.run()
            horizon_maps = [m.strip() for m in (g_list.outputs.stdout or "").splitlines() if m.strip()]

            if not horizon_maps:
                logger.warning(
                    "Export requested, but no horizon rasters found matching pattern: %s",
                    f"{horizon}_*_*",
                )
            else:
                for horizon_map in sorted(horizon_maps):
                    out_name = f"{horizon_map}.tif"
                    logger.info("Exporting %s -> %s", horizon_map, out_name)
                    Module(
                        "r.out.gdal",
                        input=horizon_map,
                        output=str(output_dir / out_name),
                        format="GTiff",
                        createopt="TFW=YES,COMPRESS=LZW",
                        overwrite=True,
                    ).run()

    logger.info("Calculating solar irradiance (interpolated) for days: %s", args.key_days)
    day_irradiance_rasters, solar_irradiance = calculate_solar_irradiance_interpolated(
        dsm=virtual_raster,
        aspect=aspect,
        slope=slope,
        key_days=args.key_days,
        step=args.time_step,
        grass_module=Module,
        n_procs=args.n_procs,
        export=args.export_rasters,
        output_dir=output_dir,
        horizon=horizon,
        horizon_step_degrees=args.horizon_step_degrees,
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
            day_irradiance_rasters=rooftop_day_irradiance_rasters,
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