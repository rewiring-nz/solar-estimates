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