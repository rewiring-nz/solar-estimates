#!/usr/bin/env bash
# Merge 1m DEM tiles and create a 1km-resolution GeoTIFF
#
# Usage:
#   ./merge_dem_1km.sh -i data/lds-new-zealand-2layers-GPKG-GTiff -o outputs/nz_dem_1km.tif \
#       [-c EPSG:2193] [-r 1000] [-t tmp]
#
# Requirements:
#   - GDAL command line tools: gdalbuildvrt, gdalwarp, gdalinfo
#   - a POSIX shell (bash)
#
# Behavior:
#   1. Finds all .tif/.tiff files under the input directory (recursively)
#   2. Builds a VRT mosaic with gdalbuildvrt
#   3. Optionally reprojects to a target CRS (default EPSG:2193) that has meter units
#   4. Resamples to target resolution (default 1000 m) using area averaging
#   5. Writes a compressed, tiled GeoTIFF output
#
set -euo pipefail

print_usage() {
  cat <<EOF
Usage: $0 -i INPUT_DIR -o OUTPUT_TIF [-c TARGET_CRS] [-r RESOLUTION] [-t TMP_DIR]
  -i INPUT_DIR   Directory containing DEM tiles (recursive search)
  -o OUTPUT_TIF  Output GeoTIFF path
  -c TARGET_CRS  Target CRS for output (default: EPSG:2193). Use 'native' to keep source CRS.
  -r RESOLUTION  Target resolution in map units (default: 1000)
  -t TMP_DIR     Temporary working directory (default: ./tmp_merge_dem)
EOF
}

# Defaults
TARGET_CRS="EPSG:2193"
RESOLUTION=100
TMP_DIR="./tmp_merge_dem"

# Parse args
INPUT_DIR=""
OUTPUT_TIF=""

while getopts "i:o:c:r:t:h" opt; do
  case "${opt}" in
    i) INPUT_DIR="${OPTARG}" ;;
    o) OUTPUT_TIF="${OPTARG}" ;;
    c) TARGET_CRS="${OPTARG}" ;;
    r) RESOLUTION="${OPTARG}" ;;
    t) TMP_DIR="${OPTARG}" ;;
    h|*) print_usage; exit 1 ;;
  esac
done

if [ -z "$INPUT_DIR" ] || [ -z "$OUTPUT_TIF" ]; then
  print_usage
  exit 1
fi

# Prepare workspace
mkdir -p "$TMP_DIR"
tiles_list="$TMP_DIR/tiles.txt"
vrt_file="$TMP_DIR/mosaic.vrt"
intermediate_tif="$TMP_DIR/mosaic_reproj.tif"

# Find tiles (do not print the many filenames to stdout)
# Support .tif and .tiff, case-insensitive
find "$INPUT_DIR" -type f \( -iname '*.tif' -o -iname '*.tiff' \) > "$tiles_list" || true

if [ ! -s "$tiles_list" ]; then
  echo "No .tif/.tiff files found in '$INPUT_DIR'. Exiting." >&2
  exit 2
fi

echo "Found $(wc -l < "$tiles_list") tile(s). Building VRT..."
gdalbuildvrt -input_file_list "$tiles_list" -hidenodata "$vrt_file"

# Detect source CRS from first tile (simple heuristic)
first_tile=$(head -n 1 "$tiles_list")
src_epsg=""
if command -v gdalinfo >/dev/null 2>&1; then
  # Extract EPSG code from gdalinfo output if available
  srs_line=$(gdalinfo "$first_tile" 2>/dev/null | awk '/AUTHORITY\["EPSG"/ {print; exit}')
  if [ -n "$srs_line" ]; then
    # srs_line looks like: AUTHORITY["EPSG","2193"]
    src_epsg=$(echo "$srs_line" | sed -E 's/.*"([0-9]+)".*/EPSG:\1/')
  fi
fi

echo "Source EPSG (heuristic): ${src_epsg:-unknown}"

# Decide whether to reproject first or not:
# If TARGET_CRS is 'native', skip reprojection and resample in source CRS (dangerous if geographic).
if [ "$TARGET_CRS" = "native" ]; then
  echo "Keeping source CRS (native). Resampling will use source CRS units."
  # Use the VRT directly as input to gdalwarp for resampling.
  warp_input="$vrt_file"
else
  # If source EPSG is equal to TARGET_CRS we can skip an explicit reprojection step
  if [ -n "$src_epsg" ] && [ "$src_epsg" = "$TARGET_CRS" ]; then
    echo "Source CRS matches target CRS ($TARGET_CRS). Skipping reprojection."
    warp_input="$vrt_file"
  else
    echo "Reprojecting to $TARGET_CRS before resampling..."
    # Reproject the VRT to a temporary TIFF (so we can safely set -tr in target CRS)
    # Use average resampling when downsampling will be done later; here we keep high-res data so use bilinear by default.
    gdalwarp -t_srs "$TARGET_CRS" -r bilinear -of GTiff -co "TILED=YES" -co "COMPRESS=LZW" "$vrt_file" "$intermediate_tif"
    warp_input="$intermediate_tif"
  fi
fi

# Now resample to target resolution (RESOLUTION in target CRS units).
# Use area averaging for downsampling; nearest or bilinear would be less appropriate for DEM aggregation.
echo "Resampling to ${RESOLUTION} x ${RESOLUTION} (map units) using average..."
mkdir -p "$(dirname "$OUTPUT_TIF")"
gdalwarp \
  -of GTiff \
  -r average \
  -tr "$RESOLUTION" "$RESOLUTION" \
  -co "TILED=YES" \
  -co "COMPRESS=LZW" \
  -co "BIGTIFF=IF_SAFER" \
  "$warp_input" "$OUTPUT_TIF"

echo "Output written to $OUTPUT_TIF"

# Print info about output
if command -v gdalinfo >/dev/null 2>&1; then
  echo "Output overview:"
  gdalinfo "$OUTPUT_TIF" | sed -n '1,120p'
fi

echo "Done. Temporary files are in $TMP_DIR (delete when not needed)."
