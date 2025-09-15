import os
import sys

def setup_grass(gisbase: str,
                grassdata_dir: str = 'grassdata',
                location: str = 'solar_estimates',
                mapset: str = 'PERMANENT'):
    """Sets up a GRASS environment and returns a Module class object that can be used to call GRASS modules."""

    # Set up GRASS environment and PATH
    os.environ['GISBASE'] = gisbase
    grass_bin = os.path.join(os.environ['GISBASE'], 'bin')
    grass_scripts = os.path.join(os.environ['GISBASE'], 'scripts')
    grass_python = os.path.join(os.environ['GISBASE'], 'etc', 'python')

    os.environ['PATH'] += os.pathsep + grass_bin + os.pathsep + grass_scripts
    sys.path.insert(0, grass_python)

    # Import GRASS modules for Python scripting
    import grass.script as gscript
    from grass.pygrass.modules import Module

    os.makedirs(grassdata_dir, exist_ok=True)

    # Create location if it doesn't exist
    location_path = os.path.join(grassdata_dir, location)
    if not os.path.exists(location_path):
        import subprocess
        cmd = [
            os.path.join(os.environ['GISBASE'], 'grass84.bat'),
            '-c', 'EPSG:2193',
            location_path
        ]
        # GRASS upon executing takes over the shell, so ensure it doesn't
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate('exit\n')
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, cmd, output=out, stderr=err)

    # Initialize GRASS session
    gscript.setup.init(grassdata_dir, location, mapset)
    
    return gscript, Module
