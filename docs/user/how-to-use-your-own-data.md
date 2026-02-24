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
* **Format:** Download as a ShapeFile.
* **Coordinate System:** Ensure your data is in **EPSG:2193** (NZGD2000 / New Zealand Transverse Mercator 2000).

!!! tip
    The [Geopackage](https://www.geopackage.org/) format is faster for spatial analysis than the legacy `shapefile` format. It is a standards based [Spatialite](https://www.gaia-gis.it/fossil/libspatialite/index) database in a file, which extends the [SQLite](https://sqlite.org/) format.

!!! note
    We've observed:

    * [NZ Building Outlines, Dec 2025](https://data.linz.govt.nz/data/?q=building+outlines) provides an authoritative dataset, but is missing some buildings.
    * [NZ Building Outlines (All Sources), Dec 2025](https://data.linz.govt.nz/data/?q=NZ+Building+Outlines+%28All+Sources%29) covers more buildings, but also has duplicates.

## 2. Organising Your Data Folder

To make your data accessible to the pipeline.py script in your Docker container, put it in the appropriate sub-folders within `src/data/inputs`. There are folders for different data types (e.g. buliding outlines, DSMs, weather). You should create a new sub-folder for data on new areas, named something like `district_YourDistrictHere`, `suburb_YourSuburbHere`, `region_*`, `electorate_*`, `ta_*` (territorial authority), or `nationwide`, to make it really clear exactly what is included in the data and what is not. Use `snake_case`, not `kebab-case`, for consistency (kebab case is reserved for other things in parts of the pipeline).

The pipeline will calculate for the areas in the intersect of the building outlines and the DSMs provided. So they don't have to be exactly the same, e.g. you might have a DSM of just the suburb Shotover Country, but run it with building outlines for all of the Queenstown Lakes district.

```text
solar-estimates/
└── src/
    └── data/
        └── inputs/
            └── building_outlines/
                ├── district_MyCoolDistrict/
                    ├── nz-building-outlines.cpg
                    ├── nz-building-outlines.dbf
                    ├── nz-building-outlines.prj
                    ├── nz-building-outlines.shp
                    ├── nz-building-outlines.shx
                    ├── nz-building-outlines.txt
                    └── nz-building-outlines.xml
            └── DEM/
            └── DSM/
                └── district_MyCoolDistrict/
                    ├── dsm_tile_1.tif
                    ├── dsm_tile_1.tif.aux.xml
                    ├── dsm_tile_2.tif
                    └── dsm_tile_2.tif.aux.xml
                    ...
            └── weather/
                └── nationwide/
```


## 3. Create a config file

Since the pipeline has a lot of long input arguments, we have config environment files where you can organise these. See the `config/` folder for examples and create a new one that points to your newly organised custom data.

The pipeline has many input arguments that you can try. See `src/README.md` for an explanation of each of the arguments.

## 4. Run the pipeline with your custom data

To run the pipeline script with your own data by pointing the docker container towards a particular environment file, like this example:

```bash
docker compose --env-file configs/shotover.env up pipeline
```

The output will appear in the `src` directory:

```text
solar-estimates/
└── src/
    ├── my_council_building_stats.csv
    ├── my_council_building_stats.gpkg
    └── my_council_merged.vrt
```

The pipeline has many input arguments that you can try. See `src/README.md` for an explanation of each of the arguments.