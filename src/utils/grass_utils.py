"""GRASS GIS environment setup helper.

This module provides a single convenience function, `setup_grass`, which
enables the programmatic usage of GRASS GIS.
"""

import os
import subprocess
import sys
from typing import Tuple

def setup_grass(
    gisbase: str,
    grassdata_dir: str = "grassdata",
    location: str = "solar_estimates",
    mapset: str = "PERMANENT",
) -> Tuple[object, type]:
    """Prepare the GRASS Python bindings and initialize a session.

    This function:
      - uses GISBASE to locate the GRASS installation
      - appends relevant GRASS directories to PATH,
      - ensures `grassdata_dir` exists and creates it if missing
      - calls `gscript.setup.init(grassdata_dir, location, mapset)`

    Args:
        gisbase: Filesystem path to the GRASS installation root (contains `bin/`, `scripts/`,
            and `etc/` directories).
        grassdata_dir: Directory to host GRASS locations (created if missing).
        location: Name of the location under `grassdata_dir` to use or create.
        mapset: GRASS mapset to initialize inside the Location.

    Returns:
        A tuple `(gscript, Module)` where `gscript` is the imported `grass.script`
        module and `Module` is the class from `grass.pygrass.modules`. These are
        used for running GRASS's modules.

    Raises:
        ImportError: If GRASS Python modules cannot be imported after modifying `sys.path`.
        subprocess.CalledProcessError: If the attempt to create a new GRASS Location fails.
    """
    # Set the GISBASE environment variable and locate GRASS dirs
    os.environ["GISBASE"] = gisbase
    grass_bin = os.path.join(os.environ["GISBASE"], "bin")
    grass_scripts = os.path.join(os.environ["GISBASE"], "scripts")
    grass_python = os.path.join(os.environ["GISBASE"], "etc", "python")

    # Ensure GRASS executables and scripts can be found by subprocesses
    os.environ["PATH"] += os.pathsep + grass_bin + os.pathsep + grass_scripts

    # Ensure Python can import GRASS packages
    sys.path.insert(0, grass_python)

    # Import GRASS scripting interfaces
    try:
        import grass.script as gscript  # type: ignore
        from grass.pygrass.modules import Module  # type: ignore
    except ImportError as e:
        # Provide diagnostic context before re-raising
        print("Error importing GRASS Python modules. Check if dependencies are installed correctly.")
        print(f"GISBASE used: {gisbase}")
        raise

    # Ensure the grassdata directory exists
    os.makedirs(grassdata_dir, exist_ok=True)

    # Create the requested Location if it does not exist.
    # TODO: take EPSG as argument?
    location_path = os.path.join(grassdata_dir, location)
    if not os.path.exists(location_path):
        cmd = ["grass", "--text", "-c", "EPSG:2193", location_path]
        print(f"DEBUG: Attempting to create GRASS Location: {' '.join(cmd)}")

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Provide an "exit" in case interactive prompts appear
        out, err = proc.communicate("exit\n")

        if proc.returncode != 0:
            # Print diagnostics and raise an error that includes output
            print("\n!!! GRASS LOCATION CREATION FAILED !!!")
            print(f"Command: {' '.join(cmd)}")
            print(f"Return Code: {proc.returncode}")
            print("\n--- GRASS STDOUT ---")
            print(out)
            print("\n--- GRASS STDERR ---")
            print(err)
            print("--------------------------------------\n")

            raise subprocess.CalledProcessError(
                proc.returncode,
                cmd,
                output=out,
                stderr=err,
            )

    # Initialize a GRASS session in this process
    gscript.setup.init(grassdata_dir, location, mapset)

    # Return the scripting interface and Module class for running GRASS modules
    return gscript, Module
