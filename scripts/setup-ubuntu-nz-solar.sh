#!/bin/bash
# DESCRIPTION:
# Install Ubuntu geospatial packages for New Zealand Solar Potential project
# from a raw Ubuntu LTS image.
#
# This script uses the ubuntugis-unstable PPA for the latest GRASS/GDAL.
#
# PREQUESISITES
# Run on Ubuntu LTS 24.04 (or similar) with sudo privileges.
#
# TO RUN:
# sudo ./setup-ubuntu-nz-solar.sh
#
# BACKGROUND:
# This script works around version mismatches and dependency clashes.
# We use the latest grass and gdal from the recent development version of ubuntugis.
# But we revert to Ubuntu LTS for other files.
# -------------------------------------------------------------

# Start by ensuring base system package lists are up to date
apt update

# Install python venv first, as it's not managed by the PPA
apt install -y python3.12-venv

echo "Adding UbuntuGIS Unstable PPA..."
apt install -y software-properties-common # Pulls in add-apt-repository for minimal ubuntu
add-apt-repository --yes ppa:ubuntugis/ubuntugis-unstable

# The PPA may be missing packages for the latest "questing" (25.10) release.
# We fix the source list file to point to the older, stable "noble" packages.
PPA_FILE=$(ls /etc/apt/sources.list.d/ | grep ubuntugis)
sed -i 's/questing/noble/g' /etc/apt/sources.list.d/$PPA_FILE

# Update the package list to include the packages from the
# newly added and corrected UbuntuGIS PPA.
apt update

echo "Installing core dependencies (GDAL, GRASS, and build tools)..."

# Install essential build tools/libraries and the geospatial packages
# python3-dev and gdal-bin/libgdal-dev are included here in one go.
apt install -y \
    build-essential \
    python3-dev \
    libcurl4-gnutls-dev \
    libc6-dev \
    gdal-bin \
    libgdal-dev \
    grass

echo "Installation complete. GRASS GIS and GDAL are ready."
