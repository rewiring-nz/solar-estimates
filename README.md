# README: Rooftop Solar Map for New Zealand

Last Updated: 21 Sep 2025

### About

This project is developing an interactive map of rooftop solar potential for every building and carpark in New Zealand, backed by detailed data and quality analysis tools.

### Project goals

* Empower policymakers, planners, councils, community champions, businesses and households to accelerate the roll out of rooftop solar.  
* Provide personalised, detailed, and trustworthy evidence that rooftop solar is the cheapest delivered energy in New Zealand, even with New Zealand’s mountains, low winter sun angles, and shaded valleys.

### Features

* **Comprehensive**: Aims to cover every building and car park in New Zealand.  
* **Sophisticated modelling**: Will incorporate roof angles, shade profiles, weather patterns, economics.  
* **Useful layers**: Potential area and generation estimates can be aggregated by building type, region/local council area, and nationwide.  
* **Free**: The data, methodology, software, and web front-end are shared for free under an open license.

### Planned methodology

For the technically interested, this is our planned approach:

* Build upon New Zealand’s excellent free public datasets, combined with international best practices and tools for solar analysis.  
* Start with New Zealand national building footprints.  
* Calculate roof slopes and directions from 1m grid Digital Elevation Models (DEMs), available for much of New Zealand, deduce the rest.  
* Calculate shading profiles from mountains and contours (for the entire country).  
* Calculate shading profiles from nearby buildings and vegetation (where 1m grid data is available).  
* Apply “cloudy day” data from historical weather patterns.  
* Integrate with energy price models, to identify economically valuable surfaces.   
* Model how many solar panels may fit onto each roof. (Bonus marks if we calculate the different roof surfaces on each building.)  
* Plot the data into an interactive web map, aggregated at building, region, and national levels.  
* Validate against existing real-world solar installations.  
* Share software, datasets, and methodologies as open source, such that it can be replicated and extended by others.

### Timeframe

The project started in August 2025, we plan to have our first release in December 2025\.

### Contributing

We are interested to hear from like-minded, tech savvy people tackling similar problems who are interested in collaborating with us.

Refer to our [CONTRIBUTING.md](CONTRIBUTING.md) page for details.

### Team

#### Core Team
* **Coordinator:** Cameron Shorter, Geospatial Analyst, cameron DOT shorter AT gmail DOT com
* Jenny Sahng, Data Scientist, Rewiring Aotearoa  
* Shreyas Rama, Geospatial Data Science Masters, University of Canterbury

#### Contributors

* Rafferty Parker
* And multiple others (waiting on permission to list here)

#### Organisations
This project is supported by:
* [Rewiring Aotearoa](https://www.rewiring.nz/)
* [The University of Canterbury](https://www.canterbury.ac.nz/)
* [Anthill Ltd](https://anthill.co.nz/)

