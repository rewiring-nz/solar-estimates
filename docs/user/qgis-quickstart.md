# Quickstart: Visualising Results in QGIS

_This quickstart describes how to view and query our geographic map layers using QGIS._

## What is QGIS?

We love [QGIS](https://qgis.org/). It is an intuitive, powerful, free, and open-source desktop GIS application, used for visualising geospatial maps, running spatial queries, and creating maps to share with others.

## 1. Setup environment and first map

If you haven't done so already, follow our [Pipeline Quickstart](pipeline-quickstart.md) to setup your environment and create your first map layers.

## 2. Install QGIS

Download and install QGIS, per instructions at the [QGIS Download page](https://qgis.org/download/).

## 3. Load Our Map Layers

1. Run QGIS on your desktop.
2. In the QGIS **Browser** pane, navigate to the `solar-estimates/src/` directory.
3. Double-click on the `suburb_ShotoverCountry_building_stats.gpkg` file to show it's layers.
4.  Right-click on the `building_stats` layer and select `Add Layer to Project`.
    1. See the building outlines getting rendered in the **Map** pane.
    2. See the buildings title get add to the **Layers** pane.

## 4. Add a Base Map (OpenStreetMap)

To see where these buildings are located in the real world, you can add OpenStreetMap as a background layer.

1. In the **Browser** panel, scroll down to `XYZ Tiles`.
2. Double-click on `XYZ Tiles` to expand it, and see the layers it supports.
3. Right-click `OpenStreetMap` and select `Add Layer to Project`.
4. **Move to Background:** In the **Layers** panel, click and drag the `OpenStreetMap` layer so it sits _under_ your building stats layer.

## 5. Query Building Data

We can query the attributes associated with each building.

1.  Select the **Identify Features** tool from the top toolbar (the icon with a small "i" and a white arrow pointer).
2.  Click on a building polygon in the map pane.
3.  An **Identify Results** panel will pop up, showing you all attributes for that building.

---

## Things to try
1. Try adding the `shotover_country_merged.vrt` layer to your map.