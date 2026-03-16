# Dockerfile: Sets up a multi-stage build environment for a Python-based geospatial pipeline.
# Installs GRASS GIS, GDAL, Python 3.12, and other dependencies on Ubuntu Noble (24.04 LTS).
# Uses a builder stage to compile and install application-specific dependencies.

# --- Builder for GRASS GIS and Python dependencies ---

# Use the robust Ubuntu Noble (24.04 LTS) base image for UbuntuGIS compatibility.
FROM ubuntu:noble AS builder

# Set environment for non-interactive installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install all system dependencies in one layer
RUN apt-get update \
    # Install tools needed for PPA, Python, and building packages
    && apt-get install -y --no-install-recommends \
        software-properties-common \
        build-essential \
        # Explicitly install Python 3.12, its headers, pip, and the venv package
        python3.12 \
        python3.12-dev \
        python3.12-venv \
        python3-pip \
        # SciPy dependency
        libatlas-base-dev \
    \
    # Add the UbuntuGIS Unstable PPA
    && add-apt-repository -y ppa:ubuntugis/ubuntugis-unstable \
    \
    # Re-update package list to load the packages from the PPA
    && apt-get update \
    \
    # Install all required geospatial libraries (GRASS and GDAL).
    && apt-get install -y --no-install-recommends \
        grass \
        grass-doc \
        gdal-bin \
        libgdal-dev \
    \
    # Clean up to reduce image size
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# --- PYTHON APPLICATION SETUP ---

# Set the working directory inside the container to /app/src, matching the local structure
WORKDIR /app

# Set Python 3.12 as the default for the container's 'python3' command
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1

# Set up virtual env
RUN python3 -m venv /opt/venv

# Add the venv's bin directory to the PATH environment variable
# All subsequent RUN commands will now use the venv's python and pip
ENV PATH="/opt/venv/bin:$PATH"

# Copy stuff we need for build first
COPY src/pyproject.toml ./src/
COPY docs/index.md ./docs/index.md

# Install Python dependencies AND documentation tools using the venv's pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir ./src \
    && pip install --no-cache-dir mkdocs-material mkdocstrings[python]

# Copy the other stuff, and a empty dir for data volume mount
COPY src/ ./src/
RUN mkdir -p /app/data
