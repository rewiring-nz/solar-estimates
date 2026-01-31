# Software Architecture and System Design

## Overview
The **solar-estimates** project is a **Docker** containerised geospatial processing pipeline designed to estimate rooftop solar potential across New Zealand. It leverages **GRASS GIS** for heavy-duty spatial analysis and **GDAL** for data translation, all orchestrated by a **Python 3.12** ```pipeline.py``` application.

_This content is mostly AI generated from source code (as at Jan 2026)._

**Last updated:** Feb 2026

## System Workflow

```mermaid
flowchart TD

    %% Stage 1: Input Datasets
    subgraph Inputs ["Input Datasets"]
        SD1[(DSM GeoTIFF Tiles)]
        SD2[(Building Outlines)]
        SD3[(WRF NetCDF - Optional)]
    end

    %% Stage 2: Interim Datasets
    subgraph Interim ["Interim Datasets (Internal GRASS/VRT)"]
        ID1[[Merged VRT]]
        ID2[[GRASS DSM Raster]]
        ID3[[Slope & Aspect Rasters]]
        ID4[[Clear-Sky Irradiance]]
        ID5[[Building Vector Map]]
        ID6[[Solar on Buildings]]
        ID7[[Filtered Irradiance]]
        ID8[[Solar Coefficients]]
        ID9[[WRF Adjusted Total]]
    end

    %% Stage 3: Target Datasets
    subgraph Targets ["Output Target Datasets"]
        TD1[Building Stats GeoPackage]
        TD2[Building Stats CSV]
        TD3[Multi-band GeoTIFF]
    end

    %% Data Flow and Transformation Labels
    SD1 -- "merge_rasters" --> ID1
    ID1 -- "load_virtual_raster_into_grass" --> ID2
    ID2 -- "calculate_slope_aspect_rasters" --> ID3
    ID2 & ID3 -- "calculate_solar_irradiance_interpolated" --> ID4
    SD2 -- "load_building_outlines" --> ID5
    ID4 & ID5 -- "calculate_outline_raster" --> ID6
    ID6 & ID3 -- "filter_raster_by_slope" --> ID7
    
    %% Optional WRF Path
    SD3 -- "process_wrf_for_grass" --> ID8
    ID4 -- "calculate_solar_coefficients" --> ID8
    ID8 -- "calculate_wrf_adjusted_per_day" --> ID9
    
    %% Final Exports
    ID7 & ID9 & ID5 -- "create_stats" --> TD1
    ID7 & ID9 & ID5 -- "create_stats" --> TD2
    ID7 & ID3 -- "export_final_raster" --> TD3
```

## Technology Stack

### Containerisation
The system is built on **Docker** and **Docker Compose** to ensure a consistent environment across different platforms (Linux, macOS, Windows).

*   **Base Image:** Ubuntu 24.04 LTS (Noble).
*   **Geospatial Libraries:** Uses the **UbuntuGIS Unstable PPA** to provide the latest versions of GRASS GIS (8.4+) and GDAL.
*   **Python Environment:** Dependencies are managed within a virtual environment (`/opt/venv`) to avoid conflicts with system-level packages.

### Computational Engines

*   **GRASS GIS:** Acts as the primary spatial database and computational engine. It handles solar radiation modelling (`r.sun`), geometric calculations (`r.slope.aspect`), and statistical aggregation.
*   **GDAL:** Used for initial data discovery, building Virtual Rasters (VRT), and final data format exports.

## Target architecture

The following diagram shows the future architecture we are working toward.

```mermaid
flowchart TD

    %% Style for Future items (traffic-light amber)
    classDef future fill:#FFE0B2,stroke:#FB8C00,stroke-width:1px,color:#000;

    subgraph A ["**Sources**"]
        
        subgraph AA ["**Spatial Datasets**"]
            direction LR
            AA1[1m Digital Surface Models]
            AA2[National building footprints]
        end

        subgraph AB ["**Other Datasets**"]
            direction LR
            AB1[Weather: MetService hindcasts]
            AB2[Energy price - Future]
            AB3[**Reference Installs**]
        end

        subgraph AC ["**Open Source Software**"]
            direction LR
            AC1[Python scripts]
            AC2[GRASS spatial algorithms]
            AC3[Docker containers]
        end

        %% Layout
        AA ~~~ AB ~~~ AC
    end

    subgraph B ["**Analysis**"]
        subgraph BA ["**Spatial Processing**"]
            direction LR
            BA1(Roof slope / aspect)
            BA2(Shade - Distant mountains / Local Veg)
            BA3(Roof segment / Solar panel fit - Future)
            BA4(Time-of-day / Time-of-year)
            BA5(Aggregation: Region / National - Future)
        end

        subgraph BB ["**Weather Analysis**"]
            direction LR
            BB1(Cloudy weather probability - Future)
            BB2(Scenarios - cold winter week - Future)
        end

        subgraph BC ["**Temporal Energy (Future)**"]
            direction LR
            BC1(Spot Energy Price - Future)
            BC2(Household/Network Load - Future)
            BC3(Load-shift - Future)
            BC4(Battery optimization - Future)
        end

        %% Layout
        BA ~~~ BB ~~~ BC
    end

    subgraph C ["**Validation**"]
        direction LR
        CA1(Against real installations - Future)
    end

    subgraph D ["**Dissemination**"]
        direction LR
        
        subgraph DA ["**Reports**"]
            direction LR
            DA1[Solar energy potential]
            DA2[Financial viability - Future]
            DA3[Temporal resilience - Future]
            DA4[Network resilience - Future]
            DA5[Scale: Building, Region, Nation]
        end

        subgraph DB ["**Downloads**"]
            direction LR
            DB1[Interactive Web Map]
            DB2[Data and Map Downloads]
            DB3[Open-Source Code]
        end

        %% Layout
        DA ~~~ DB
    end

    %% Sequential Flow
    A --> B --> C --> D

    %% Apply Future styling
    class AB2,BA3,BA5,BB1,BB2,BC1,BC2,BC3,BC4,CA1,DA2,DA3,DA4 future
```
_Diagram: Target high level architecture. Boxes tagged with "Future" are planned for a future implementation._