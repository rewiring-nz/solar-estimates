# Developer Quickstart

_This document describes how a developer can get the New Zealand Solar Map tools running in a development environment._

**Last updated:** Jan 2026

## Context

As at November 2025, these scripts are still a work-in-progress. Reach out to the team for latest advice.

* The scripts were initially developed on Mac, as explained in ../src/README.md
* We now have a version running on Ubuntu 24.04 LTS. Follow install script in ../scripts/setup-ubuntu-nz-solar.sh , then run the python scripts in ../src/README.md

## Google Cloud Ubuntu free-tier setup
As at Nov 2025, we haven't got the Cloud Ubuntu environment working. This is as far as we've got so far:

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
