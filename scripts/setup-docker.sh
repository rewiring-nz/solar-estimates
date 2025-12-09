#!/bin/bash
# Docker Setup Script, to setup Docker for Debian, Ubuntu, and Chromebook (Crostini)
#
# USAGE: Run this script with sudo from your standard user account:
#        sudo ./setup-docker.sh
#
# This script performs the following actions:
# 1. Updates package lists and installs necessary dependencies.
# 2. Automatically detects the distribution (Ubuntu or Debian/Crostini) and sets the correct
#    Docker repository.
# 3. Installs the core Docker Engine components (docker-ce, docker-ce-cli, containerd.io).
# 4. Adds the current non-root user who ran 'sudo' to the 'docker' group for permissionless
#    usage.

# --- Safety checks ---
# 1. Check if the script has root privileges (EUID=0)
if [ "$EUID" -ne 0 ]; then
  echo "Error: This script must be run with 'sudo' by a non-root user."
  echo "Usage: sudo ./setup-docker.sh"
  exit 1
fi

# 2. Check if the script was run directly as root (i.e., SUDO_USER is not set)
TARGET_USER="${SUDO_USER}"
if [ -z "$TARGET_USER" ] || [ "$TARGET_USER" == "root" ]; then
    echo "Error: The script was run directly as root (e.g., via 'sudo su -' or 'sudo -i')."
    echo "This script must be executed via 'sudo' from a standard user account"
    echo "to correctly identify the user who needs permissions to run Docker without sudo."
    echo "Please use: sudo ./setup-docker.sh"
    exit 1
fi

# --- Environment Detection ---
# Check if the distribution ID is 'ubuntu' or default to 'debian' for Crostini/Debian.
if grep -q ^ID=ubuntu /etc/os-release; then
    REPO_DISTRO="ubuntu"
    DISTRO_NAME="Ubuntu"
else
    # This covers Debian, Crostini (which is a Debian container), and other derivatives.
    REPO_DISTRO="debian"
    DISTRO_NAME="Debian/Crostini"
fi

echo "--- Starting Docker Installation for $DISTRO_NAME (Target User: $TARGET_USER) ---"

# 1. Update package lists and install necessary dependencies
echo "1. Installing system dependencies..."
apt update -y
apt install -y ca-certificates curl gnupg lsb-release

# 2. Add Docker's official GPG key and set up the repository
echo "2. Setting up Docker GPG key and repository for $REPO_DISTRO..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/"$REPO_DISTRO"/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Add the repository to Apt sources, using the detected distribution and codename.
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/"$REPO_DISTRO" \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# 3. Install Docker Engine, CLI, and Compose plugin
echo "3. Installing Docker Engine and related components..."
apt update -y
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 4. Add the user to the 'docker' group to run commands without sudo
if [ -n "$TARGET_USER" ]; then
    echo "4. Adding user '$TARGET_USER' to the 'docker' group..."
    usermod -aG docker "$TARGET_USER"
fi

echo "--- Installation Complete! ---"
echo "You can verify the installation with: systemctl status docker"
echo ""
echo "!!! IMPORTANT NEXT STEP: RESTART YOUR SESSION !!!"
echo "The changes to the 'docker' user group WILL NOT take effect until your current session is reset."
echo ""
echo "For Debian or Ubuntu Desktop/Server:"
echo "    Log out and log back in, or run the command: newgrp docker"
echo ""
echo "For Chromebook (Crostini):"
echo "    Right-click the Terminal app on the shelf and select 'Shut down Linux', then re-open the Terminal."
echo ""
echo "After restarting, run 'docker run hello-world' to test the setup."
