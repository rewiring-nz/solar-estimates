import os
import pathlib


def generate_duration_message(total_seconds: float) -> str:
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"The pipeline took {round(total_seconds)} seconds ({round(days)} days, {round(hours)} hours, {round(minutes)} minutes, and {round(seconds)} seconds)"


def calculate_tif_size_MB(glob_pattern):
    path_obj = pathlib.Path(glob_pattern)

    # If the user passed a glob with a *
    if "*" in str(glob_pattern):
        # Extract the directory part (e.g., 'data/inputs/DSM/suburb_name/')
        base_dir = path_obj.parent
        pattern = path_obj.name
        files = base_dir.glob(pattern)
    else:
        # plain dir path
        files = path_obj.rglob("*.tif")

    total_bytes = sum(f.stat().st_size for f in files if f.is_file())
    return total_bytes / (1024 * 1024)


def get_dir_size_MB(directory):
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(directory):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip if it is symbolic link
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)

    total_mb = total_size / (1024 * 1024)
    return total_mb
