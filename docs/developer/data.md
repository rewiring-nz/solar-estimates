# Key Project Datasets
_Primary datasets used in our prject._

### New Zealand LiDAR 1m DSM
* **Description:** A high-resolution surface model capturing the elevation of "first return" features, including the tops of buildings and tree canopies (920GB).
* **URL:** https://data.linz.govt.nz/layer/53621-nz-lidar-1m-dsm-2013-2024/
* **Project Use:** Used to calculate specific roof slopes and azimuths, and to model solar shading caused by local vegetation and neighboring structures.
* **Limitations:** Very large dataset.

### NZ 8m Digital Elevation Model
* **Description:** A national-scale elevation model describing the bare ground level, excluding surface objects like trees or buildings (18.84GB).
* **URL:** https://data.linz.govt.nz/layer/51768-nz-8m-digital-elevation-model-2012/
* **Project Use:** Provides the foundation for low-granularity shading analysis caused by large-scale terrain and mountain ranges.

### NZ Building Outlines
* **Description:** A dataset containing polygons representing the footprints of buildings across New Zealand (440MB).
* **URL:** https://data.linz.govt.nz/layer/101290-nz-building-outlines/
* **Project Use:** The primary dataset for identifying individual building locations and footprints for solar potential mapping.
* **Future:** Integrate NZ Building Outlines (All Sources) which seems to have more buildings, as well as duplicates.

## Tile Index

The 1m DSM and 8m DEM are tiled using the [New Zealand 1:10,000 tile index LINZ layer 104690](https://data.linz.govt.nz/layer/104690), creating individual georeferenced tiles (typically ~4,800 × 7,200 pixels at 1m resolution).

Tiles are named using the format `REGION_10000_INDEX.tif` (e.g., `BH31_10000_0403.tiff`). This enables downloading only tiles covering your region of interest rather than entire national datasets.

### Meshblock Higher Geographies
* **Description:** An administrative dataset that links individual meshblocks to higher-level statistical and local government boundaries (160MB).
* **URL:** https://datafinder.stats.govt.nz/layer/123519-meshblock-higher-geographies-2026/
* **Project Use:** Used to append administrative attributes to building data, enabling the aggregation of results by region or district.

## Reporting Boundaries

| Boundary | Title | Aggregates |
| :--- | :--- | :--- |
| **MB** | Meshblock: Street Block (60–120 residents) | — |
| **SA1** | Statistical Area 1: Neighborhood (100–500 residents) | MB |
| **SA2** | Suburb/Township (1,000–4,000 residents) | SA1s |
| **SA3** | Sub-District | SA2s |
| **TA** | Territorial Authority: Council/District | SA3s |
| **REGC** | Regional Council: Water Catchment Area | MB (does not always align with TAs) |

## Accessing LINZ Elevation Data

### Via S3 (Recommended for bulk access)

LINZ publishes elevation data as **Cloud Optimized GeoTIFFs** in the public S3 bucket `s3://nz-elevation` (region: `ap-southeast-2`). Public access requires no AWS credentials.

**Access methods:**
- **AWS CLI:** `aws s3 ls s3://nz-elevation/dsm_1m/ --no-sign-request`
- **s5cmd:** `s5cmd ls s3://nz-elevation/dsm_1m/`
- **GDAL:** `/vsicurl/https://nz-elevation.s3.ap-southeast-2.amazonaws.com/dsm_1m/...`

### Via STAC Metadata (Recommended for discovery)

LINZ publishes STAC Collections and Items for all elevation datasets. Use STAC to discover tile footprints and download links for specific bounding boxes:

- **STAC Browser:** https://data.linz.govt.nz/stac/v1/
- **Python:** Use `pystac-client` to query collections by geometry or spatial extent

### Via LINZ Data.govt.nz

Direct download available from https://data.linz.govt.nz/, but large datasets are more practical via S3 or STAC discovery for programmatic workflows.

### Processing Notes

- **Projection:** LINZ elevation data is natively in EPSG:2193 (NZTM2000). Processing uses this CRS directly (no reprojection overhead).
- **Compression:** Cloud Optimized GeoTIFFs use LERC compression, enabling efficient streaming (typically 50% smaller than LZW).
- **Tile Size:** ~512 × 512 blocks for rapid tile access via HTTP range requests.

## Viewing LINZ Elevation Data in QGIS

**Install a STAC plugin** to browse LINZ S3 layers directly without downloading:

1. In QGIS: **Plugins → Manage and Install Plugins**
2. Search for "STAC" and install a client (e.g., "STAC Browser" or "Spectral")
3. Connect to LINZ STAC: `https://data.linz.govt.nz/stac/v1/`
4. Browse collections and add layers to your map (streams from S3, no local storage)

### Local QGIS Viewing (Advanced)

LINZ tiles use LERC compression, which your local GDAL might not support. You can use the project Docker container to decode and convert them to LZW before opening in QGIS. (LZW files are ~2x larger).

The LZW files are written to your host filesystem and can be opened directly in QGIS. 

**Convert a directory of tiles (recommended):**

Output is written next to the source directory as `<input-dir>-lzw`:

```bash
docker compose run --rm pipeline sh -lc '
  /app/scripts/convert-to-lzw.sh data/inputs/DSM/<area-name>
'
```

Or do it manually calling GDAL from the command line:

```bash
# Convert a LERC-compressed tile to LZW for local QGIS viewing
gdal_translate -of GTiff \
  -co COMPRESS=LZW -co TILED=YES -co BLOCKXSIZE=512 -co BLOCKYSIZE=512 -co BIGTIFF=IF_SAFER \
  data-s3/CC11_10000_0102.tif data-s3-lzw/CC11_10000_0102-lzw.tif
  ```