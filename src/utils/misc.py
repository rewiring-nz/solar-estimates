import glob
import os
import pathlib


def generate_duration_message(total_seconds: float) -> str:
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"The pipeline took {round(total_seconds)} seconds ({round(days)} days, {round(hours)} hours, {round(minutes)} minutes, and {round(seconds)} seconds)"


def calculate_tif_size_MB(glob_pattern):
    path_obj = pathlib.Path(glob_pattern)

    # Use glob.has_magic so bracket/range patterns (e.g. 0[12]) are also detected.
    if glob.has_magic(str(glob_pattern)):
        file_paths = [pathlib.Path(p) for p in glob.glob(str(glob_pattern), recursive=True)]
    elif path_obj.is_dir():
        file_paths = list(path_obj.rglob("*.tif"))
    elif path_obj.is_file() and path_obj.suffix.lower() == ".tif":
        file_paths = [path_obj]
    else:
        file_paths = []

    total_bytes = sum(f.stat().st_size for f in file_paths if f.is_file())
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
