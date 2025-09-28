# Developer Quickstart

This document describes how a developer can get the New Zealand Solar Map tools running in a development environment.

## Context

We have designed the New Zealand Solar Map tools to run in a linux environment, although other platforms will likely work too.  
For development, we recommend working on a small subset of data, to reduce your CPU compute time.  
To process data across the country, we typically make use of large cloud compute.  
This documentation describes:

* Setting up a free Google Cloud Platform (GCP) Ubuntu environment.  
* Configuring up the linux environment.  
* Running your first “Hello World” instance.

## Google Cloud Ubuntu free-tier setup

This how-to describes setting up a free tier virtual machine (VM) on Google Cloud Platform (GCP) for your NZ Solar Map Tool development.

### Task 1: Create a Google Cloud account

Step 1.1 Create a [Google Cloud](https://cloud.google.com/) account with an active project and billing enabled (necessary even for free-tier usage).

### Task 2: Create a [Virtual Machine](https://console.cloud.google.com/compute/instances) 

Step 2.1: From the Compute Engine, select “Create Instance”

Step 2.2: Select options:

1. **Region:** Iowa, Oregon, or South Carolina  
   > [!WARNING] These are the only **free** regions. Be careful not to select others.  
2. **Machine Type:** E2 \-\> E2-micro.  
   > [!WARNING]  This is the only **free** machine type.  
3. **Operating System:** Ubuntu Pro, Ubuntu 24.04 LTS  
4. **Disk Size:** 30 GB

### Task 3: Connect via SSH

The easiest way to connect to your new virtual machine is via the browser-based SSH tool provided by GCP.

1. On the [Virtual Machine](https://console.cloud.google.com/compute/instances) page, find your new instance.  
2. In the row for your instance, click the SSH button.  
3. A separate browser window will open, automatically establishing a secure connection to your Ubuntu terminal.

## Task 4: Install applications

The applications and git repository you will need to setup are loaded by the script [setup.sh](https://github.com/rewiring-nz/solar-estimates/blob/main/setup.sh).  
Step 4.1 In a bash terminal, download and then run [setup.sh](https://github.com/rewiring-nz/solar-estimates/blob/main/setup.sh) script.

```bash
# Download and run setup script which installs dependancies and applications and git repository 
wget https://github.com/rewiring-nz/solar-estimates/blob/main/setup.sh  
sudo bash setup.sh
```