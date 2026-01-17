
# Quickstart: Run pipeline script

_This quickstart describes how you can install and run our pipeline script to create your first map layers, based on a default dataset and default parameters._

## Prerequisites

* **Command Line:** Familiarity with running commands from a terminal.  
* **Docker:** Familiarity with [Docker](https://www.docker.com/). We use it to ensure the environment is consistent.  
* **Git (Optional):** Understanding `git` is helpful for managing updates. Refer to [GitHub's Git Guide](https://github.com/git-guides) for a quick overview.  
* **Admin Rights:** You will likely need administrator privileges to install Docker.

## 1: Download the Solar-Estimates Code

You can either download the code as a simple zip file or use `git` to clone the repository.

### Option 1A: Download and Unzip (Simplest)

```bash
# Move to your home directory
cd ~

# Download and unzip the latest source code 
wget https://github.com/rewiring-nz/solar-estimates/archive/refs/heads/main.zip 
unzip main.zip
mv ~/solar-estimates-main/ ~/solar-estimates/
cd ~/solar-estimates/
```

### Option 1B: Clone with Git (Recommended for Developers)

```bash
# Move to your home directory
cd ~

# clone repository
`git clone https://github.com/rewiring-nz/solar-estimates.git
cd solar-estimates/
```

!!! tip
    You can find these download details from the github source page: [https://github.com/rewiring-nz/solar-estimates](https://github.com/rewiring-nz/solar-estimates).

## 2: Install Docker

If you haven’t already installed Docker, follow the instructions for your operating system:

### Option 2A: Windows or Mac:

Follow the official [Docker Desktop installation guide](https://docs.docker.com/get-started/get-docker/).
Then start docker by opening the application. In your taskbar you should see a little whale icon. When clicked, it should say `Docker Desktop is running`.

### Option 2B: Ubuntu or Debian Linux:

You can use our setup script:

```bash
# Navigate to the scripts directory and run the installer 
cd scripts
sudo ./setup-docker.sh
```

## 3: Run the Pipeline

With Docker ready, you can now launch the processing pipeline. This process downloads required images and runs the analysis, which may take several minutes.

```bash
# Ensure you are in the project root directory (i.e. go back up one level if you were in scripts/)

docker compose up pipeline
```
You will see logs in your terminal as the `pipeline.sh` script executes.

Once finished, observe that you have created the following files in the `solar-estimates/src/` directory:

| File | Layer Type |
| :--- | :--- |
| `shotover_country_building_stats.gpkg` | **GeoPackage:** A spatial database containing a layer of building polygons and their solar attributes. |
| `shotover_country_merged.vrt` | **Virtual Raster:** A wrapper to multiple solar irradiation tiles. |
| `shotover_country_building_stats.csv` | **Tabular Data:** A spreadsheet of building solar attributes. |

## 4: Stop and Clean Up

When you are finished or want to stop the process, use the following command to shut down the Docker container safely:

```bash
# Again, run this from your root directory
docker compose down
```
## Next steps
1. **View Map Layers:** Why don't you use QGIS to view the map layers you just created, by following our [QGIS Quickstart](qgis-quickstart.md).