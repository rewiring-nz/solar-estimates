#!/usr/bin/env bash
# Mount current repo into /work in the container and run the merge script
docker run --rm -it \
  -v "$(pwd)":/work -w /work \
  ghcr.io/osgeo/gdal:ubuntu-small-latest \
  bash -lc "./scripts/merge_dem.sh -r 10 -i src/data/lds-new-zealand-2layers-GPKG-GTiff/nelson-lidar-1m-dem-2025 -o outputs/nelson_dem_10m.tif"
