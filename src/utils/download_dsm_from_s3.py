#!/usr/bin/env python3
"""Download LINZ 1m DSM tiles from S3 using STAC and env-style config.

This script is intentionally standalone and follows the project's existing
configuration convention of KEY=VALUE env files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen, urlretrieve


def parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_env_file(env_path: Path) -> dict[str, str]:
    config: dict[str, str] = {}
    with env_path.open("r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            # Strip inline comments (e.g. VALUE=foo # comment) but only for
            # unquoted values — quoted strings may legitimately contain '#'.
            if not (value.startswith('"') or value.startswith("'")):
                for sep in (" #", "\t#"):
                    idx = value.find(sep)
                    if idx >= 0:
                        value = value[:idx].rstrip()
                        break
            value = value.strip('"').strip("'")
            config[key] = value
    return config


def parse_int(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    return int(value)


def fetch_json(url: str, timeout_seconds: int) -> dict[str, Any]:
    with urlopen(url, timeout=timeout_seconds) as response:
        return json.load(response)


def parse_bbox(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 4:
        raise ValueError("DOWNLOAD_BBOX must have 4 comma-separated values")
    minx, miny, maxx, maxy = map(float, parts)
    if minx >= maxx or miny >= maxy:
        raise ValueError("DOWNLOAD_BBOX must satisfy minx < maxx and miny < maxy")
    return (minx, miny, maxx, maxy)


def parse_tile_ids_from_file(path_value: str | None) -> set[str]:
    if not path_value:
        return set()
    path = Path(path_value)
    if not path.exists():
        raise ValueError(f"DOWNLOAD_TILE_IDS_FILE does not exist: {path}")
    tile_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as file:
        for raw_line in file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            tile_ids.add(line)
    return tile_ids


def intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def intersection_area(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
) -> float:
    if not intersects(a, b):
        return 0.0
    x_overlap = min(a[2], b[2]) - max(a[0], b[0])
    y_overlap = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, x_overlap) * max(0.0, y_overlap)


def parse_tile_ids(value: str | None) -> set[str]:
    if not value:
        return set()
    normalized = value.replace(",", " ")
    return {part.strip() for part in normalized.split() if part.strip()}


def resolve_item_asset(item: dict[str, Any], asset_key: str) -> dict[str, Any]:
    assets = item.get("assets", {})
    asset = assets.get(asset_key)
    if not isinstance(asset, dict):
        raise ValueError(
            f"Missing asset key '{asset_key}' in STAC item {item.get('id', '<unknown>')}"
        )
    href = asset.get("href")
    if not isinstance(href, str) or not href.lower().endswith((".tif", ".tiff")):
        raise ValueError(
            f"Asset '{asset_key}' is not a GeoTIFF in STAC item {item.get('id', '<unknown>')}"
        )
    return asset


def parse_checksum(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if ":" in normalized:
        algorithm, digest = normalized.split(":", 1)
        if algorithm and digest:
            return (algorithm, digest)
    # STAC examples from LINZ commonly use multihash for sha256: 0x12 0x20 + digest
    if normalized.startswith("1220") and len(normalized) == 68:
        return ("sha256", normalized[4:])
    return None


def compute_digest(file_path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    with file_path.open("rb") as file:
        while True:
            chunk = file.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def get_remote_content_length(url: str, timeout_seconds: int) -> int | None:
    try:
        request = Request(url, method="HEAD")
        with urlopen(request, timeout=timeout_seconds) as response:
            value = response.headers.get("Content-Length")
            if value is None:
                return None
            return int(value)
    except Exception:
        return None


def verify_local_file(
    file_path: Path,
    expected_size: int | None,
    checksum: tuple[str, str] | None,
) -> tuple[bool, str]:
    if not file_path.exists():
        return (False, "missing")

    actual_size = file_path.stat().st_size
    if expected_size is not None and actual_size != expected_size:
        return (False, f"size mismatch (expected {expected_size}, got {actual_size})")

    if checksum is not None:
        algorithm, expected_digest = checksum
        actual_digest = compute_digest(file_path, algorithm)
        if actual_digest.lower() != expected_digest.lower():
            return (False, f"checksum mismatch ({algorithm})")

    return (True, "valid")


def append_manifest_record(manifest_path: Path, record: dict[str, Any]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=True) + "\n")


def select_items(config: dict[str, str]) -> list[dict[str, Any]]:
    collection_url = config["S3_STAC_COLLECTION_URL"]
    timeout_seconds = parse_int(config.get("REQUEST_TIMEOUT_SECONDS"), default=30)
    asset_key = config.get("DOWNLOAD_ASSET_KEY")
    if not asset_key:
        raise ValueError("Missing required config key: DOWNLOAD_ASSET_KEY")
    collection = fetch_json(collection_url, timeout_seconds=timeout_seconds)

    bbox_filter = parse_bbox(config.get("DOWNLOAD_BBOX"))
    tile_id_filter = parse_tile_ids(config.get("DOWNLOAD_TILE_IDS"))
    tile_id_filter_from_file = parse_tile_ids_from_file(config.get("DOWNLOAD_TILE_IDS_FILE"))
    tile_id_filter.update(tile_id_filter_from_file)
    download_all = parse_bool(config.get("DOWNLOAD_ALL_COLLECTION_ITEMS"), default=False)

    if not download_all and not bbox_filter and not tile_id_filter:
        raise ValueError(
            "Set one selector: DOWNLOAD_ALL_COLLECTION_ITEMS=true, DOWNLOAD_TILE_IDS(_FILE), or DOWNLOAD_BBOX"
        )

    item_links = [
        urljoin(collection_url, link["href"])
        for link in collection.get("links", [])
        if link.get("rel") == "item" and isinstance(link.get("href"), str)
    ]
    if not item_links:
        raise ValueError("No STAC item links found in collection")

    selected: list[dict[str, Any]] = []
    for item_url in item_links:
        item = fetch_json(item_url, timeout_seconds=timeout_seconds)
        item_id = item.get("id")
        if not isinstance(item_id, str):
            continue

        item_bbox_raw = item.get("bbox")
        if not (
            isinstance(item_bbox_raw, list)
            and len(item_bbox_raw) >= 4
            and all(isinstance(v, (int, float)) for v in item_bbox_raw[:4])
        ):
            continue
        item_bbox = (
            float(item_bbox_raw[0]),
            float(item_bbox_raw[1]),
            float(item_bbox_raw[2]),
            float(item_bbox_raw[3]),
        )

        overlap = intersection_area(item_bbox, bbox_filter) if bbox_filter else 1.0
        by_tile = bool(tile_id_filter and item_id in tile_id_filter)
        by_bbox = bool(bbox_filter and overlap > 0)
        by_all = download_all
        if not (by_tile or by_bbox or by_all):
            continue

        asset = resolve_item_asset(item, asset_key=asset_key)
        asset_href = urljoin(item_url, str(asset["href"]))
        checksum = parse_checksum(asset.get("file:checksum"))
        expected_size = asset.get("file:size")
        if isinstance(expected_size, str) and expected_size.isdigit():
            expected_size = int(expected_size)
        if not isinstance(expected_size, int):
            expected_size = get_remote_content_length(asset_href, timeout_seconds=timeout_seconds)

        selected.append(
            {
                "id": item_id,
                "bbox": item_bbox,
                "overlap_area": overlap,
                "asset_href": asset_href,
                "expected_size": expected_size,
                "checksum": checksum,
            }
        )

    selected.sort(key=lambda x: (-float(x["overlap_area"]), str(x["id"])))

    max_tiles_value = config.get("MAX_TILES")
    if max_tiles_value is not None and max_tiles_value.strip():
        max_tiles = parse_int(max_tiles_value, default=0)
        if max_tiles > 0:
            selected = selected[:max_tiles]

    return selected


def output_name_for_download(asset_href: str, save_as_tif: bool) -> str:
    source_name = Path(urlparse(asset_href).path).name
    if save_as_tif and source_name.lower().endswith(".tiff"):
        return source_name[:-5] + ".tif"
    return source_name


def download_items(items: list[dict[str, Any]], config: dict[str, str]) -> None:
    output_area_name = config.get("OUTPUT_AREA_NAME", "suburb_ShotoverCountry")
    output_dir = Path(
        config.get("OUTPUT_DSM_DIR", f"data/inputs/DSM/{output_area_name}_s3")
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    overwrite = parse_bool(config.get("OVERWRITE"), default=False)
    save_as_tif = parse_bool(config.get("SAVE_AS_TIF"), default=True)
    max_retries = parse_int(config.get("MAX_DOWNLOAD_RETRIES"), default=2)
    max_tiles_value = config.get("MAX_TILES")
    preview_only = bool(max_tiles_value is not None and max_tiles_value.strip() and parse_int(max_tiles_value, default=0) == 0)
    manifest_path = Path(
        config.get(
            "DOWNLOAD_MANIFEST_PATH",
            str(output_dir / "download_manifest.jsonl"),
        )
    )

    # Track timing and data transfer
    start_time = time.time()
    total_bytes_downloaded = 0
    total_expected_bytes = 0
    download_count = 0
    skipped_count = 0
    preview_count = 0

    print(f"Selected {len(items)} item(s)")
    if preview_only:
        print("MAX_TILES=0 -> preview-only mode (no files will be downloaded)")
    for item in items:
        tile_id = str(item["id"])
        asset_href = str(item["asset_href"])
        expected_size = item.get("expected_size")
        checksum = item.get("checksum")
        out_name = output_name_for_download(asset_href, save_as_tif=save_as_tif)
        out_path = output_dir / out_name

        print(f"- {tile_id}: {asset_href}")
        if expected_size is not None:
            print(f"  expected_size={expected_size}")
        if isinstance(expected_size, int):
            total_expected_bytes += expected_size
        if preview_only:
            append_manifest_record(
                manifest_path,
                {
                    "timestamp_utc": datetime.now(UTC).isoformat(),
                    "tile_id": tile_id,
                    "asset_href": asset_href,
                    "output_path": str(out_path),
                    "status": "preview_only",
                    "expected_size": expected_size,
                    "checksum": checksum,
                },
            )
            preview_count += 1
            continue

        if out_path.exists() and not overwrite:
            is_valid, reason = verify_local_file(
                out_path,
                expected_size=expected_size if isinstance(expected_size, int) else None,
                checksum=checksum if isinstance(checksum, tuple) else None,
            )
            if is_valid:
                print(f"  skip (already valid): {out_path}")
                append_manifest_record(
                    manifest_path,
                    {
                        "timestamp_utc": datetime.now(UTC).isoformat(),
                        "tile_id": tile_id,
                        "asset_href": asset_href,
                        "output_path": str(out_path),
                        "status": "skipped_valid",
                        "expected_size": expected_size,
                        "checksum": checksum,
                    },
                )
                skipped_count += 1
                continue

            print(f"  existing file invalid ({reason}), re-downloading")

        success = False
        last_error = "unknown"
        for attempt in range(1, max_retries + 2):
            temp_path = out_path.with_suffix(out_path.suffix + ".part")
            if temp_path.exists():
                temp_path.unlink()

            try:
                urlretrieve(asset_href, temp_path)
                is_valid, reason = verify_local_file(
                    temp_path,
                    expected_size=expected_size if isinstance(expected_size, int) else None,
                    checksum=checksum if isinstance(checksum, tuple) else None,
                )
                if not is_valid:
                    temp_path.unlink(missing_ok=True)
                    raise RuntimeError(f"download verification failed: {reason}")

                temp_path.replace(out_path)
                actual_size = out_path.stat().st_size
                total_bytes_downloaded += actual_size
                download_count += 1
                print(f"  downloaded -> {out_path} ({actual_size / 1e6:.1f} MB)")
                append_manifest_record(
                    manifest_path,
                    {
                        "timestamp_utc": datetime.now(UTC).isoformat(),
                        "tile_id": tile_id,
                        "asset_href": asset_href,
                        "output_path": str(out_path),
                        "status": "downloaded",
                        "attempt": attempt,
                        "expected_size": expected_size,
                        "checksum": checksum,
                    },
                )
                success = True
                break
            except Exception as exc:
                last_error = str(exc)
                print(f"  attempt {attempt} failed: {last_error}")

        if not success:
            append_manifest_record(
                manifest_path,
                {
                    "timestamp_utc": datetime.now(UTC).isoformat(),
                    "tile_id": tile_id,
                    "asset_href": asset_href,
                    "output_path": str(out_path),
                    "status": "failed",
                    "error": last_error,
                    "expected_size": expected_size,
                    "checksum": checksum,
                },
            )
            raise RuntimeError(f"Failed to download {tile_id} after retries: {last_error}")
    
    # Print summary
    elapsed_seconds = time.time() - start_time
    print(f"\n=== Download Summary ===")
    print(f"Downloaded: {download_count} tile(s), {total_bytes_downloaded / 1e9:.2f} GB")
    print(f"Skipped (valid): {skipped_count} tile(s)")
    if preview_only:
        print(f"Previewed: {preview_count} tile(s), {total_expected_bytes / 1e9:.2f} GB expected")
    print(f"Elapsed time: {elapsed_seconds:.1f} seconds")
    if download_count > 0 and elapsed_seconds > 0:
        mb_per_sec = (total_bytes_downloaded / 1e6) / elapsed_seconds
        print(f"Transfer rate: {mb_per_sec:.1f} MB/s")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download LINZ 1m DSM tiles from S3 using STAC collection filters"
    )
    parser.add_argument(
        "--config",
        default="configs/suburb_ShotoverCountry_s3_minimal.env",
        help="Path to KEY=VALUE config file (default: configs/suburb_ShotoverCountry_s3_minimal.env)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"Config file does not exist: {config_path}")

    config = parse_env_file(config_path)
    if "S3_STAC_COLLECTION_URL" not in config:
        raise SystemExit("Missing required config key: S3_STAC_COLLECTION_URL")

    items = select_items(config)
    if not items:
        raise SystemExit(
            "No matching tiles found. Adjust DOWNLOAD_TILE_IDS(_FILE), DOWNLOAD_BBOX, or DOWNLOAD_ALL_COLLECTION_ITEMS"
        )
    download_items(items, config)


if __name__ == "__main__":
    main()
