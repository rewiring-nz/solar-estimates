# Batch processing multiple areas

_This guide explains how to use the Python orchestrator to sequentially process multiple areas. This will allow you to run multiple small tiles/areas to cover a larger area overall, without running out of memory._

**Last updated:** March 2026

If you have downloaded data for multiple suburbs/districts or tiles, running them all manually one after the other can be tedious. You may also wish to run the pipeline over the entire country in small chunks, and have it running for several days/weeks. To allow this, we use a manager/worker architecture via `scripts/orchestrator.py`.

The orchestrator (manager) reads a text file of your desired areas and spins up the Docker container (worker, i.e. one run of scripts/pipeline.py) for one area at a time. Once an area is complete, the Docker container shuts down, completely clearing RAM and temporary files, before starting the next area. This prevents GRASS GIS memory leaks during long, potentially multi-day runs.

## 1. Create a batch list

Create a simple text file in `configs/batches/` that acts as your run manifest. Add the names of the config env files you want to run, one per line. 

!!! tip
    You can use `#` to add comments or temporarily disable specific runs without deleting them. 

See the text files already in [configs/batches/](../../configs/batches/) for examples. 
Ensure you have created the corresponding `.env` files in your `configs/` directory for every area listed in your batch file, and have the referenced input data files in `data/inputs/` as well (see [How-to: Use Your Own Source Data](./how-to-use-your-own-data.md)).

## 2. Run the orchestrator

You need to have python installed to run the orchestrator, but not really any other dependencies (other than docker of course). Run the orchestrator from your terminal as you would any other python script, from the project root:

```bash
python scripts/orchestrator.py --batch-file configs/batches/example_batch.txt
```