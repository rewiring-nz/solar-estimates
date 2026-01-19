# How-to: Use Your Own Source Data

_This guide explains how to source and use your own data for our solar pipeline generation script, running within a Docker container._

**Last updated:** Jan 2026

!!! warning
    Our pipeline script is CPU intensive. You are likely to run out of memory, or take a very long time to run. Best to start with small datasets before getting larger.

## 1. Where to Get Source Data

The pipeline script requires two primary inputs: **Digital Surface Models (DSM)** and **Building Outlines**.

### 1.1 Digital Surface Models (DSM)
For accurate solar modeling (including roof pitch and shading from chimneys or trees), you need a **1m resolution DSM**.
* **Source:** Search for the latest at: [LINZ Data Service - New Zealand LiDAR 1m DSM](https://data.linz.govt.nz/data/?q=New+Zealand+LiDAR+1m+DSM)
* **Format:** Download as GeoTIFF files.
* **Region:** Select a region you are interested in. You might experience download size limits.
* **Coordinate System:** Ensure your data is in **EPSG:2193** (NZGD2000 / New Zealand Transverse Mercator 2000).

!!! tip
    Digital *Surface* Models (DSM) include building rooftops and tree tops. Digital *Elevation* Models (DEM) are not suitable for our analysis as they represent bare ground elevation.

### 1.2 Building Outlines
* **Source:** [LINZ Data Service - All Building Outlines](https://data.linz.govt.nz/data/?q=building+outlines)
* **Format:** Download as a GeoPackage.
* **Coordinate System:** Ensure your data is in **EPSG:2193** (NZGD2000 / New Zealand Transverse Mercator 2000).

!!! tip
    The [Geopackage](https://www.geopackage.org/) format is faster for spatial analysis than the legacy `shapefile` format. It is a standards based [Spatialite](https://www.gaia-gis.it/fossil/libspatialite/index) database in a file, which extends the [SQLite](https://sqlite.org/) format.

## 2. Organizing Your Data Folder

To make your data accessible to the pipeline.py script, within your Docker container, you should place it within the `src/data/` directory of the project.

Create a new sub-folder for your specific area to keep things organized:
```text
solar-estimates/
└── src/
    └── data/
        └── my-council/
            ├── dsm_tile_1.tif
            ├── dsm_tile_2.tif
            └── nz-building-outlines-all-sources.gpkg
```

## 3. Run the Pipeline with Custom Data

To run the pipeline script with our own data, we use the docker `compose run command` to override the default arguments.

```bash
docker compose run pipeline /opt/venv/bin/python /app/src/pipeline.py \
  --area-name "my-council" \
  --dsm-glob "data/my-council/*.tif" \
  --building-dir "data/my-council" \
  --building-layer-name "nz-building-outlines-all-sources"
```

### 3.1 Breakdown of Arguments
* **`--area-name`**: This prefix will be used for your output GeoPackage.
* **`--dsm-glob`**: The path to your DSM files inside the container. Since the project root is mounted to `/app` in the Docker environment, the path starts with `data/...`.
* **`--building-dir`**: The folder containing your source building GeoPackage inside the container.
* **`--building-layer-name`**: The specific name of the layer inside your GeoPackage.

## Next steps
Why don't you try changing some of the other input attributes.