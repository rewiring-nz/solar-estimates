#!/usr/bin/env bash
#
# Convert LERC-compressed GeoTIFF tile(s) to LZW-compressed GeoTIFFs for local QGIS viewing.
#
# Usage:
#   ./convert-to-lzw.sh [options] input-dir-or-file [output-dir-or-file]
#
# Examples:
#   ./convert-to-lzw.sh data-s3
#   ./convert-to-lzw.sh data-s3 data-s3-lzw
#   ./convert-to-lzw.sh data-s3/CC11_10000_0102.tif
#   ./convert-to-lzw.sh data-s3/CC11_10000_0102.tif data-s3/CC11_10000_0102-lzw.tif
#   ./convert-to-lzw.sh --overwrite data-s3
#
# Notes:
# - Source files must be GeoTIFFs with LERC compression (validated via gdalinfo).
# - Output defaults to <input-dir>-lzw or <input-file-stem>-lzw.tif.
# - Existing outputs are skipped unless --overwrite is set.

set -Eeuo pipefail
IFS=$'\n\t'

script_name="$(basename "$0")"

die() {
  echo "Error: $*" >&2
  exit 1
}

warn() {
  echo "Warning: $*" >&2
}

usage() {
  cat <<EOF
Usage:
  $script_name [options] <input-dir-or-file> [output-dir-or-file]

Options:
  -h, --help            Show this help message and exit
  --overwrite           Overwrite existing output files
  --strict              Fail if any source is not LERC (default: true)
  --no-strict           Skip non-LERC files with a warning instead of failing

Behavior:
  - Accepts either:
    1) a directory containing .tif/.tiff files, or
    2) a single .tif/.tiff file
  - Optional output path:
    1) directory path for directory input
    2) file path for single-file input
  - Converts using:
    COMPRESS=LZW, TILED=YES, BLOCKXSIZE=512, BLOCKYSIZE=512, BIGTIFF=IF_SAFER
  - Validates each source file is LERC-compressed before conversion.
EOF
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

is_tiff_path() {
  local p="$1"
  [[ "$p" == *.tif || "$p" == *.tiff || "$p" == *.TIF || "$p" == *.TIFF ]]
}

is_lerc_compressed() {
  local f="$1"
  # gdalinfo reports compression in IMAGE_STRUCTURE metadata, typically:
  #   COMPRESSION=LERC
  # or variants like LERC_ZSTD/LERC_DEFLATE in some datasets.
  gdalinfo "$f" 2>/dev/null | grep -Eq 'COMPRESSION=LERC($|_)'
}

default_output_path_for_input() {
  local input_path="$1"
  if [[ -d "$input_path" ]]; then
    echo "${input_path%/}-lzw"
  else
    local parent
    local base
    local stem
    parent="$(dirname "$input_path")"
    base="$(basename "$input_path")"
    stem="${base%.*}"
    echo "$parent/${stem}-lzw.tif"
  fi
}

collect_inputs() {
  local input_path="$1"
  local -n out_arr_ref="$2"

  out_arr_ref=()

  if [[ -d "$input_path" ]]; then
    while IFS= read -r -d '' f; do
      out_arr_ref+=("$f")
    done < <(find "$input_path" -maxdepth 1 -type f \( -iname '*.tif' -o -iname '*.tiff' \) -print0)
  elif [[ -f "$input_path" ]]; then
    is_tiff_path "$input_path" || die "Input file must end with .tif or .tiff: $input_path"
    out_arr_ref+=("$input_path")
  else
    die "Input path does not exist: $input_path"
  fi
}

convert_one() {
  local src="$1"
  local dst="$2"

  local dst_dir
  dst_dir="$(dirname "$dst")"
  mkdir -p "$dst_dir"

  local tmp="${dst}.tmp.$$"

  gdal_translate \
    -of GTiff \
    -co COMPRESS=LZW \
    -co TILED=YES \
    -co BLOCKXSIZE=512 \
    -co BLOCKYSIZE=512 \
    -co BIGTIFF=IF_SAFER \
    "$src" "$tmp"

  mv -f "$tmp" "$dst"
}

main() {
  require_cmd gdalinfo
  require_cmd gdal_translate

  local output_path=""
  local overwrite=false
  local strict=true
  local input_path=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      --overwrite)
        overwrite=true
        ;;
      --strict)
        strict=true
        ;;
      --no-strict)
        strict=false
        ;;
      -*)
        die "Unknown option: $1 (use --help)"
        ;;
      *)
        if [[ -n "$input_path" ]]; then
          if [[ -n "$output_path" ]]; then
            die "Too many positional arguments"
          fi
          output_path="$1"
        else
          input_path="$1"
        fi
        ;;
    esac
    shift
  done

  [[ -n "$input_path" ]] || die "Missing input path (use --help)"

  local -a inputs=()
  collect_inputs "$input_path" inputs
  [[ ${#inputs[@]} -gt 0 ]] || die "No .tif/.tiff files found in: $input_path"

  if [[ -z "$output_path" ]]; then
    output_path="$(default_output_path_for_input "$input_path")"
  fi

  local converted=0
  local skipped_existing=0
  local skipped_non_lerc=0
  local failed=0

  echo "Input:  $input_path"
  echo "Found ${#inputs[@]} file(s)"

  if [[ -d "$input_path" ]]; then
    [[ ! -f "$output_path" ]] || die "For directory input, output must be a directory path: $output_path"
    mkdir -p "$output_path"
    echo "Output directory: $output_path"

    for src in "${inputs[@]}"; do
      local base
      local dst
      base="$(basename "$src")"
      dst="$output_path/$base"

      if [[ -e "$dst" && "$overwrite" == false ]]; then
        echo "Skip existing: $dst"
        skipped_existing=$((skipped_existing + 1))
        continue
      fi

      if ! is_lerc_compressed "$src"; then
        if [[ "$strict" == true ]]; then
          die "Source is not LERC-compressed (or unreadable): $src"
        else
          warn "Skipping non-LERC source: $src"
          skipped_non_lerc=$((skipped_non_lerc + 1))
          continue
        fi
      fi

      echo "Converting: $src -> $dst"
      if convert_one "$src" "$dst"; then
        converted=$((converted + 1))
      else
        warn "Failed conversion: $src"
        failed=$((failed + 1))
      fi
    done
  else
    local src="${inputs[0]}"
    local dst="$output_path"

    is_tiff_path "$dst" || die "For file input, output must end with .tif or .tiff: $dst"
    echo "Output file: $dst"

    if [[ -e "$dst" && "$overwrite" == false ]]; then
      echo "Skip existing: $dst"
      skipped_existing=$((skipped_existing + 1))
    elif ! is_lerc_compressed "$src"; then
      if [[ "$strict" == true ]]; then
        die "Source is not LERC-compressed (or unreadable): $src"
      else
        warn "Skipping non-LERC source: $src"
        skipped_non_lerc=$((skipped_non_lerc + 1))
      fi
    else
      echo "Converting: $src -> $dst"
      if convert_one "$src" "$dst"; then
        converted=$((converted + 1))
      else
        warn "Failed conversion: $src"
        failed=$((failed + 1))
      fi
    fi
  fi

  echo ""
  echo "Summary:"
  echo "  Converted:        $converted"
  echo "  Skipped existing: $skipped_existing"
  echo "  Skipped non-LERC: $skipped_non_lerc"
  echo "  Failed:           $failed"

  [[ "$failed" -eq 0 ]] || exit 1
}

main "$@"