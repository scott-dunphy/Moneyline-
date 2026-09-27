# Sources

Every map's footer names its data source, year, geography and method. Full
citations follow. No copyrighted map images were downloaded or reused; every
map is drawn from data by the scripts in `R/`.

## U.S. Census Bureau

**American Community Survey (ACS) 5-year estimates, 2020–2024.** U.S. Census Bureau.
Tables B19013 (median household income), B25003 (tenure; renter-occupied housing
units), B01003 (total population) and B11001 (households), census tracts,
Minnesota. API: <https://api.census.gov/data/2024/acs/acs5>.
Documentation: <https://www.census.gov/programs-surveys/acs>.
Used in maps 1, 2 and 5. ACS figures are survey estimates with margins of error,
not official counts.

**ACS migration flows, 2016–2020 5-year.** U.S. Census Bureau, metro-to-metro flows.
API: <https://api.census.gov/data/2020/acs/flows>.
Documentation: <https://www.census.gov/topics/population/migration/guidance/acs-migration-flows.html>.
Used in map 6. 2016–2020 is the latest release with metropolitan-area flows.

**2020 Census P.L. 94-171 Redistricting Data.** U.S. Census Bureau, table P2
(Hispanic or Latino, and not Hispanic or Latino by race), census tracts,
Hennepin County, MN. API: <https://api.census.gov/data/2020/dec/pl>.
Documentation: <https://www.census.gov/programs-surveys/decennial-census/about/rdo/summary-files.html>.
Used in map 3. These are official decennial census counts.

**TIGER/Line and cartographic boundary files.** U.S. Census Bureau.
- Cartographic boundary tracts, counties, places, states and CBSAs:
  <https://www2.census.gov/geo/tiger/GENZ2024/shp/> and <https://www2.census.gov/geo/tiger/GENZ2020/shp/>
- TIGER/Line area water: <https://www2.census.gov/geo/tiger/TIGER2024/AREAWATER/>
- TIGER/Line primary and secondary roads: <https://www2.census.gov/geo/tiger/TIGER2024/PRISECROADS/>
- Overview: <https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html>

Used in all six maps.

## Routing

**Mapbox Isochrone API.** Mapbox. <https://docs.mapbox.com/api/navigation/isochrone/>.
Called through `mapboxapi::mb_isochrone()` when `MAPBOX_PUBLIC_TOKEN` is set.
Mapbox terms: <https://www.mapbox.com/legal/tos>.

**Valhalla isochrone service (fallback).** Public Valhalla server operated by FOSSGIS e.V.,
<https://valhalla1.openstreetmap.de/>, using OpenStreetMap data © OpenStreetMap
contributors, ODbL (<https://www.openstreetmap.org/copyright>). Used for map 5
when no Mapbox token is set; the committed PNG was produced this way, and its
footer says so.

## Synthetic data

**Map 4 point events** are simulated in `R/04_heat_map.R` (fixed random seed)
and are not real 311 calls, permits or crimes. To use a real public point
dataset, one option is the City of Minneapolis Open Data portal,
<https://opendata.minneapolismn.gov/> (for example the `Public_311_2025`
service-request layer); cite it in the footer if you do.

## R packages

tidycensus (Walker & Herman), tigris (Walker), sf (Pebesma), ggplot2 (Wickham et al.),
ggspatial (Dunnington), ggrepel (Slowikowski), patchwork (Pedersen), MASS (Venables & Ripley),
mapboxapi (Walker), httr, jsonlite, dplyr, tidyr, scales, ragg. Cite with
`citation("package")` in R.
