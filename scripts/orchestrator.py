import subprocess
import os
import glob
import logging
import argparse

"""
Solar estimates pipeline orchestra

This script orchestrates the running of multiple docker-compose invocations, so that we can
run the pipeline for multiple env_files/tiles with one command sequentially.
"""

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# def download_linz_tile(tile_id):
#     """Placeholder for future API integration."""
#     logging.info(f"Downloading data for tile: {tile_id}...")
#     # TODO: Hit LINZ API, download DSM to data/inputs/DSM/
#     # TODO: Download building outlines to data/inputs/building_outlines/
#     pass

# def generate_env_file(tile_id):
#     """Dynamically generate a .env file for the specific tile."""
#     env_path = f"configs/temp_{tile_id}.env"
#     with open(env_path, 'w') as f:
#         f.write(f"INPUT_DSM_GLOB=data/inputs/DSM/tile_{tile_id}/*.tif\n")
#         f.write(f"INPUT_BUILDING_DIR=data/inputs/building_outlines/tile_{tile_id}\n")
#         f.write(f"OUTPUT_env_file_NAME=tile_{tile_id}\n")
#         f.write(f"OUTPUT_BUILDING_LAYER_NAME=buildings_{tile_id}\n")
#         # Add other standard variables here...
#     return env_path

# def cleanup_tile_data(tile_id, env_path):
#     """Delete the downloaded input data to save disk space over long runs."""
#     logging.info(f"Cleaning up input data and temp configs for {tile_id}...")
#     # TODO: os.remove() or shutil.rmtree() on the specific tile directories
#     if os.path.exists(env_path):
#         os.remove(env_path)


def parse_args():
    """Set up command line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Orchestrator for batch processing solar estimates."
    )

    # Changed from --tiles to --batch-file
    parser.add_argument(
        "--batch-file",
        required=True,
        help="Path to a text file containing a list of env files to process (one per line).",
    )

    return parser.parse_args()


def run_pipeline(env_path):
    logging.info(f"Triggering Docker Compose for {env_path}...")
    result = subprocess.run(
        ["docker", "compose", "--env-file", env_path, "up", "pipeline"],
        capture_output=False,  # Set to True if you want to suppress console output and log to file
    )

    if result.returncode != 0:
        logging.error(f"Pipeline failed for {env_path}")
        return False
    return True


def main():
    args = parse_args()

    # Read the batch file
    target_env_files = []
    try:
        with open(args.batch_file, "r") as f:
            for line in f:
                stripped_line = line.strip()
                # Ignore empty lines and lines starting with '#'
                if stripped_line and not stripped_line.startswith("#"):
                    target_env_files.append(stripped_line)
    except FileNotFoundError:
        logging.error(f"Could not find batch file: {args.batch_file}")
        return

    n_env_files = len(target_env_files)
    logging.info(f"Loaded {n_env_files} env_files to run from {args.batch_file}")

    for i, env_file in enumerate(target_env_files):
        logging.info(
            f"\n\n\n--- Starting workflow for {env_file} ({i+1} of {n_env_files}) ---\n"
        )

        try:
            if not os.path.exists(env_file):
                logging.warning(
                    f"Config file {env_file} not found. Skipping {env_file}."
                )
                continue
            success = run_pipeline(env_file)
            logging.info(
                f"\n\n\n--- Workflow for {env_file} complete ({i+1} of {n_env_files} done) ---\n"
            )

        except Exception as e:
            logging.error(f"Critical error processing {env_file}: {e}")
            continue


if __name__ == "__main__":
    main()
