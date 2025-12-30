# Project Overview

This project will provide accurate and validated estimates of rooftop solar potential for almost every building in New Zealand, for use in tools such as interactive maps.  
View our maps in our [Felt webmap browser](https://felt.com/map/solar-estimates-data-0-0-1-hrZt5lhuQXySjcQGbx9CwzA?loc=-45.00495,168.76761,14.69z).

# About

## Features

* **Comprehensive**: Aims to cover every building in New Zealand, where data is available.  
* **Sophisticated modelling**: Will incorporate roof angles, shade profiles, weather patterns, economics.  
* **Useful layers**: Potential area and generation estimates can be aggregated by building type, region/local council area, and nationwide.  
* **Free**: The data, methodology, software, and any web front-end are shared for free under open licenses.

## Project goals

* Empower policymakers, planners, councils, community champions, businesses and households to make evidence based decisions which accelerate the roll out of rooftop solar.  
* Provide personalised, detailed, and trustworthy evidence of the rooftop solar potential for every rooftop in New Zealand.  
* Demonstrate that rooftop solar provides the cheapest delivered energy in New Zealand, even with New Zealand’s mountains, low winter sun angles, and shaded valleys.

# Downloads

## Webmap

View our latest maps in our [Felt webmap browser](https://felt.com/map/solar-estimates-data-0-0-1-hrZt5lhuQXySjcQGbx9CwzA?loc=-45.00495,168.76761,14.69z).

## Datasets

Our spatial datasets can be downloaded from our [Releases](https://drive.google.com/drive/u/0/folders/1vn0D9Gh6Tn7wS-0ftMRBGsQIWFtjAMbU) directory. These include:

* Shotover\_country\_building\_stats-0.0.1.gpkg  
  * Buildings in Shotover County, with annual solar potential  
* Shotover\_country\_building\_stats-0.0.1.csv  
  * Just the attributes, in CSV format  
* shotover\_country\_merged-0.0.1.zip spatial diff and vrt.  
  * 1x1 meter grid showing solar potential of each grid

**About datasets**  
You can download the maps, and then view and analyse from your favourite desktop GIS application.  
We like the free and powerful [QGIS](https://qgis.org/).

## Software

Our latest software can be downloaded from our git repository:

* [https://github.com/rewiring-nz/solar-estimates](https://github.com/rewiring-nz/solar-estimates) 

A tagged software release is on our roadmap.

## Version history

**Next steps:**

* Expand our analysis area to all of New Zealand.  
* Incrementally replace assumptions with deeper analysis, and more data, as listed in tasks in our [project kanban board](https://github.com/orgs/rewiring-nz/projects/3).

| Date | Version | Description |
| :---- | :---- | :---- |
| 2025-01-30 | 0.0.1 | Proof of concept.<br>Provides map layers for annual solar potential for: 1\. Rooftops. 2\. 1x1m grid.<br>Considers rooftop slope and direction.<br>Shading calculated from 1x1 grid Digital Surface Model, considers distant mountains and local (trees).<br>Estimates used for other parameters, such as weather.<br>Pipeline script runs in docker.<br>Region limited to a small suburb in Shotover County, New Zealand. |