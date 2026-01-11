
# Software design
This section concisely touches on key design concepts for our ```solar estimates``` project. 

We aim to keep this document **concise** and **timeless**, so that it is:

* Quick to read.
* Easy to absorb.
* Easy to maintain.

**Last updated:** Jan 2026

## High level architecture

```mermaid
flowchart TD

    subgraph A ["**Sources**"]
        
        subgraph AA ["**Spatial Datasets**"]
            direction LR
            AA1[1m Digital Surface Models]
            AA2[National building footprints]
        end

        subgraph AB ["**Other Datasets**"]
            direction LR
            AB1[Weather: MetService hindcasts]
            AB2[Energy price - Future]
            AB3[**Reference Installs**]
        end

        subgraph AC ["**Open Source Software**"]
            direction LR
            AC1[Python scripts]
            AC2[GRASS spatial algorithms]
            AC3[Docker containers]
        end

        %% Layout
        AA ~~~ AB ~~~ AC
    end

    subgraph B ["**Analysis**"]
        subgraph BA ["**Spatial Processing**"]
            direction LR
            BA1(Roof slope / aspect)
            BA2(Shade - Distant mountains / Local Veg)
            BA3(Roof segment / Solar panel fit - Future)
            BA4(Time-of-day / Time-of-year)
            BA5(Aggregation: Region / National - Future)
        end

        subgraph BB ["**Weather Analysis**"]
            direction LR
            BB1(Cloudy weather probability - Future)
            BB2(Scenarios - cold winter week - Future)
        end

        subgraph BC ["**Temporal Energy (Future)**"]
            direction LR
            BC1(Spot Energy Price - Future)
            BC2(Household/Network Load - Future)
            BC3(Load-shift - Future)
            BC4(Battery optimization - Future)
        end

        %% Layout
        BA ~~~ BB ~~~ BC
    end

    subgraph C ["**Validation**"]
        direction LR
        CA1(Against real installations - Future)
    end

    subgraph D ["**Dissemination**"]
        direction LR
        
        subgraph DA ["**Reports**"]
            direction LR
            DA1[Solar energy potential]
            DA2[Financial viability - Future]
            DA3[Temporal resilience - Future]
            DA4[Network resilience - Future]
            DA5[Scale: Building, Region, Nation]
        end

        subgraph DB ["**Downloads**"]
            direction LR
            DB1[Interactive Web Map]
            DB2[Data and Map Downloads]
            DB3[Open-Source Code]
        end

        %% Layout
        DA ~~~ DB
    end

    %% Sequential Flow
    A --> B --> C --> D
```
_Diagram: High level architecture. Boxes tagged with "Future" are planned for a future implementation._