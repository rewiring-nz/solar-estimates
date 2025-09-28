#!/bin/bash
#
# FILE:         setup.sh
# AUTHOR:       NZ Solar Map Tool Development Team
# DATE:         2025-09-28
# DESCRIPTION:  Automated environment setup script for the 'solar-estimates' project.
#               Installs system dependencies (Git, GRASS, GDAL) and sets up the
#               Python Conda environment on a clean Ubuntu LTS Virtual Machine.
# LICENSE:      MIT

# Exit immediately if a command returns a non-zero status.
set -e

REPO_URL="https://github.com/rewiring-nz/solar-estimates.git"
REPO_DIR="solar-estimates"

echo "Starting NZ Solar Map Tool environment setup..."
echo "Targeting Ubuntu LTS with GRASS GIS and Conda-managed Python environment."

# --- 1. System Package Installation ---
echo "1/5: Updating system packages and installing core dependencies (git, GRASS, GDAL)..."
sudo apt update
# Install essential tools using apt.
sudo apt install -y build-essential git curl unzip grass-core gdal-bin

# --- 2. Clone the Repository (Context-Aware) ---

# Check if the script is already running inside a cloned repository.
# This checks for the presence of the hidden .git directory in the current working directory.
if [ -d ".git" ]; then
    echo "2/5: Already inside a git repository. Skipping clone."
    # Set REPO_DIR to the current directory for subsequent steps
    REPO_DIR="."
else
    echo "2/5: Not running inside a git repository. Cloning from $REPO_URL..."

    if [ -d "$REPO_DIR" ]; then
        echo "Repository directory '$REPO_DIR' already exists. Skipping clone, assuming code is present."
    else
        git clone $REPO_URL $REPO_DIR
    fi

    # IMPORTANT: Change directory into the cloned repository to find environment.yml
    cd $REPO_DIR
fi

# --- 3. Miniconda Installation ---
# Conda is used to manage a clean, reproducible Python environment as defined in environment.yml
CONDA_INSTALLER="Miniconda3-latest-Linux-x86_64.sh"
CONDA_PATH="$HOME/miniconda3"
echo "3/5: Installing Miniconda..."

if [ ! -d "$CONDA_PATH" ]; then
    # Use absolute path for consistency since we've changed directories
    curl -O https://repo.anaconda.com/miniconda/$CONDA_INSTALLER
    bash $CONDA_INSTALLER -b -p $CONDA_PATH
    rm $CONDA_INSTALLER
else
    echo "Miniconda already installed at $CONDA_PATH. Skipping download."
fi

# Initialize conda for the current shell session
source $CONDA_PATH/bin/activate

# --- 4. Conda Environment Setup ---
ENV_NAME="solar-estimates"
ENV_FILE="src/environment.yml"
echo "4/5: Creating Conda environment '$ENV_NAME' from $ENV_FILE..."

if conda info --envs | grep -q $ENV_NAME; then
    echo "Conda environment '$ENV_NAME' already exists. Recreating it to ensure cleanliness."
    conda env remove -n $ENV_NAME -y
fi

# Create the environment. This handles gdal and scipy dependencies.
conda env create -f $ENV_FILE

# Activate the new environment
conda activate $ENV_NAME

# --- 5. Post-Setup Instructions ---
echo "5/5: Environment setup complete! 🎉"
echo ""
echo "NEXT STEPS:"
echo "1. Activate your environment (if not already active):"
echo "   source $CONDA_PATH/bin/activate"
echo "   conda activate $ENV_NAME"
echo ""
echo "2. Update 'gisbase' in 'example.py' to the Ubuntu path:"
echo "   gscript, Module = setup_grass(gisbase=\"/usr/lib/grass\")"
echo ""
echo "3. Execute the example script (ensure you have the data/ directory set up):"
echo "   python3 example.py"